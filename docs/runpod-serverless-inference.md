# TRELLIS.2 on RunPod Serverless with a MacBook Controller

This guide explains how to run the TRELLIS.2 GPU step on RunPod Serverless while your MacBook
remains the orchestrator: OpenAI image generation, optimization, QA, review, and exports all
stay local.

It assumes you already have the 3D Asset Factory CLI working locally with the `mock` runner.

## Architecture

```text
MacBook (you)                                RunPod Serverless (cloud)
-----------------------------------------    ----------------------------------
python -m asset_factory generate ...  ---->  endpoint: trellis2-prod
  OpenAI GPT Image 2.0 concept                NVIDIA L4 / A40 / A100 / H100
  TRELLIS2_COMMAND wrapper       <---- glb    Docker image you push
  optimize + preview                          handler.py reads job input
  QA + review + exports                       writes raw.glb, returns base64
```

The MacBook never touches CUDA. The serverless worker is a container with a single `handler`
function that takes a base64-encoded concept image, runs TRELLIS.2, and returns the GLB bytes
(or a presigned URL). Your laptop integrates through the existing `TRELLIS2_COMMAND` seam — a
small wrapper script submits the job, polls until done, downloads the GLB, and writes it to
`{output}/raw.glb`.

## When to choose RunPod Serverless

Pick RunPod Serverless when you want:

- Full control over the container image, with a normal Docker workflow.
- A broad GPU selection (L4, A40, A100, H100) at competitive per-second pricing.
- HTTP-only integration so the laptop doesn't need a Python SDK.
- Easy worker scaling with min/max workers, idle timeouts, and queue concurrency.

Skip RunPod Serverless if you prefer a Python-decorator deployment (Modal) or a fully managed
public endpoint with no Docker (Replicate).

## Prerequisites

On the MacBook:

- macOS with Python 3.11+ (matches `pyproject.toml`).
- This repo cloned and installed with `python -m pip install -e ".[dev]"`.
- A working `OPENAI_API_KEY`.
- Docker Desktop (or `colima` / `orbstack`) to build the image. RunPod expects `linux/amd64`,
  so on Apple Silicon you must build with `--platform linux/amd64`.

Cloud side:

- A RunPod account at <https://runpod.io>.
- A RunPod API key (Account → Settings → API Keys).
- A container registry to push to: Docker Hub, GHCR, or RunPod's bundled registry.
- A target GPU class with 24 GB+ VRAM.

## One-time RunPod setup

1. Create an API key at <https://runpod.io/console/user/settings>. Copy the value.
2. Pick a registry. The examples below use Docker Hub as `your-dockerhub-user`.
3. (Optional) Create a Network Volume for model weights so cold starts don't re-download them.
   Console → Storage → Network Volumes. Mount path is configured per endpoint.

## The serverless worker (template)

Add a worker package under `infra/runpod_worker/`. This is illustrative — the imports into
TRELLIS.2 need to match your install.

`infra/runpod_worker/handler.py`:

```python
# Template: RunPod Serverless handler for TRELLIS.2.
import base64
import os
import pathlib
import tempfile

import runpod

WEIGHTS_DIR = os.environ.get("TRELLIS_WEIGHTS", "/runpod-volume/trellis2")


def handler(event):
    job_input = event.get("input", {}) or {}
    image_b64 = job_input.get("image_b64")
    resolution = int(job_input.get("resolution", 1024))

    if not image_b64:
        return {"error": "missing input.image_b64"}

    work = pathlib.Path(tempfile.mkdtemp())
    in_path = work / "concept.png"
    out_path = work / "raw.glb"
    in_path.write_bytes(base64.b64decode(image_b64))

    os.environ["TRELLIS_WEIGHTS"] = WEIGHTS_DIR
    from trellis2.inference import image_to_glb  # placeholder import
    image_to_glb(str(in_path), str(out_path), resolution=resolution)

    return {
        "raw_glb_b64": base64.b64encode(out_path.read_bytes()).decode("ascii"),
        "resolution": resolution,
    }


runpod.serverless.start({"handler": handler})
```

`infra/runpod_worker/Dockerfile`:

```dockerfile
# Template Dockerfile. Pin versions to what TRELLIS.2 was tested with.
FROM nvidia/cuda:12.4.1-cudnn-devel-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends \
        git python3.11 python3-pip ffmpeg libgl1 \
    && rm -rf /var/lib/apt/lists/*

RUN python3.11 -m pip install --no-cache-dir \
        runpod \
        torch==2.4.0 torchvision==0.19.0

RUN git clone https://github.com/microsoft/TRELLIS.git /opt/trellis2 \
    && python3.11 -m pip install --no-cache-dir -e /opt/trellis2

WORKDIR /app
COPY handler.py /app/handler.py
CMD ["python3.11", "-u", "/app/handler.py"]
```

Build and push (on a MacBook target `linux/amd64` explicitly):

```bash
docker buildx build \
    --platform linux/amd64 \
    -t your-dockerhub-user/trellis2-runpod:latest \
    --push \
    infra/runpod_worker
```

## Create the endpoint

In the RunPod console:

1. Serverless → Endpoints → New Endpoint.
2. Container image: `your-dockerhub-user/trellis2-runpod:latest`.
3. GPU type: pick A40 or higher. Set min workers to 0 (cold) or 1 (warm) depending on budget.
4. Container disk: at least 30 GB. Idle timeout: 5 s for cost, 5 min for warm reuse.
5. Attach the Network Volume to `/runpod-volume` if you created one.
6. Save. Copy the endpoint ID — it looks like `abc1234xyz`.

