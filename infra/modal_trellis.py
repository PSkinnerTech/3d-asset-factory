"""Modal app that exposes microsoft/TRELLIS.2 image-to-3D as a remote function.

The local controller-side runner at ``scripts/modal_trellis_runner.py`` calls
``trellis_generate.remote(image_bytes, resolution)`` on the deployed Modal
function and writes the returned GLB bytes to ``{output_dir}/raw.glb``.

Deploy with::

    modal deploy infra/modal_trellis.py

The function MUST return raw GLB bytes. The controller validates the ``glTF``
magic header before persisting.

Upstream pinned: https://github.com/microsoft/TRELLIS.2 (TRELLIS.2-4B weights
at https://huggingface.co/microsoft/TRELLIS.2-4B). Per the upstream README the
project targets PyTorch 2.6.0 on CUDA 12.4, requires a Linux NVIDIA GPU with at
least 24 GB VRAM (verified on A100/H100), and installs through ``setup.sh``
rather than a ``requirements.txt``.
"""

from __future__ import annotations

import pathlib

import modal

# --- Configuration ----------------------------------------------------------

APP_NAME = "trellis2-inference"
FUNCTION_NAME = "trellis_generate"

# Default GPU. TRELLIS.2 README states A100/H100 are the verified configurations
# and that the 4B model needs >= 24 GB VRAM. A10G has 24 GB and works for the
# 512-1024 voxel range but is slower; bump to "A100-80GB" or "H100" for the
# 1536^3 resolution path. Override at deploy time by editing this constant.
GPU = "A100-80GB"

# CUDA 12.4 + Python 3.10 to match upstream conda env exactly. setup.sh creates
# a `trellis2` env on Python 3.10 with PyTorch 2.6.0 + CUDA 12.4 wheels.
BASE_IMAGE = "nvidia/cuda:12.4.1-cudnn-devel-ubuntu22.04"
PYTHON_VERSION = "3.10"

# Pinned upstream. Use a commit SHA in production once you've validated one.
TRELLIS_REPO_URL = "https://github.com/microsoft/TRELLIS.2.git"
TRELLIS_INSTALL_DIR = "/opt/trellis2"
TRELLIS_MODEL_ID = "microsoft/TRELLIS.2-4B"

# Per-call timeout. Per the upstream README on an H100:
#   512^3  ~3s, 1024^3 ~17s, 1536^3 ~60s (inference only).
# Cold start adds checkpoint download (~16 GB) on first invocation per worker;
# the volume cache keeps subsequent starts fast. 20 minutes covers cold start
# and the worst-case 1536^3 path with margin.
FUNCTION_TIMEOUT_SECONDS = 20 * 60

# --- Image build ------------------------------------------------------------
#
# We deliberately do not run TRELLIS.2's ``setup.sh --new-env`` because that
# spins up a conda environment and we are already inside a controlled image.
# Instead we replicate what ``setup.sh --basic --flash-attn --nvdiffrast
# --nvdiffrec --cumesh --o-voxel --flexgemm`` does, against the system Python
# Modal provides via ``add_python``.

