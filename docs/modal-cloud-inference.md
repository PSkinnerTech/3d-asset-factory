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
  TRELLIS2_COMMAND wrapper      <---- glb     conda env / pip env with trellis2
  optimize + preview                          model weights cached in volume
  QA + review + exports
```

The MacBook never imports CUDA. The Modal function only does the GPU step. They communicate
through the existing `TRELLIS2_COMMAND` seam — a small wrapper script on your laptop runs the
Modal function (over the Modal CLI or Modal Python SDK), downloads the resulting GLB, and writes
it to `{output}/raw.glb` so the rest of the pipeline picks it up unchanged.

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
- Homebrew, optional but convenient.

Cloud side:

- A Modal account at <https://modal.com>.
- The `modal` CLI installed locally and authenticated.
- Access to a GPU class with at least 24 GB VRAM (A10G is the typical minimum for TRELLIS.2,
  A100 / H100 is faster).

## One-time Modal setup

Install and log in to Modal from your MacBook:

```bash
python -m pip install modal
modal token new
```

`modal token new` opens a browser, asks you to confirm, and stores the credentials in
`~/.modal.toml`. Confirm it worked:

```bash
modal profile current
```

Create a Modal secret for any API keys you want the GPU function to see. For this pipeline the
GPU function does not call OpenAI — that stays on the laptop — so the secret is optional. If you
do want the function to log into Hugging Face to pull TRELLIS.2 weights:

```bash
modal secret create huggingface HF_TOKEN=hf_your_token_here
```

## The Modal app (template)

Add a new file at the repo root, for example `infra/modal_trellis.py`. This file is an
illustrative template — adjust the image build and the call into your TRELLIS.2 install to match
the upstream project you are using.

```python
# infra/modal_trellis.py
# Template: edit image build and the trellis2 call site to match your environment.
import modal

GPU = "A10G"  # or "A100-40GB", "A100-80GB", "H100"

image = (
    modal.Image.from_registry("nvidia/cuda:12.4.1-cudnn-devel-ubuntu22.04", add_python="3.11")
    .apt_install("git", "ffmpeg", "libgl1")
    .pip_install(
        "torch==2.4.0",
        "torchvision==0.19.0",
        # add the rest of the TRELLIS.2 dependency set here
    )
    .run_commands(
        "git clone https://github.com/microsoft/TRELLIS.git /opt/trellis2",
        "pip install -e /opt/trellis2",
    )
)

weights_volume = modal.Volume.from_name("trellis2-weights", create_if_missing=True)

app = modal.App("trellis2-inference")

@app.function(
    image=image,
    gpu=GPU,
    volumes={"/weights": weights_volume},
    secrets=[modal.Secret.from_name("huggingface")],
    timeout=60 * 15,
)
def trellis_generate(image_bytes: bytes, resolution: int = 1024) -> bytes:
    import io, os, tempfile, pathlib
    # 1) write the concept image to a temp file
    work = pathlib.Path(tempfile.mkdtemp())
    in_path = work / "concept.png"
    in_path.write_bytes(image_bytes)
    out_path = work / "raw.glb"

    # 2) call into TRELLIS.2 — replace this block with the actual entrypoint
    #    in the upstream repo, pointing weights at /weights.
    os.environ["TRELLIS_WEIGHTS"] = "/weights"
    from trellis2.inference import image_to_glb  # placeholder import
    image_to_glb(str(in_path), str(out_path), resolution=resolution)

    return out_path.read_bytes()
```

Deploy it once:

```bash
modal deploy infra/modal_trellis.py
```

Run it ad-hoc to sanity-check the image build before wiring it into the pipeline:

```bash
modal run infra/modal_trellis.py::trellis_generate --help
```

## Local wrapper script (template)

`TRELLIS2_COMMAND` expects a process that reads `{image}`, writes `{output}/raw.glb`, and exits
with status 0 on success. Add a script at `scripts/modal_trellis_runner.py` to bridge to Modal.
This is a template — adapt to your Modal app name.

```python
# scripts/modal_trellis_runner.py
# Template: invoked by TRELLIS2_COMMAND. Usage: modal_trellis_runner.py {image} {output} [resolution]
import pathlib
import sys