## Local wrapper script (template)

`TRELLIS2_COMMAND` expects a process that reads `{image}`, writes `{output}/raw.glb`, and exits
with status 0. Add `scripts/runpod_trellis_runner.py`:

```python
# scripts/runpod_trellis_runner.py
# Template: invoked by TRELLIS2_COMMAND.
# Usage: runpod_trellis_runner.py {image} {output} [resolution]
import base64
import os
import pathlib
import sys
import time

import requests

API_KEY = os.environ["RUNPOD_API_KEY"]
ENDPOINT_ID = os.environ["RUNPOD_ENDPOINT_ID"]
BASE = f"https://api.runpod.ai/v2/{ENDPOINT_ID}"
HEADERS = {"Authorization": f"Bearer {API_KEY}"}


def submit(image_b64: str, resolution: int) -> str:
    r = requests.post(
        f"{BASE}/run",
        headers=HEADERS,
        json={"input": {"image_b64": image_b64, "resolution": resolution}},
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["id"]


def wait(job_id: str, timeout_s: int = 900) -> dict:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        r = requests.get(f"{BASE}/status/{job_id}", headers=HEADERS, timeout=30)
        r.raise_for_status()
        payload = r.json()
        status = payload.get("status")
        if status == "COMPLETED":
            return payload["output"]
        if status in {"FAILED", "CANCELLED", "TIMED_OUT"}:
            raise RuntimeError(f"runpod job {job_id} status={status}: {payload}")
        time.sleep(2)
    raise TimeoutError(f"runpod job {job_id} did not finish in {timeout_s}s")


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: runpod_trellis_runner.py <image_path> <output_dir> [resolution]",
              file=sys.stderr)
        return 2
    image_path = pathlib.Path(sys.argv[1])
    output_dir = pathlib.Path(sys.argv[2])
    resolution = int(sys.argv[3]) if len(sys.argv) > 3 else 1024
    output_dir.mkdir(parents=True, exist_ok=True)

    image_b64 = base64.b64encode(image_path.read_bytes()).decode("ascii")
    job_id = submit(image_b64, resolution)
    output = wait(job_id)
    (output_dir / "raw.glb").write_bytes(base64.b64decode(output["raw_glb_b64"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

If the GLB grows beyond a few megabytes, switch the handler to upload to S3 / R2 / a RunPod
volume and return a presigned URL instead of base64. Base64 is fine for proofs of concept.

## Environment variables

On the MacBook before each run:

```bash
export OPENAI_API_KEY="sk-your-development-key"
export RUNPOD_API_KEY="rpa_your_runpod_key"
export RUNPOD_ENDPOINT_ID="abc1234xyz"
export TRELLIS2_COMMAND='python scripts/runpod_trellis_runner.py {image} {output} {resolution}'
```

The runner expands `{image}`, `{output}`, and `{resolution}` as defined in
`src/asset_factory/runners/trellis.py`. The wrapper must write `{output}/raw.glb` and exit 0.

## Example end-to-end command

```bash
export OPENAI_API_KEY="sk-your-development-key"
export RUNPOD_API_KEY="rpa_your_runpod_key"
export RUNPOD_ENDPOINT_ID="abc1234xyz"
export TRELLIS2_COMMAND='python scripts/runpod_trellis_runner.py {image} {output} {resolution}'

python -m asset_factory generate assets/seeds/chloroplast_conceptual.yaml --runner trellis
```

What happens, in order:

1. Laptop renders the concept image with OpenAI GPT Image 2.0.
2. `TrellisCommandRunner` expands `TRELLIS2_COMMAND` and launches the wrapper.
3. The wrapper POSTs the base64 image to `/v2/{endpoint}/run`.
4. RunPod schedules a worker (warm or cold), runs the handler, and returns the GLB.
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

- `curl -s -H "Authorization: Bearer $RUNPOD_API_KEY" \
        "https://api.runpod.ai/v2/$RUNPOD_ENDPOINT_ID/health"` confirms credentials and
  endpoint state.
- Worker logs live in the RunPod console under the endpoint → Workers → Logs.
- Build the image once and run it locally with `docker run --rm -p 8000:8000 ...` to verify
  imports load before pushing.
- `MissingRawGlbError` from the local runner means the wrapper exited 0 without writing
  `raw.glb`. Inspect `raw_report.json` and the wrapper's stdout/stderr.
- `NonZeroReturnCodeError` means the wrapper itself errored. The `stderr` in `raw_report.json`
  almost always identifies the problem (missing env var, 401, malformed job input).
- Set request timeouts generously — TRELLIS.2 inference plus cold start can exceed 60 s.

## Cost and latency notes

- Per-second billing on the chosen GPU; price varies by class and community vs. secure cloud.
- Cold start time is dominated by container pull and weight load. Keep weights on a Network
  Volume mounted into the container.
- Set `min workers = 1` for low latency, `min workers = 0` to pay only when running.
- Concurrency: RunPod can queue multiple jobs per worker; set `max workers` to bound spend.
- OpenAI image cost is separate and stays on the laptop side.

## When RunPod Serverless is the right choice

Pick RunPod Serverless when you want a Docker-native workflow with full control over the image,
mature HTTP semantics, and broad GPU pricing options. The HTTP-only client fits the existing
`TRELLIS2_COMMAND` seam without any extra Python dependencies on the laptop.

If you would rather write a decorated Python function and skip Docker, see
[Modal](modal-cloud-inference.md). If you want a fully managed public model endpoint with no
ops, see [Replicate](replicate-cloud-inference.md).
