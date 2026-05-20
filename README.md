# EdTech 3D Asset Factory

CLI-first developer tool for generating educational science 3D assets from checked-in specs.

## Reference Demo

GitHub README files do not render X/Twitter iframe embeds, so the demo is linked directly:

[Watch the TRELLIS.2 image-to-3D demo video on X](https://x.com/HowToAI_/status/2056387308287676819)

If this README needs true inline playback later, upload a copy of the video as a GitHub release
asset or repository media file and embed that direct `.mp4` URL.

## Development

```bash
python -m pip install -e ".[dev]"
pytest
```

## Commands

```bash
asset-factory generate assets/seeds/chloroplast_conceptual.yaml
asset-factory qa runs/chloroplast_001/<timestamp>
asset-factory export runs/chloroplast_001/<timestamp> --profile web
asset-factory review runs/chloroplast_001/<timestamp>
```

## Seed Specs

The `assets/seeds` directory contains 10 initial science specs:

- 5 conceptual assets for biology and physics.
- 5 realistic assets for biology and earth science.

Generate one with the mock runner:

```bash
asset-factory generate assets/seeds/chloroplast_conceptual.yaml --runner mock
```

Generate one with TRELLIS.2 once `TRELLIS2_COMMAND` and OpenAI credentials are configured:

```bash
TRELLIS2_COMMAND='python /path/to/trellis_generate.py {image} {output}' \
asset-factory generate assets/seeds/chloroplast_conceptual.yaml --runner trellis
```

## Verified Local Workflow

Mock generation works without OpenAI credentials or TRELLIS.2:

```bash
asset-factory generate assets/seeds/chloroplast_conceptual.yaml --runner mock
```

Expected output:

```text
Generated run: runs/chloroplast_001/20260520T100148Z
```

The generated run contains:

```text
image/concept.png
image/prompt.txt
trellis/raw.glb
trellis/raw_report.json
optimize/asset.glb
previews/thumbnail.png
previews/turntable.webm
exports/web/asset.glb
exports/unity/asset.glb
exports/unreal/asset.glb
reports/qa.json
reports/review.html
manifest.json
```

Inspect the manifest:

```bash
python -m json.tool runs/chloroplast_001/20260520T100148Z/manifest.json | head -80
```

The manifest should include:

```json
{
  "asset": {
    "id": "chloroplast_001"
  },
  "education": {
    "style": "conceptual"
  },
  "provenance": {
    "runner_type": "mock"
  },
  "qa": {
    "passed": true
  }
}
```

OpenAI + TRELLIS.2 generation uses the same spec and run layout:

```bash
export OPENAI_API_KEY="sk-your-development-key"
export TRELLIS2_COMMAND='python /path/to/trellis_generate.py {image} {output}'
asset-factory generate assets/seeds/chloroplast_conceptual.yaml --runner trellis
```

## TRELLIS.2 Inference

The asset factory can run the full pipeline on any machine that can execute the command stored in
`TRELLIS2_COMMAND`. For real TRELLIS.2 inference, that command must run on a Linux NVIDIA GPU host.

MacBook Pro / Apple Silicon is useful for development, spec editing, mock generation, review, and
export validation. It is not a viable target for TRELLIS.2 CUDA inference because the upstream
TRELLIS.2 stack expects Linux, NVIDIA drivers, CUDA, and a GPU with at least 24GB VRAM.

### Runner Contract

`TRELLIS2_COMMAND` is a command template. The asset factory replaces:

- `{image}` with the generated concept image path.
- `{output}` with the run's TRELLIS output directory.
- `{resolution}` with the requested voxel resolution.

The command must create:

```text
{output}/raw.glb
```

It may also write logs or sidecar files into `{output}`. The asset factory writes
`{output}/raw_report.json` with stdout, stderr, return code, timing, and failure details.

### Local GPU Inference

Use this path when you are already inside a Linux NVIDIA GPU machine.

Prerequisites:

- Linux host with an NVIDIA GPU and 24GB+ VRAM.
- CUDA Toolkit installed; CUDA 12.4 is the expected baseline for TRELLIS.2.
- Conda available.
- `OPENAI_API_KEY` set for concept image generation.
- TRELLIS.2 cloned and installed with its model weights available.

Install this tool:

```bash
git clone https://github.com/PSkinnerTech/edtech-3d-asset-factory.git
cd edtech-3d-asset-factory
python -m pip install -e ".[dev]"
```

Install TRELLIS.2 separately:

```bash
git clone -b main https://github.com/microsoft/TRELLIS.2.git --recursive
cd TRELLIS.2
. ./setup.sh --new-env --basic --flash-attn --nvdiffrast --nvdiffrec --cumesh --o-voxel --flexgemm
```

Create a TRELLIS wrapper that follows the runner contract. The exact implementation may need to
track upstream TRELLIS.2 API changes, but the shape is:

```python
# /opt/trellis2/trellis_generate.py
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ["OPENCV_IO_ENABLE_OPENEXR"] = "1"
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

import cv2
import torch
from PIL import Image

import o_voxel
from trellis2.pipelines import Trellis2ImageTo3DPipeline


def main() -> None:
    image_path = Path(sys.argv[1])
    output_dir = Path(sys.argv[2])
    output_dir.mkdir(parents=True, exist_ok=True)

    pipeline = Trellis2ImageTo3DPipeline.from_pretrained("microsoft/TRELLIS.2-4B")
    pipeline.cuda()

    image = Image.open(image_path)
    mesh = pipeline.run(image)[0]
    mesh.simplify(16777216)

    glb = o_voxel.postprocess.to_glb(
        vertices=mesh.vertices,
        faces=mesh.faces,
        attr_volume=mesh.attrs,
        coords=mesh.coords,
        attr_layout=mesh.layout,
        voxel_size=mesh.voxel_size,
        aabb=[[-0.5, -0.5, -0.5], [0.5, 0.5, 0.5]],
        decimation_target=1000000,
        texture_size=4096,
        remesh=True,
        remesh_band=1,
        remesh_project=0,
        verbose=True,
    )
    glb.export(output_dir / "raw.glb", extension_webp=True)


if __name__ == "__main__":
    main()
```

Run the smoke test:

```bash
export OPENAI_API_KEY="sk-your-development-key"
export TRELLIS2_COMMAND='conda run -n trellis2 python /opt/trellis2/trellis_generate.py {image} {output}'

python -m asset_factory generate assets/seeds/chloroplast_conceptual.yaml --runner trellis
```

Validate the generated run:

```bash
python -m json.tool runs/chloroplast_001/*/manifest.json | head -120
asset-factory review runs/chloroplast_001/<timestamp>
```

### SSH Remote Runner

This is the quickest way to use a Mac as the controller while a Linux GPU host performs only the
TRELLIS.2 inference step.

Flow:

```text
MacBook / controller
  generate concept image
  scp concept image to GPU host
  ssh GPU host to run TRELLIS.2
  scp raw.glb back into {output}/raw.glb
  continue local QA, review, and exports
```

Expected GPU host layout:

```text
/opt/trellis2/TRELLIS.2
/opt/trellis2/trellis_generate.py
/tmp/asset-factory-jobs
```

Controller-side wrapper shape:

```python
# scripts/remote_trellis_runner.py
from __future__ import annotations

import shlex
import subprocess
import sys
import uuid
from pathlib import Path


REMOTE = "ubuntu@gpu-host"
REMOTE_ROOT = "/tmp/asset-factory-jobs"
REMOTE_COMMAND = "conda run -n trellis2 python /opt/trellis2/trellis_generate.py"


def run(command: list[str]) -> None:
    subprocess.run(command, check=True)


def main() -> None:
    image = Path(sys.argv[1]).resolve()
    output = Path(sys.argv[2]).resolve()
    output.mkdir(parents=True, exist_ok=True)

    job_id = uuid.uuid4().hex
    remote_job = f"{REMOTE_ROOT}/{job_id}"
    remote_image = f"{remote_job}/input.png"
    remote_output = f"{remote_job}/output"

    run(["ssh", REMOTE, "mkdir", "-p", remote_job, remote_output])
    run(["scp", str(image), f"{REMOTE}:{remote_image}"])
    run([
        "ssh",
        REMOTE,
        f"{REMOTE_COMMAND} {shlex.quote(remote_image)} {shlex.quote(remote_output)}",
    ])
    run(["scp", f"{REMOTE}:{remote_output}/raw.glb", str(output / "raw.glb")])


if __name__ == "__main__":
    main()
```

Run from the controller:

```bash
export OPENAI_API_KEY="sk-your-development-key"
export TRELLIS2_COMMAND='python scripts/remote_trellis_runner.py {image} {output}'

python -m asset_factory generate assets/seeds/chloroplast_conceptual.yaml --runner trellis
```

This path is intentionally simple. It is good for one-developer smoke testing and early demos. It is
not the right long-term interface for queues, team access, retries, auth, or observability.

### Remote Runner API

The better product path is a small GPU service with an HTTP API. The asset factory would gain a
future `RemoteTrellisRunner` that submits an image and receives a GLB plus structured logs.

Suggested API:

```http
POST /v1/generate
Content-Type: multipart/form-data

image=@concept.png
resolution=1024
asset_id=chloroplast_001
```

Successful response:

```json
{
  "job_id": "01j...",
  "status": "succeeded",
  "runner_type": "trellis-remote",
  "runner_version": "trellis2-4b",
  "raw_glb_url": "https://...",
  "metrics": {
    "duration_seconds": 17.2,
    "gpu": "NVIDIA H100"
  }
}
```

Recommended production behavior:

- Store uploaded images and GLBs in object storage.
- Run TRELLIS.2 jobs asynchronously with a queue.
- Return structured failure reports with stderr, model version, GPU type, and timing.
- Require API authentication.
- Keep the CLI runner contract stable so local, SSH, and remote API runners produce the same
  `runs/<asset>/<timestamp>` layout.
