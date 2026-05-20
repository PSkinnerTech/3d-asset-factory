# TRELLIS.2 on Replicate with a MacBook Controller

This guide explains how to call a TRELLIS.2 model hosted on Replicate while your MacBook stays
the orchestrator: spec parsing, OpenAI concept image, optimization, QA, review, and exports
remain local.

It assumes you already have the 3D Asset Factory CLI working with the `mock` runner.

## Architecture

```text
MacBook (you)                                Replicate (cloud)
-----------------------------------------    ----------------------------------
python -m asset_factory generate ...  ---->  model: owner/trellis2 or your fork
  OpenAI GPT Image 2.0 concept                NVIDIA A100 / H100 (managed)
  TRELLIS2_COMMAND wrapper       <---- glb    cog-packaged predict()
  optimize + preview                          returns raw.glb (file or url)
  QA + review + exports
```

The MacBook never touches CUDA. Replicate hosts the model as a Cog package and exposes a stable
HTTP API. Your laptop integrates through the existing `TRELLIS2_COMMAND` seam — a small Python
wrapper runs the Replicate prediction, downloads the returned GLB, and writes it to
`{output}/raw.glb`.

## When to choose Replicate

Pick Replicate when you want:

- The fewest moving parts on the laptop — one API key, one HTTP call, no Docker registry.
- A model registry that handles versioning, autoscaling, and a public/private toggle out of
  the box.
- An existing community model (when one for TRELLIS.2 is available and trusted), or to publish
  your own packaged model.
- Predictable per-second GPU pricing without managing workers.

Skip Replicate if you need fine-grained container control (RunPod Serverless) or if you want to
ship a tightly-coupled Python function alongside the rest of your code (Modal).

## Prerequisites

On the MacBook:

- macOS with Python 3.11+ (matches `pyproject.toml`).
- This repo cloned and installed with `python -m pip install -e ".[dev]"`.
- `OPENAI_API_KEY` set.
- The `replicate` Python SDK installed: `python -m pip install replicate`.
- (Only if you publish your own model) the `cog` CLI from <https://github.com/replicate/cog>
  and Docker. Cog targets `linux/amd64`; on Apple Silicon use `cog push --platform linux/amd64`.

Cloud side:

- A Replicate account at <https://replicate.com>.
- A Replicate API token (Account → API tokens).
- Either:
  - A community TRELLIS.2 model on Replicate that you trust, or
  - Your own Cog-packaged TRELLIS.2 model published as `your-handle/trellis2`.

## One-time Replicate setup

1. Get an API token at <https://replicate.com/account/api-tokens>.
2. Export it locally:

   ```bash
   export REPLICATE_API_TOKEN="r8_your_token"
   ```

3. Pick a model identifier. Either copy the slug of an existing community model
   (`some-user/trellis2`) or publish your own (next section).

### Publishing your own model (template)

If no public TRELLIS.2 model meets your needs, package one with Cog. Add `infra/cog/` with the
following template files.

`infra/cog/cog.yaml`:

```yaml
build:
  gpu: true
  cuda: "12.4"
  python_version: "3.11"
  python_packages:
    - "torch==2.4.0"
    - "torchvision==0.19.0"
    # add the rest of the TRELLIS.2 deps here
  system_packages:
    - "git"
    - "ffmpeg"
    - "libgl1"
  run:
    - "git clone https://github.com/microsoft/TRELLIS.git /opt/trellis2"
    - "pip install -e /opt/trellis2"

predict: "predict.py:Predictor"
```

`infra/cog/predict.py`:

```python
# Template Cog predictor. Adapt to the actual TRELLIS.2 entrypoint.
import pathlib
import tempfile

from cog import BasePredictor, Input, Path


class Predictor(BasePredictor):
    def setup(self):
        from trellis2.inference import load_model  # placeholder import
        self.model = load_model()

    def predict(
        self,
        image: Path = Input(description="Concept image PNG/JPG"),
        resolution: int = Input(default=1024, ge=256, le=2048),
    ) -> Path:
        out_dir = pathlib.Path(tempfile.mkdtemp())
        out_path = out_dir / "raw.glb"
        self.model.image_to_glb(str(image), str(out_path), resolution=resolution)
        return Path(out_path)
```

Build and push:

```bash
cog login
cog push r8.im/your-handle/trellis2 --platform linux/amd64
```

The first push creates the model. Subsequent pushes create new versions.

## Local wrapper script (template)

`TRELLIS2_COMMAND` expects a process that reads `{image}`, writes `{output}/raw.glb`, and exits
with status 0. Add `scripts/replicate_trellis_runner.py`:

```python
# scripts/replicate_trellis_runner.py
# Template: invoked by TRELLIS2_COMMAND.
# Usage: replicate_trellis_runner.py {image} {output} [resolution]
import os
import pathlib
import sys
import urllib.request

import replicate

MODEL = os.environ["REPLICATE_MODEL"]  # e.g. "your-handle/trellis2:VERSION_HASH"


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: replicate_trellis_runner.py <image_path> <output_dir> [resolution]",
              file=sys.stderr)
        return 2
    image_path = pathlib.Path(sys.argv[1])
    output_dir = pathlib.Path(sys.argv[2])
    resolution = int(sys.argv[3]) if len(sys.argv) > 3 else 1024
    output_dir.mkdir(parents=True, exist_ok=True)

    with image_path.open("rb") as f:
        output = replicate.run(
            MODEL,
            input={"image": f, "resolution": resolution},
        )

    raw_glb = output_dir / "raw.glb"
    # Replicate returns either a URL string, a FileOutput-like object, or a list of them.
    item = output[0] if isinstance(output, list) else output

    if hasattr(item, "read"):
        raw_glb.write_bytes(item.read())
    elif isinstance(item, str) and item.startswith(("http://", "https://")):
        urllib.request.urlretrieve(item, raw_glb)
    else:
        raise RuntimeError(f"unexpected replicate output: {type(item).__name__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Pin `REPLICATE_MODEL` to a specific version hash, not a floating tag, so reruns are
reproducible.

## Environment variables

On the MacBook before each run:

```bash
export OPENAI_API_KEY="sk-your-development-key"
export REPLICATE_API_TOKEN="r8_your_token"
export REPLICATE_MODEL="your-handle/trellis2:0123abcd...the_version_hash"
export TRELLIS2_COMMAND='python scripts/replicate_trellis_runner.py {image} {output} {resolution}'
```

The runner expands `{image}`, `{output}`, and `{resolution}` as defined in
`src/asset_factory/runners/trellis.py`. The wrapper must write `{output}/raw.glb` and exit 0.

## Example end-to-end command

```bash
export OPENAI_API_KEY="sk-your-development-key"
export REPLICATE_API_TOKEN="r8_your_token"
export REPLICATE_MODEL="your-handle/trellis2:0123abcd..."
export TRELLIS2_COMMAND='python scripts/replicate_trellis_runner.py {image} {output} {resolution}'

python -m asset_factory generate assets/seeds/chloroplast_conceptual.yaml --runner trellis
```

What happens, in order:

1. Laptop renders the concept image with OpenAI GPT Image 2.0.
2. `TrellisCommandRunner` expands `TRELLIS2_COMMAND` and launches the wrapper.
3. The wrapper streams the image to Replicate as the `image` input.
4. Replicate runs the prediction on a managed GPU and returns the GLB.
5. The wrapper writes `runs/<asset_id>/<timestamp>/trellis/raw.glb`.
6. Local steps continue: optimize, previews, QA, review HTML, export packages, manifest.

## Expected output contract

After a successful run:

```text
runs/<asset_id>/<timestamp>/trellis/raw.glb
runs/<asset_id>/<timestamp>/trellis/raw_report.json
```

`raw_report.json` is written by `TrellisCommandRunner` and contains the expanded command,
stdout, stderr, return code, and timing.

## Debugging tips

- `replicate.predictions.list()` from a Python shell shows recent runs and statuses.
- Every prediction has a web URL like `https://replicate.com/p/<id>` with logs and the input
  image. Bookmark it from the prediction object: `prediction.urls["web"]`.
- `cog predict -i image=@local.png` runs the predictor locally before pushing — fastest way to
  catch dependency errors.
- If you get `MissingRawGlbError`, the wrapper exited 0 without writing `raw.glb`. Inspect
  `raw_report.json` plus the prediction's logs.
- `NonZeroReturnCodeError` usually means the wrapper itself errored — bad token, missing
  `REPLICATE_MODEL`, or a model version that no longer exists. The `stderr` in
  `raw_report.json` identifies which.
- For large GLBs prefer the URL output path. `urllib.request.urlretrieve` streams to disk and
  avoids holding the file in memory.

## Cost and latency notes

- Per-second GPU billing. The exact rate depends on the hardware Replicate routes you to (A100,
  H100, etc.); check the model's hardware setting.
- Cold starts can take 30–60 s while the image and weights load. After that, warm predictions
  are quick.
- Public models incur a per-prediction setup cost the first time you call them after a long
  idle period.
- OpenAI image cost is separate and stays on the laptop side.

## When Replicate is the right choice

Pick Replicate when you want the simplest possible integration: one token, one HTTP call, no
container ops. The wrapper above is the only code you maintain on the laptop, and it slots
directly into the existing `TRELLIS2_COMMAND` seam.

If you need fine-grained container or scaling control, see
[RunPod Serverless](runpod-serverless-inference.md). If you want a Python-decorator deploy
model with code colocated next to the rest of the pipeline, see
[Modal](modal-cloud-inference.md).
