# Modal TRELLIS.2 Live Smoke Test Plan

This plan covers the next phase after PR #10 merged the concrete Modal TRELLIS.2
implementation into `main`: taking the code from "merged and green in CI" to a
first successful cloud inference run on Modal, driven from a MacBook Pro M3 Max
controller.

The audience is Patrick, working alone, on macOS. It is written to be
executable top-to-bottom from a fresh `main` checkout, with explicit decision
points where the upstream TRELLIS.2 surface, GPU pricing, or Hugging Face
access could force a divergence.

## 1. Purpose and desired end state

**Goal.** Produce a valid `raw.glb` on the MacBook by calling the Modal-hosted
TRELLIS.2 function with a concept image, then run that same path inside the
asset factory pipeline end-to-end and land a real run directory under
`runs/<asset_id>/<timestamp>/` with a manifest, QA report, review HTML, and
export packages.

**Done when:**

- `modal deploy infra/modal_trellis.py` succeeds and `modal app list` shows
  `trellis2-inference` as deployed.
- Ephemeral GPU smoke:
  `modal run infra/modal_trellis.py::smoke --image-path <concept.png>
  --output-path /tmp/raw.glb` writes a non-empty GLB whose first 4 bytes are
  `glTF`. This proves the Modal image, TRELLIS.2 imports, and function body.
- Deployed-function smoke:
  `.venv/bin/python scripts/modal_trellis_runner.py <concept.png> <out_dir> 1024` writes
  `out_dir/raw.glb` from the laptop with no Modal SDK errors. This proves the
  deployed app lookup path used by `TRELLIS2_COMMAND`.
- `python -m asset_factory generate assets/seeds/chloroplast_conceptual.yaml
  --runner trellis` with `TRELLIS2_COMMAND` pointed at
  `scripts/modal_trellis_runner.py` completes through optimize, QA, review,
  and exports.
- The final `manifest.json` records a `trellis` runner with a real GLB, not the
  mock runner stub.

Anything short of all five is "in progress", not "done".

## 2. Current repo state after the Modal PRs

After #10 merged into `main`:

- `infra/modal_trellis.py` — concrete Modal app. Defines:
  - `APP_NAME = "trellis2-inference"`, `FUNCTION_NAME = "trellis_generate"`.
  - CUDA 12.4 + Python 3.10 base, PyTorch 2.6.0, flash-attn 2.7.3, nvdiffrast,
    nvdiffrec, CuMesh, FlexGEMM, o-voxel.
  - `microsoft/TRELLIS.2-4B` weights via Hugging Face, cached in the
    `trellis2-weights` Modal volume mounted at `/weights`.
  - Default GPU `A100-80GB`, timeout 20 min, `huggingface` secret attached.
  - `@app.local_entrypoint() smoke(image_path, output_path, resolution)` for
    direct `modal run` testing.
- `scripts/modal_trellis_runner.py` — controller-side subprocess that
  `TRELLIS2_COMMAND` invokes. Calls `modal.Function.from_name(...)`, validates
  the `glTF` magic header, writes `{output}/raw.glb`. Returns clear errors on
  missing Modal SDK, missing deploy, bad payload.
- `tests/test_modal_trellis_runner.py` — unit tests with a mocked invoker.
  These already pass in CI; they do not exercise the live Modal path.
- `docs/modal-cloud-inference.md` — reference walkthrough (architecture,
  decisions, debugging tips). This plan is the **operational** counterpart:
  what to type, in what order, today.
- `README.md` `### Modal (MacBook controller, GPU in the cloud)` section has
  the canonical command sequence.

The pipeline contract is unchanged: `TRELLIS2_COMMAND` expands `{image}`,
`{output}`, `{resolution}` and must produce `{output}/raw.glb`. Everything
downstream (optimize, QA, review, export, manifest) treats the runner as a
black box.

## 3. Architecture recap