import modal


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: modal_trellis_runner.py <image_path> <output_dir> [resolution]",
              file=sys.stderr)
        return 2
    image_path = pathlib.Path(sys.argv[1])
    output_dir = pathlib.Path(sys.argv[2])
    resolution = int(sys.argv[3]) if len(sys.argv) > 3 else 1024

    output_dir.mkdir(parents=True, exist_ok=True)
    raw_glb = output_dir / "raw.glb"

    fn = modal.Function.from_name("trellis2-inference", "trellis_generate")
    glb_bytes = fn.remote(image_path.read_bytes(), resolution)
    raw_glb.write_bytes(glb_bytes)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Make sure the laptop has `modal` installed in the same Python environment you use for the
pipeline.

## Environment variables

On the MacBook before each run:

```bash
export OPENAI_API_KEY="sk-your-development-key"
export TRELLIS2_COMMAND='python scripts/modal_trellis_runner.py {image} {output} {resolution}'
```

The runner expands `{image}`, `{output}`, and `{resolution}` based on the implementation in
`src/asset_factory/runners/trellis.py`. The wrapper must write `{output}/raw.glb`, exit 0, and
keep stderr clean enough to debug.

## Example end-to-end command

```bash
export OPENAI_API_KEY="sk-your-development-key"
export TRELLIS2_COMMAND='python scripts/modal_trellis_runner.py {image} {output} {resolution}'

python -m asset_factory generate assets/seeds/chloroplast_conceptual.yaml --runner trellis
```

What happens, in order:

1. Laptop renders the concept image with OpenAI GPT Image 2.0.
2. The trellis runner expands `TRELLIS2_COMMAND` and launches `modal_trellis_runner.py`.
3. The wrapper opens an authenticated Modal connection and calls `trellis_generate.remote(...)`.
4. Modal cold-starts (first call) or reuses a warm container.
5. The GLB bytes come back, get written to `runs/<asset_id>/<timestamp>/trellis/raw.glb`.
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
- `modal run infra/modal_trellis.py::trellis_generate --image-bytes ...` lets you invoke the
  function directly with a known-good payload, isolating laptop wrapper bugs from GPU bugs.
- If you see `MissingRawGlbError`, the wrapper exited 0 but did not write `raw.glb`. Check that
  `raw_glb.write_bytes(...)` ran and that the path matches `{output}/raw.glb`.
- If you see `NonZeroReturnCodeError`, look at `trellis/raw_report.json` first — its `stderr`
  field captures the wrapper's traceback.
- Modal cold starts can be 30–90 s the first time per day. Keep a small warmer call if you need
  predictable latency.
- Pin `torch` / CUDA versions to what the TRELLIS.2 upstream tested with. Building the image
  once and pinning is far cheaper than rebuilding on every code edit.

## Cost and latency notes

- GPU choice dominates cost. A10G is the cheapest viable class; A100-80GB and H100 are faster
  but several times the per-second rate.
- Modal bills per-second of GPU wall time while the function is running, plus a small overhead
  for container startup. Idle warm containers don't bill GPU time.
- Cache model weights in a `modal.Volume` so they don't re-download on cold start.
- The OpenAI image cost is separate and incurred on the laptop side, not on Modal.

## When Modal is the right choice

Pick Modal when you want a Python-first, code-defined deployment, low ops overhead, and the
ability to iterate on the GPU function the same way you iterate on any other Python module. It
fits this repo cleanly because the existing `TRELLIS2_COMMAND` seam was designed for exactly
this kind of subprocess wrapper.

If you need a fully managed HTTP-only endpoint with no Python on the laptop, see
[Replicate](replicate-cloud-inference.md). If you want raw Docker control over the GPU runtime
with serverless billing, see [RunPod Serverless](runpod-serverless-inference.md).
