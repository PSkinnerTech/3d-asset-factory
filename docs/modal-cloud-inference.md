# TRELLIS.2 on Modal with a MacBook Controller

This guide explains how to run the heavy TRELLIS.2 step on Modal's serverless GPUs while your
MacBook stays the controller for everything else: spec parsing, OpenAI concept generation,
optimization, QA, review, and exports.

It assumes you already have the 3D Asset Factory CLI working locally with the `mock` runner.

## Architecture

```text
MacBook (you)                                Modal (cloud)
-----------------------------------------    ----------------------------------
python -m asset_factory generate ...  ---->  modal function: trellis_generate
  OpenAI GPT Image 2.0 concept                NVIDIA A10G / A100 / H100
  scripts/modal_trellis_runner.py <-- glb     conda env / pip env with trellis2
  optimize + preview                          model weights cached in volume
  QA + review + exports
```

The MacBook never imports CUDA. The Modal function only does the GPU step. They communicate
through the existing `TRELLIS2_COMMAND` seam — `scripts/modal_trellis_runner.py` runs on the
laptop, calls the deployed Modal function, downloads the resulting GLB, and writes it to
`{output}/raw.glb` so the rest of the pipeline picks it up unchanged.

The files added for this integration are:

- `scripts/modal_trellis_runner.py` — controller-side bridge invoked by `TRELLIS2_COMMAND`.
  Production-quality: validates inputs, calls Modal, validates the GLB payload, writes
  `{output}/raw.glb`, exits non-zero on any failure.
- `infra/modal_trellis.py` — the Modal app/function definition. Pinned to
  `microsoft/TRELLIS.2` (TRELLIS.2-4B weights on Hugging Face), CUDA 12.4, PyTorch 2.6.0,
  A100-80GB GPU by default. Edit the constants at the top of the file to retarget.
- `tests/test_modal_trellis_runner.py` — unit tests for the bridge that mock the Modal call.

## When to choose Modal

Pick Modal when you want:

- A Python-native deployment model. The GPU function is just a decorated Python function.
- Snapshotted container starts and volume-backed model weights, which keep warm latency low.
- Fine-grained per-second billing on the GPU class you select.
- Easy local testing with `modal run` before promoting to `modal deploy`.

Skip Modal if you would rather call a hosted black-box endpoint (Replicate) or stay close to
classic VM/container runtimes with custom Docker images (RunPod Serverless is closer to that).

## Prerequisites

On the MacBook:

- macOS with Python 3.11+ (matches `pyproject.toml`).
- This repo cloned and installed with `python -m pip install -e ".[dev]"`.
- A working `OPENAI_API_KEY`.

Cloud side:

- A Modal account at <https://modal.com>.
- The `modal` CLI installed locally and authenticated (SDK version `>=0.64`, which is what
  `Function.from_name` requires).
- Access to a GPU class with at least 24 GB VRAM. The TRELLIS.2 README lists A100 / H100 as
  the verified configurations; `infra/modal_trellis.py` defaults to `A100-80GB`. A10G works
  for the 512–1024 voxel range at a lower per-second cost; bump to `H100` for the 1536³ path.

## One-time setup

### 1. Install the Modal CLI and authenticate

```bash
python -m pip install 'modal>=0.64'
modal token new
```

`modal token new` opens a browser, asks you to confirm, and stores credentials in
`~/.modal.toml`. Confirm it worked:

```bash
modal profile current
```

### 2. Create the Hugging Face secret

`microsoft/TRELLIS.2-4B` is currently a public Hugging Face repo and an unauthenticated
download works, but `infra/modal_trellis.py` still attaches a Modal secret called
`huggingface` so the function survives the repo being gated in the future and so you can
pre-warm the cache from your account's allowance. Create it with:

```bash
modal secret create huggingface HF_TOKEN=hf_your_token_here
```

If you would rather not create the secret, edit `infra/modal_trellis.py` and remove the
`secrets=[modal.Secret.from_name("huggingface")]` block from the `@app.function(...)`
decorator before deploying.

### 3. Pre-create the weights volume (optional)

The function defines a Modal volume called `trellis2-weights` and mounts it at `/weights`.
Hugging Face caches land in `/weights/hf-cache` so subsequent cold starts skip the ~16 GB
download. Modal creates the volume on first deploy via `create_if_missing=True`, but you can
pre-create it explicitly:

```bash
modal volume create trellis2-weights
```

### 4. Deploy the Modal app

```bash
modal deploy infra/modal_trellis.py
```

The first deploy compiles the CUDA extensions (`flash-attn`, `nvdiffrast`, `nvdiffrec`,
`CuMesh`, `FlexGEMM`, `o_voxel`) from source. Expect the build to take roughly 15–25 minutes;
Modal caches the resulting image so subsequent deploys are fast unless the image definition
changes.

### 5. Retarget GPU / model if needed

Open `infra/modal_trellis.py` and adjust the constants near the top if your workload differs
from the default:

- `GPU` (default `"A100-80GB"`) — set to `"A10G"` to cut cost for 512³–1024³ outputs, or
  `"H100"` for the fastest 1536³ runs.
- `TRELLIS_MODEL_ID` (default `"microsoft/TRELLIS.2-4B"`) — point at a fine-tuned variant if
  you have one published on Hugging Face with the same `Trellis2ImageTo3DPipeline` layout.
- `FUNCTION_TIMEOUT_SECONDS` (default `1200`) — raise this if you target very high
  resolutions or expect long cold starts.

You can sanity-check the GPU function in isolation with the bundled local entrypoint:

```bash
modal run infra/modal_trellis.py::smoke --image-path /tmp/concept.png \
                                        --output-path /tmp/raw.glb
```