```text
MacBook M3 Max (controller)              Modal (cloud, NVIDIA GPU)
-------------------------------          --------------------------------
python -m asset_factory generate         @app.function trellis_generate
  └─ spec parse                            ├─ image=Trellis2ImageTo3DPipeline
  └─ OpenAI GPT Image 2.0  ── concept ──►│   .from_pretrained(...)
  └─ TrellisCommandRunner                 ├─ pipeline.run(pil_image)
       expands TRELLIS2_COMMAND           ├─ mesh.simplify(16777216)
  └─ scripts/modal_trellis_runner.py      └─ o_voxel.postprocess.to_glb(...)
       modal.Function.from_name           returns: raw GLB bytes
       fn.remote(image_bytes, res)  ◄──── (Modal SDK serializes the response)
  └─ validate `glTF` magic
  └─ write {output}/raw.glb
  └─ optimize / preview / QA / review / export / manifest (all local)
```

Two seams matter:

1. **`TRELLIS2_COMMAND`** — the environment-variable command template the
   pipeline's `TrellisCommandRunner` expands. This is the only interface
   between the laptop pipeline and any GPU host (local CUDA box, SSH, RunPod,
   Replicate, or Modal). Today this points at
   `.venv/bin/python scripts/modal_trellis_runner.py {image} {output} {resolution}`.
2. **`raw.glb` contract** — the runner's only obligation is to put a valid GLB
   (file starts with `glTF`, non-empty, non-zero exit) at `{output}/raw.glb`.
   `TrellisCommandRunner` also writes `raw_report.json` (command, stdout,
   stderr, return code, timing) alongside. If `raw.glb` is missing the
   pipeline raises `MissingRawGlbError`; if the runner exits non-zero it
   raises `NonZeroReturnCodeError`. Both surface in QA as a failed run.

The MacBook never imports `torch`, `flash-attn`, or anything CUDA. All of that
lives inside the Modal image.

## 4. Prerequisites and accounts

**Accounts**

- Modal account at <https://modal.com>. Free tier is sufficient for the smoke
  test; the A100-80GB minutes will appear on the included credits.
- Hugging Face account with an `HF_TOKEN`. Required only if upstream gates
  `microsoft/TRELLIS.2-4B`. As of PR #10 the repo is public, but the Modal
  function still mounts a `huggingface` secret so it survives gating.
- GitHub access to `PSkinnerTech/3d-asset-factory` (already given).
- OpenAI API key with image generation enabled (`OPENAI_API_KEY`). Used for
  the concept image step that precedes Modal.

**Local toolchain (MacBook M3 Max, macOS)**

- Python 3.11+ (matches `pyproject.toml` `requires-python = ">=3.11"`).
- Either `uv` (preferred for speed on M3) or `python -m pip`. Both work; the
  examples below use `pip` for fidelity to the README.
- `git`, `gh` (optional, for PR work later).
- Browser available for the Modal OAuth confirmation step.

**No local CUDA, no Conda, no torch on the laptop.** That is the entire point
of putting TRELLIS.2 on Modal — keep the controller clean.

## 5. Step-by-step local setup from a fresh `main` checkout

```bash
# 5.1 — fresh clone
git clone https://github.com/PSkinnerTech/3d-asset-factory.git
cd 3d-asset-factory
git checkout main
git pull --ff-only

# 5.2 — virtualenv (uv variant)
uv venv --python 3.11
source .venv/bin/activate
uv pip install -e ".[dev]"
uv pip install 'modal>=0.64'

# 5.2 alt — virtualenv (stdlib pip variant)
# python3.11 -m venv .venv
# source .venv/bin/activate
# python -m pip install -e ".[dev]"
# python -m pip install 'modal>=0.64'

# 5.3 — confirm the toolchain
python -c "import modal; print(modal.__version__)"
python -m ruff check .
python -m pytest -q

# 5.4 — confirm the mock path still works (sanity for the rest of the pipeline)
python -m asset_factory generate assets/seeds/chloroplast_conceptual.yaml --runner mock
```

The mock run must succeed before going anywhere near Modal. If it doesn't,
fix that first — Modal will not save you from a broken local pipeline.

## 6. Modal authentication, secrets, and volume

```bash
# 6.1 — authenticate the local SDK to your Modal workspace
modal token new
# (opens a browser; confirm; credentials land in ~/.modal.toml)
modal profile current

# 6.2 — create the Hugging Face secret. The Modal function decorator
# references it by name; deploy will fail loudly if it is missing.
modal secret create huggingface HF_TOKEN=hf_your_token_here

# 6.3 — pre-create the weights volume (optional; `create_if_missing=True`
# means the first deploy will create it anyway).
modal volume create trellis2-weights

# 6.4 — verify
modal secret list | grep huggingface
modal volume list | grep trellis2-weights
```