image = (
    modal.Image.from_registry(BASE_IMAGE, add_python=PYTHON_VERSION)
    .apt_install(
        "git",
        "build-essential",
        "ninja-build",
        "libjpeg-dev",
        "libgl1",
        "libglib2.0-0",
        "ffmpeg",
    )
    # Pinned to the CUDA 12.4 wheels TRELLIS.2's setup.sh selects on NVIDIA.
    .pip_install(
        "torch==2.6.0",
        "torchvision==0.21.0",
        extra_index_url="https://download.pytorch.org/whl/cu124",
    )
    # The "--basic" set from upstream setup.sh, with pillow-simd dropped (it
    # requires libjpeg-turbo headers and conflicts with system pillow on slim
    # images; standard pillow is fine for our single image-load path).
    .pip_install(
        "imageio>=2.35",
        "imageio-ffmpeg>=0.5",
        "tqdm",
        "easydict",
        "opencv-python-headless",
        "ninja",
        "trimesh>=4.4",
        "transformers",
        "tensorboard",
        "pandas",
        "lpips",
        "zstandard",
        "kornia",
        "timm",
        "huggingface_hub",
        # utils3d pinned to the same commit setup.sh uses upstream.
        "git+https://github.com/EasternJournalist/utils3d.git@9a4eb15e4021b67b12c460c7057d642626897ec8",
    )
    # flash-attn must compile against the installed torch; --no-build-isolation
    # ensures it sees the torch we just installed. Its setup metadata imports
    # psutil under no-build-isolation, so psutil must exist before this layer.
    .pip_install("psutil")
    .pip_install("flash-attn==2.7.3", extra_options="--no-build-isolation")
    .env(
        {
            # Modal image builds do not expose a GPU, so PyTorch cannot infer
            # extension target architectures. Cover the Modal GPU classes we
            # expect to use: A100, A10, L4/Ada, and H100.
            "TORCH_CUDA_ARCH_LIST": "8.0;8.6;8.9;9.0",
            "CC": "/usr/bin/gcc",
            "CXX": "/usr/bin/g++",
        }
    )
    # Clone TRELLIS.2 with submodules; o-voxel ships inside the repo and is
    # pip-installed below.
    .run_commands(
        f"git clone --recursive {TRELLIS_REPO_URL} {TRELLIS_INSTALL_DIR}",
        # nvdiffrast / nvdiffrec / CuMesh / FlexGEMM — the CUDA extension set
        # from setup.sh. Each needs --no-build-isolation so it links against
        # the torch we already installed.
        "git clone --branch v0.4.0 https://github.com/NVlabs/nvdiffrast.git /tmp/nvdiffrast"
        " && pip install --no-build-isolation /tmp/nvdiffrast",
        "git clone --branch renderutils https://github.com/JeffreyXiang/nvdiffrec.git"
        " /tmp/nvdiffrec && pip install --no-build-isolation /tmp/nvdiffrec",
        "git clone --recursive https://github.com/JeffreyXiang/CuMesh.git /tmp/cumesh"
        " && pip install --no-build-isolation /tmp/cumesh",
        "git clone --recursive https://github.com/JeffreyXiang/FlexGEMM.git /tmp/flexgemm"
        " && pip install --no-build-isolation /tmp/flexgemm",
        f"pip install --no-build-isolation {TRELLIS_INSTALL_DIR}/o-voxel",
    )
    # TRELLIS.2's DINOv3 feature extractor currently reaches into
    # DINOv3ViTModel.layer. Transformers 5.x moved that surface; 4.57.x still
    # matches the upstream TRELLIS.2 implementation.
    .pip_install("transformers==4.57.6", "huggingface_hub>=0.34,<1.0")
    .env(
        {
            # OpenEXR support is required by trellis2.utils.render_utils, even
            # though we do not render videos in this entrypoint, because the
            # import chain pulls it in.
            "OPENCV_IO_ENABLE_OPENEXR": "1",
            "PYTORCH_CUDA_ALLOC_CONF": "expandable_segments:True",
            # Send the HF download cache to the persisted volume so we only
            # pay the ~16 GB download once per workspace.
            "HF_HOME": "/weights/hf-cache",
            "HUGGINGFACE_HUB_CACHE": "/weights/hf-cache",
            "CUDA_HOME": "/usr/local/cuda",
            "PYTHONPATH": TRELLIS_INSTALL_DIR,
        }
    )
)

# Persisted weights volume — mounted at /weights inside the container. Caches
# the Hugging Face checkpoint and any other large model artifacts.
weights_volume = modal.Volume.from_name("trellis2-weights", create_if_missing=True)