If `smoke` produces a valid GLB at `/tmp/raw.glb`, the GPU side is fine and any remaining
failures are on the controller. If `smoke` fails, inspect `modal app logs trellis2-inference`
— the most common first-deploy failure is a CUDA extension that did not compile against the
PyTorch wheel in the image (re-run the deploy after fixing the version mismatch).

## Wire it into `TRELLIS2_COMMAND`

On the MacBook before each run:

```bash
export OPENAI_API_KEY="sk-your-development-key"
export TRELLIS2_COMMAND='.venv/bin/python scripts/modal_trellis_runner.py {image} {output} {resolution}'
```

The `TrellisCommandRunner` (see `src/asset_factory/runners/trellis.py`) expands `{image}`,
`{output}`, and `{resolution}` from the pipeline state. The runner must produce
`{output}/raw.glb`, exit 0 on success, and write a useful error to stderr otherwise.
Use the Python executable from the environment where `modal` is installed; in this repo's local
development setup that is usually `.venv/bin/python`, and using a bare `python` command can fail
on systems that only expose `python3`.

`scripts/modal_trellis_runner.py` also accepts overrides through environment variables, useful
if you want to run more than one Modal app side by side:

```bash
export MODAL_TRELLIS_APP="trellis2-inference"        # default
export MODAL_TRELLIS_FUNCTION="trellis_generate"     # default
```

## End-to-end command

```bash
export OPENAI_API_KEY="sk-your-development-key"
export TRELLIS2_COMMAND='.venv/bin/python scripts/modal_trellis_runner.py {image} {output} {resolution}'

python -m asset_factory generate assets/seeds/chloroplast_conceptual.yaml --runner trellis
```

What happens, in order:

1. Laptop renders the concept image with OpenAI GPT Image 2.0.
2. `TrellisCommandRunner` expands `TRELLIS2_COMMAND` and launches
   `scripts/modal_trellis_runner.py`.
3. The runner reads the concept image bytes and looks up the deployed Modal function via
   `modal.Function.from_name`.
4. Modal cold-starts (first call) or reuses a warm container, runs TRELLIS.2, and returns the
   raw GLB bytes.
5. The runner validates the `glTF` magic header and writes
   `runs/<asset_id>/<timestamp>/trellis/raw.glb`.
6. Local steps continue: optimize, previews, QA, review HTML, export packages, manifest.

## Expected output contract

After a successful run:

```text
runs/<asset_id>/<timestamp>/trellis/raw.glb
runs/<asset_id>/<timestamp>/trellis/raw_report.json
```

`raw_report.json` is written by `TrellisCommandRunner` and includes the expanded command,
stdout, stderr, return code, and timing.

## Debugging tips

- `modal app logs trellis2-inference` streams logs from the live deployment.
- `modal run infra/modal_trellis.py::smoke --image-path concept.png --output-path raw.glb`
  invokes the function directly, isolating laptop-wrapper bugs from GPU bugs.
- If `raw_report.json` shows `error_type: MissingRawGlbError`, the runner exited 0 but did
  not write `raw.glb`. Look at the runner stderr — `validate_glb_bytes` should have raised a
  `RunnerError` first.
- If `raw_report.json` shows `error_type: NonZeroReturnCodeError`, read the `stderr` field of
  the report. The runner prefixes every error with `modal_trellis_runner:`.
- `modal_trellis_runner: the 'modal' package is required ...` — `pip install modal` and run
  `modal token new` in the same Python environment you use for the pipeline.
- `modal_trellis_runner: could not look up Modal function ...` — you have not run
  `modal deploy infra/modal_trellis.py` yet (or your local credentials point at a different
  Modal workspace than the deployment).
- `modal_trellis_runner: Modal function payload missing glTF magic header` — the function
  returned data, but it is not a valid GLB. Likely the upstream TRELLIS.2 entrypoint produced
  a different file format, or returned the wrong file. Use `modal run ... ::smoke` to inspect.
- Cold starts have two components: container snapshot restore (typically 5–15 s) and the
  first-time Hugging Face download of TRELLIS.2-4B into the `trellis2-weights` volume
  (~16 GB, runs once and is cached for every subsequent worker). Keep a warm pool with
  `min_containers=1` on the `@app.function(...)` decorator if you need predictable latency.
- Inference time per the upstream README on an H100: ~3 s at 512³, ~17 s at 1024³, ~60 s at
  1536³. A100-80GB is ~30 % slower; A10G is meaningfully slower at the high end.

## Local testing without Modal

`scripts/modal_trellis_runner.py` exposes an injectable `invoker` so you can run the
controller logic without ever touching Modal. The bundled tests do this:

```bash
python -m pytest tests/test_modal_trellis_runner.py -q
```

The tests cover argument parsing, input validation, GLB header validation, output writing,
and the failure-path exit codes the asset factory pipeline relies on.

## Cost and latency notes

- GPU choice dominates cost. A10G is the cheapest viable class; A100-80GB and H100 are faster
  but several times the per-second rate.
- Modal bills per-second of GPU wall time while the function is running, plus a small overhead
  for container startup. Idle warm containers don't bill GPU time.
- Cache model weights in a `modal.Volume` (already wired in the template) so they don't
  re-download on cold start.
- The OpenAI image cost is separate and incurred on the laptop side, not on Modal.

## When Modal is the right choice

Pick Modal when you want a Python-first, code-defined deployment, low ops overhead, and the
ability to iterate on the GPU function the same way you iterate on any other Python module. It
fits this repo cleanly because the existing `TRELLIS2_COMMAND` seam was designed for exactly
this kind of subprocess wrapper.

If you need a fully managed HTTP-only endpoint with no Python on the laptop, see
[Replicate](replicate-cloud-inference.md). If you want raw Docker control over the GPU runtime
with serverless billing, see [RunPod Serverless](runpod-serverless-inference.md).