If you cannot or do not want to create the Hugging Face secret, edit
`infra/modal_trellis.py` and remove the `secrets=[modal.Secret.from_name(
"huggingface")]` argument from the `@app.function(...)` decorator before
deploying. This is fine while `microsoft/TRELLIS.2-4B` is public.

## 7. Deploy the Modal app

```bash
modal deploy infra/modal_trellis.py
```

What to expect on the first deploy:

- **Image build, 15–25 minutes.** Modal builds the CUDA 12.4 image, installs
  PyTorch 2.6.0, compiles `flash-attn==2.7.3` against that torch
  (`--no-build-isolation`), then clones and builds `nvdiffrast`, `nvdiffrec`,
  `CuMesh`, `FlexGEMM`, and `o-voxel`. Each of these CUDA extensions adds a
  few minutes.
- **Image cache hit on subsequent deploys.** Unless you change the image
  definition (apt packages, pip lines, run_commands, or env), redeploys are
  near-instant.
- **No GPU is charged during build.** Modal builds on its own infrastructure.

Follow logs in another terminal if you want a live view:

```bash
modal app logs trellis2-inference -f
```

When the deploy returns, confirm:

```bash
modal app list | grep trellis2-inference
```

## 8. Run the ephemeral Modal GPU smoke test

This is the most important first GPU check. It isolates image-build,
dependency, upstream TRELLIS.2 API, and function-body problems from
controller-side problems.

Important nuance: `modal run` creates an ephemeral app for the local entrypoint.
Passing this step proves the Modal function can run on a GPU, but it does **not**
prove the deployed app lookup used by `modal.Function.from_name(...)`. Step 9
proves that deployed-function path.

```bash
# 8.1 — get any small RGBA-ish PNG. The chloroplast concept output from a
# prior mock run works, or generate one fresh:
python -m asset_factory generate assets/seeds/chloroplast_conceptual.yaml \
  --runner mock
# locate the concept.png that mock produced under
# runs/chloroplast_001/<timestamp>/image/concept.png

# 8.2 — run the bundled smoke entrypoint against the app definition
modal run infra/modal_trellis.py::smoke \
  --image-path runs/chloroplast_001/<timestamp>/image/concept.png \
  --output-path /tmp/raw.glb \
  --resolution 1024
```

What to expect:

- **First call: long cold start.** Modal cold-starts a fresh container,
  downloads `microsoft/TRELLIS.2-4B` (~16 GB) into the `trellis2-weights`
  volume, then runs inference. Plan on 5–10 minutes wall time.
- **Subsequent calls: warm.** Per upstream README on H100: ~3 s @ 512³,
  ~17 s @ 1024³, ~60 s @ 1536³. A100-80GB is ~30 % slower. The volume keeps
  the weights, so cold containers still skip the download.

Success criteria:

```bash
test -s /tmp/raw.glb && head -c 4 /tmp/raw.glb
# must print: glTF
```

Anything else — `head -c 4` printing nothing, an HTML error page, a JSON
payload, a zero-byte file — means the GPU side is wrong and the controller
will fail the same way. Fix Modal before moving to step 9.

Passing this step means the GPU-side implementation is viable. The live
integration is still not done until the deployed-function smoke in step 9 also
passes.

## 9. Run end-to-end through `scripts/modal_trellis_runner.py`

Once the ephemeral GPU smoke test passes, exercise the deployed app by name.
This is the first test that uses the same lookup path as the pipeline:
`modal.Function.from_name("trellis2-inference", "trellis_generate")`.

If step 8 passed but this step fails, focus on deployment, Modal workspace /
environment selection, app name, or function name rather than TRELLIS.2 itself.

