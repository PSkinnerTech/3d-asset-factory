"""Modal app that exposes TRELLIS.2 image-to-3D as a remote function.

This file is a **template**. The local controller-side runner at
``scripts/modal_trellis_runner.py`` is production-quality, but the GPU-side
container build and the TRELLIS.2 entrypoint can vary by upstream commit and
install. Replace the values marked ``TODO`` with the ones that match your
TRELLIS.2 install.

Deploy with::

    modal deploy infra/modal_trellis.py

Once deployed, the controller-side wrapper at ``scripts/modal_trellis_runner.py``
will discover this function via ``modal.Function.from_name(APP_NAME, FUNCTION_NAME)``
and invoke ``trellis_generate.remote(image_bytes, resolution)``.

The function MUST return the raw GLB bytes. The controller writes them to
``{output_dir}/raw.glb`` so the rest of the 3D Asset Factory pipeline picks the
file up unchanged.
"""

from __future__ import annotations

import pathlib

import modal

# --- Configuration ----------------------------------------------------------

APP_NAME = "trellis2-inference"
FUNCTION_NAME = "trellis_generate"

# TODO: pick the smallest GPU class with enough VRAM for TRELLIS.2. A10G is
# usually the cheapest viable option; A100-80GB / H100 are faster.
GPU = "A10G"

# TODO: pin to the CUDA + Python versions that the TRELLIS.2 upstream tests
# against. Rebuilding the image is the slow part of iteration, so pinning here
# pays off.
BASE_IMAGE = "nvidia/cuda:12.4.1-cudnn-devel-ubuntu22.04"
PYTHON_VERSION = "3.11"

# TODO: replace with the upstream TRELLIS.2 repo URL and the install command
# that pulls in its dependencies. The block below is a placeholder and will not
# actually install a working TRELLIS.2 environment as-is.
TRELLIS_REPO_URL = "https://github.com/microsoft/TRELLIS.git"
TRELLIS_INSTALL_DIR = "/opt/trellis2"

# Per-call timeout. Cold starts plus inference for a single asset typically
# fit comfortably in 15 minutes; raise this if you target very high resolutions.
FUNCTION_TIMEOUT_SECONDS = 15 * 60

# --- Image build ------------------------------------------------------------

image = (
    modal.Image.from_registry(BASE_IMAGE, add_python=PYTHON_VERSION)
    .apt_install("git", "ffmpeg", "libgl1", "libglib2.0-0")
    # TODO: pin the full TRELLIS.2 dependency set. The exact list depends on
    # the upstream commit you target. Start from their requirements file.
    .pip_install(
        "torch==2.4.0",
        "torchvision==0.19.0",
        "numpy>=1.26",
        "pillow>=10.0",
        "trimesh>=4.4",
    )
    .run_commands(
        f"git clone {TRELLIS_REPO_URL} {TRELLIS_INSTALL_DIR}",
        # TODO: replace with the upstream's actual install command. Some
        # forks expose a `pip install -e .` target; others ship a setup.sh.
        f"pip install -e {TRELLIS_INSTALL_DIR}",
    )
)

# Persisted weights volume - mounted at /weights inside the container. Caching
# the downloaded TRELLIS.2 checkpoints here keeps cold starts cheap.
weights_volume = modal.Volume.from_name("trellis2-weights", create_if_missing=True)

# Optional secret holding HF_TOKEN if the upstream weights live behind a
# Hugging Face gated repo. Create with:
#   modal secret create huggingface HF_TOKEN=hf_your_token_here
# Remove this secret from the function decorator below if you do not need it.
secrets = [modal.Secret.from_name("huggingface")]

app = modal.App(APP_NAME)


@app.function(
    image=image,
    gpu=GPU,
    volumes={"/weights": weights_volume},
    secrets=secrets,
    timeout=FUNCTION_TIMEOUT_SECONDS,
)
def trellis_generate(image_bytes: bytes, resolution: int = 1024) -> bytes:
    """Generate a GLB from a concept image using TRELLIS.2.

    Inputs:
        image_bytes: Raw bytes of the concept PNG / JPEG generated locally.
        resolution: Hint for the output resolution. Upstream TRELLIS.2 may
            interpret this differently across versions; keep it advisory.

    Returns:
        The GLB file as raw bytes. The controller writes them to
        ``{output_dir}/raw.glb`` so the rest of the pipeline picks the file up
        unchanged.
    """
    import os
    import pathlib
    import tempfile

    if not isinstance(image_bytes, (bytes, bytearray)):
        raise TypeError(f"image_bytes must be bytes, got {type(image_bytes).__name__}")
    if not image_bytes:
        raise ValueError("image_bytes is empty")
    if not isinstance(resolution, int) or resolution <= 0:
        raise ValueError(f"resolution must be a positive integer, got {resolution!r}")

    work = pathlib.Path(tempfile.mkdtemp(prefix="trellis2_"))
    in_path = work / "concept.png"
    out_path = work / "raw.glb"
    in_path.write_bytes(bytes(image_bytes))

    # Point the upstream code at the volume-cached weights.
    os.environ.setdefault("TRELLIS_WEIGHTS", "/weights")
    os.environ.setdefault("HF_HOME", "/weights/hf-cache")

    # TODO: replace this block with the real TRELLIS.2 entrypoint for your
    # install. The import path and function signature below are placeholders.
    # Common shapes you may see upstream:
    #
    #     from trellis2.pipelines import ImageTo3DPipeline
    #     pipeline = ImageTo3DPipeline.from_pretrained("/weights/...")
    #     pipeline.run(str(in_path), str(out_path), resolution=resolution)
    #
    # or a CLI:
    #
    #     subprocess.run(
    #         ["python", "/opt/trellis2/run.py",
    #          "--image", str(in_path),
    #          "--output", str(out_path),
    #          "--resolution", str(resolution)],
    #         check=True,
    #     )
    from trellis2.inference import image_to_glb  # type: ignore[import-not-found]

    image_to_glb(str(in_path), str(out_path), resolution=resolution)

    if not out_path.exists() or out_path.stat().st_size == 0:
        raise RuntimeError(
            f"TRELLIS.2 did not produce a GLB at {out_path}; check the install + entrypoint."
        )

    return out_path.read_bytes()


@app.local_entrypoint()
def smoke(image_path: str, output_path: str = "raw.glb", resolution: int = 1024) -> None:
    """`modal run infra/modal_trellis.py::smoke --image-path concept.png`.

    Useful for isolating GPU-side bugs from controller-side bugs.
    """
    data = pathlib.Path(image_path).read_bytes()
    glb = trellis_generate.remote(data, resolution)
    pathlib.Path(output_path).write_bytes(glb)
    print(f"wrote {output_path} ({len(glb)} bytes)")