# Hugging Face secret. Required if your workspace has not accepted the model
# license yet, or if you want to pull a gated revision. Create with:
#   modal secret create huggingface HF_TOKEN=hf_your_token_here
# The TRELLIS.2-4B repo is currently public, so this is optional but
# recommended to avoid surprises if upstream gates a future revision.
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
    """Generate a GLB from a concept image using microsoft/TRELLIS.2-4B.

    Inputs:
        image_bytes: Raw bytes of the concept PNG / JPEG generated locally.
        resolution: Advisory hint kept for parity with ``TRELLIS2_COMMAND``.
            The upstream pipeline's ``run`` method does not currently take a
            resolution argument; the value is validated and logged. Plug it
            into ``pipeline.run`` here if a future TRELLIS.2 revision adds
            the parameter.

    Returns:
        The GLB file as raw bytes. The controller writes them to
        ``{output_dir}/raw.glb``.
    """
    import io
    import os
    import pathlib
    import tempfile

    if not isinstance(image_bytes, (bytes, bytearray)):
        raise TypeError(f"image_bytes must be bytes, got {type(image_bytes).__name__}")
    if not image_bytes:
        raise ValueError("image_bytes is empty")
    if not isinstance(resolution, int) or resolution <= 0:
        raise ValueError(f"resolution must be a positive integer, got {resolution!r}")

    # These must be set before importing cv2 / trellis2.* because cv2 freezes
    # OpenEXR support at import time. They are also baked into the image via
    # .env(...) but we re-export defensively for `modal run` invocations.
    os.environ.setdefault("OPENCV_IO_ENABLE_OPENEXR", "1")
    os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
    os.environ.setdefault("HF_HOME", "/weights/hf-cache")
    os.environ.setdefault("HUGGINGFACE_HUB_CACHE", "/weights/hf-cache")

    import o_voxel  # type: ignore[import-not-found]
    from PIL import Image
    from trellis2.pipelines import Trellis2ImageTo3DPipeline  # type: ignore[import-not-found]

    work = pathlib.Path(tempfile.mkdtemp(prefix="trellis2_"))
    out_path = work / "raw.glb"

    pil_image = Image.open(io.BytesIO(bytes(image_bytes))).convert("RGBA")

    pipeline = Trellis2ImageTo3DPipeline.from_pretrained(TRELLIS_MODEL_ID)
    pipeline.cuda()

    # Upstream example.py: ``mesh = pipeline.run(image)[0]; mesh.simplify(...)``
    mesh = pipeline.run(pil_image)[0]
    # nvdiffrast face limit per upstream comment in example.py.
    mesh.simplify(16777216)

    glb = o_voxel.postprocess.to_glb(
        vertices=mesh.vertices,
        faces=mesh.faces,
        attr_volume=mesh.attrs,
        coords=mesh.coords,
        attr_layout=mesh.layout,
        voxel_size=mesh.voxel_size,
        aabb=[[-0.5, -0.5, -0.5], [0.5, 0.5, 0.5]],
        decimation_target=1_000_000,
        texture_size=4096,
        remesh=True,
        remesh_band=1,
        remesh_project=0,
        verbose=True,
    )
    glb.export(str(out_path), extension_webp=True)

    if not out_path.exists() or out_path.stat().st_size == 0:
        raise RuntimeError(
            f"TRELLIS.2 did not produce a GLB at {out_path}; check the upstream pipeline."
        )

    # Persist any newly cached HF artifacts so the next cold start reuses them.
    weights_volume.commit()

    return out_path.read_bytes()


@app.local_entrypoint()
def smoke(image_path: str, output_path: str = "raw.glb", resolution: int = 1024) -> None:
    """``modal run infra/modal_trellis.py::smoke --image-path concept.png``.

    Useful for isolating GPU-side bugs from controller-side bugs.
    """
    data = pathlib.Path(image_path).read_bytes()
    glb = trellis_generate.remote(data, resolution)
    pathlib.Path(output_path).write_bytes(glb)
    print(f"wrote {output_path} ({len(glb)} bytes)")