```bash
# 9.1 — deployed-function smoke through the controller runner,
# outside the asset-factory pipeline
mkdir -p /tmp/runner_out
.venv/bin/python scripts/modal_trellis_runner.py \
  runs/chloroplast_001/<timestamp>/image/concept.png \
  /tmp/runner_out \
  1024

# expect:
#   wrote /tmp/runner_out/raw.glb
# and:
test -s /tmp/runner_out/raw.glb && head -c 4 /tmp/runner_out/raw.glb
# must print: glTF
```

If the runner errors with `the 'modal' package is required ...` you're in the
wrong virtualenv. `which python` should point at the repo's `.venv`.

If it errors with `could not look up Modal function trellis2-inference::
trellis_generate ...`, the deploy didn't land in this workspace. Re-run
`modal deploy infra/modal_trellis.py` and `modal app list`.

Then the full asset factory run:

```bash
# 9.2 — wire it into the pipeline
export OPENAI_API_KEY="sk-your-development-key"
export TRELLIS2_COMMAND='.venv/bin/python scripts/modal_trellis_runner.py {image} {output} {resolution}'

python -m asset_factory generate assets/seeds/chloroplast_conceptual.yaml \
  --runner trellis
```

The pipeline will:

1. Generate the OpenAI concept image locally.
2. `TrellisCommandRunner` expands `TRELLIS2_COMMAND` and launches the runner
   subprocess with the concrete image path, output dir, and resolution.
3. The runner calls Modal, validates the GLB, writes `raw.glb`.
4. The pipeline continues into `optimize`, previews, QA, `review.html`,
   `exports/{web,unity,unreal}`, and `manifest.json`.

## 10. Expected outputs and how to verify success

Run directory layout from `runs/chloroplast_001/<timestamp>/`:

```text
image/concept.png            # OpenAI GPT Image 2.0
image/prompt.txt
trellis/raw.glb              # from Modal — non-zero size, starts with "glTF"
trellis/raw_report.json      # from TrellisCommandRunner; runner_type=trellis-command
optimize/asset.glb
previews/thumbnail.png
previews/turntable.webm
reports/qa.json
reports/review.html
exports/web/
exports/unity/
exports/unreal/
manifest.json
```

Verification checklist:

```bash
RUN=runs/chloroplast_001/$(ls -t runs/chloroplast_001 | head -1)

# raw GLB exists, non-empty, valid magic
test -s "$RUN/trellis/raw.glb" && head -c 4 "$RUN/trellis/raw.glb"   # glTF

# runner report shows success
python -m json.tool "$RUN/trellis/raw_report.json" | head -40

# QA gate passed
python -m json.tool "$RUN/reports/qa.json" | head -40

# manifest references the trellis runner, not the mock
python -m json.tool "$RUN/manifest.json" | grep -E 'runner|trellis'

# review page renders locally
python -m asset_factory review "$RUN"
```

If the QA gate fails on triangle count or GLB size, that is *not* a Modal
problem — TRELLIS.2 produced output that violated the spec's `qa` thresholds
in `assets/seeds/chloroplast_conceptual.yaml`. Tune the spec, not the runner.

## 11. Failure modes and debugging tree

Walk this in order. Each rung is cheaper than the next.

### 11.1 Modal authentication

Symptoms: `modal token new` doesn't open a browser, or `modal profile current`
errors. Fixes:

- Ensure `modal` is installed in the active virtualenv: `python -c "import
  modal; print(modal.__version__)"`.
- If `~/.modal.toml` exists but points at a stale workspace, run
  `modal token new` again and pick the right workspace.
- Corporate networks sometimes block the OAuth callback port. Use a personal
  network or run `modal token new --no-verify` if Modal still offers it.

### 11.2 Old Modal SDK (`AttributeError: Function.from_name`)

`scripts/modal_trellis_runner.py` requires `modal>=0.64`. If you pinned an
older version anywhere:

```bash
python -m pip install --upgrade 'modal>=0.64'
python -c "import modal; print(modal.__version__)"
```

### 11.3 Image build failures during `modal deploy`

- **`flash-attn` failing to compile** — almost always a torch version
  mismatch. The image pins `torch==2.6.0` and `flash-attn==2.7.3`. If you
  edited either, revert and redeploy. Build log will be in
  `modal app logs trellis2-inference`.
- **`nvdiffrast` / `CuMesh` / `FlexGEMM` build errors** — these need
  `--no-build-isolation` so they link against the in-image torch. The
  `infra/modal_trellis.py` `run_commands` block already does this. If you
  added another extension, mirror that flag.
- **Apt package missing** — add it to the `.apt_install(...)` list at the top
  of the image definition.
- **Out-of-disk during build** — Modal handles this; if you keep hitting it,
  ask Modal support to raise the build disk for your workspace.

### 11.4 CUDA / flash-attn dependency errors at function start

These show up at the first `fn.remote(...)` invocation, not at deploy time.

- `ImportError: flash_attn_2_cuda` — torch ABI mismatch. Rebuild the image.
- `RuntimeError: CUDA error: no kernel image is available for execution on
  the device` — the GPU class you selected does not match what flash-attn was
  built for. The default `A100-80GB` is safe; if you switched to a class with
  a different compute capability, flash-attn may need a rebuild.

### 11.5 Hugging Face gated model access

Symptoms: function fails inside `Trellis2ImageTo3DPipeline.from_pretrained`
with a 401/403 from `huggingface.co`. Fixes:

- Recreate the Modal secret with a valid token that has `read` on the gated
  repo: `modal secret create huggingface HF_TOKEN=hf_xxx --force`.
- Accept the model license on the Hugging Face website while logged in as the
  same account.
- Confirm the secret is attached by re-deploying — the secret is read at
  function startup, not at deploy time, so a stale secret will not invalidate
  the deploy.

### 11.6 App name / function name mismatch

`modal_trellis_runner: could not look up Modal function ...` — the runner
defaults to `trellis2-inference::trellis_generate`. If you renamed either in
`infra/modal_trellis.py`, set both env vars before running:

```bash
export MODAL_TRELLIS_APP="your-new-app-name"
export MODAL_TRELLIS_FUNCTION="your-new-function-name"
```

### 11.7 No `raw.glb` written

If `raw_report.json` shows `error_type: MissingRawGlbError`, the runner exited
0 but did not write the file. The runner's `validate_glb_bytes` should have
raised first, so this almost always means someone ran a stale wrapper. Check
that `TRELLIS2_COMMAND` actually points at this repo's
`scripts/modal_trellis_runner.py`, not an old copy.

### 11.8 Invalid GLB header

`modal_trellis_runner: Modal function payload missing glTF magic header`. The
function returned data, but it isn't a GLB. Run `modal run
infra/modal_trellis.py::smoke ...` and inspect `/tmp/raw.glb` directly. Likely
the upstream `Trellis2ImageTo3DPipeline` API changed (see decision 12.1).

### 11.9 Timeouts and cold starts

- Function timeout default is `FUNCTION_TIMEOUT_SECONDS = 20 * 60`. Bump it
  in `infra/modal_trellis.py` if you target 1536³ on a slower GPU.
- First call per worker downloads ~16 GB into the volume. Expect 5–10 min.
- For predictable latency after the smoke-test phase, consider
  `scaledown_window` or `min_containers=1` on the `@app.function(...)`
  decorator. Cost this before enabling it: warm idle containers can still bill
  for reserved resources such as GPU reservation or residual memory. Do not
  leave an A100/H100 warm pool enabled casually.

## 12. Decision points

### 12.1 Upstream TRELLIS.2 API has changed

The function body currently calls:

```python
pipeline = Trellis2ImageTo3DPipeline.from_pretrained(TRELLIS_MODEL_ID)
pipeline.cuda()
mesh = pipeline.run(pil_image)[0]
mesh.simplify(16777216)
glb = o_voxel.postprocess.to_glb(...)
```

If `microsoft/TRELLIS.2` upstream changes any of these signatures, the smoke
test will fail. Options, in order of preference:

1. Update the function body in `infra/modal_trellis.py` to match the new API.
2. Pin the upstream repo at a specific commit SHA in `TRELLIS_REPO_URL` (e.g.
   `https://github.com/microsoft/TRELLIS.2.git@<sha>`). The current pin is
   the default branch — fine for the smoke test, brittle for production.
3. If the change is large (e.g. they replace `o_voxel` with something else),
   stop and write a follow-up spec under `docs/superpowers/specs/` before
   editing further.

### 12.2 A100-80GB is too expensive

The default GPU is `A100-80GB` because it covers the full 512³–1536³ range.
For early iteration, cheaper is better:

- Edit `GPU = "A100-80GB"` to `GPU = "A10"` in `infra/modal_trellis.py`.
  A10 has 24 GB VRAM, which is the upstream minimum and fine for 512³–1024³.
  Older Modal examples may mention `A10G`; prefer the current documented value
  unless your Modal CLI explicitly accepts the older alias.
- Redeploy. The image cache is reused; only the GPU attachment changes.
- Cost the smoke run from the Modal dashboard or billing/usage page after a few
  calls before deciding to stay on A10 or move back up.

### 12.3 Build time is unacceptable

First-deploy build of 15–25 minutes is one-time, but if you iterate on the
image definition it recurs.

- Avoid editing the `.pip_install(...)` / `.run_commands(...)` block unless
  needed; Modal invalidates the cache layer-by-layer.
- Group fast-changing config into `.env(...)` (does not invalidate compile
  layers).
- If you only need to test the *function body* (not the image), use
  `modal run` against the already-deployed function — no rebuild.

### 12.4 Hugging Face access is blocked

If you cannot get an `HF_TOKEN` (account approval pending, model gated):

- Confirm whether `microsoft/TRELLIS.2-4B` is still public. If yes, remove
  the `secrets=[modal.Secret.from_name("huggingface")]` line and redeploy.
- If it is gated, you must either get the token or mirror the weights to a
  bucket you control and point `TRELLIS_MODEL_ID` at a local path inside the
  volume. That is more work than the smoke test deserves — get the token.

## 13. Iteration loop

The recommended inner loop while debugging:

```text
1. Edit infra/modal_trellis.py function body or constants.
2. modal deploy infra/modal_trellis.py          # rebuilds only what changed
3. modal run infra/modal_trellis.py::smoke ...  # GPU-only check
4. .venv/bin/python scripts/modal_trellis_runner.py ...   # controller-only check
5. python -m asset_factory generate ...         # full pipeline check
```

Do not skip rungs. A failure at step 5 with no prior smoke test wastes
minutes per attempt because you cannot tell whether you broke the runner,
the pipeline, or the GPU function.

### When to promote to a first-class `RemoteTrellisRunner`

The current path is `TRELLIS2_COMMAND` → subprocess → script → Modal. That's
the right choice today because it reuses the existing seam and ships with no
changes to `src/asset_factory/runners/`. Promote to a real
`RemoteTrellisRunner` class (sibling of `TrellisCommandRunner`) when **any
two** of these become true:

- The smoke loop is stable and the team needs queueing, retries, or
  concurrency.
- You want structured runner metrics (cold-start ms, GPU seconds, container
  id) in `manifest.json`, not just stdout/stderr text in `raw_report.json`.
- A second remote backend (Replicate, RunPod) is being added and a base class
  would deduplicate the lookup / call / validate logic.
- The script accumulates more than ~250 lines or starts growing flags that
  belong in a config object.

Until then, the script-based runner is the simplest thing that works and
keeps the laptop free of any cloud-SDK coupling at the pipeline layer.

## 14. Optional follow-up checklist

These are not required to declare the smoke test done, but they are the
obvious next stops.

- [ ] Pin `TRELLIS_REPO_URL` to a specific upstream commit SHA so the image
      is reproducible.
- [ ] Add a `min_containers=1` warm pool and measure the latency / cost
      delta over a typical day of iteration.
- [ ] Capture cold-start vs warm-start timings into `raw_report.json` (will
      require either parsing Modal's logs or passing structured timings back
      from the function).
- [ ] Wire `--resolution` through to `pipeline.run(...)` if a future
      TRELLIS.2 revision accepts it; today it is advisory only.
- [ ] Add a Modal-side integration test that runs `::smoke` against a
      checked-in fixture image, behind a `MODAL_LIVE=1` env flag so CI never
      runs it accidentally.
- [ ] Promote the runner to `RemoteTrellisRunner` per section 13 once the
      criteria are met.
- [ ] Extend `docs/modal-cloud-inference.md` with any debugging tips
      discovered during the live smoke test that aren't already documented
      there.
