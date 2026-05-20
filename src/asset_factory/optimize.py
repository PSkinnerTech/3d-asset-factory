from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

import imageio.v3 as iio
import numpy as np
from PIL import Image, ImageOps


@dataclass(frozen=True)
class OptimizedAsset:
    optimized_glb: Path
    thumbnail: Path
    turntable: Path


def optimize_asset(
    raw_glb: Path,
    concept_image: Path,
    optimize_dir: Path,
    previews_dir: Path,
) -> OptimizedAsset:
    optimize_dir.mkdir(parents=True, exist_ok=True)
    previews_dir.mkdir(parents=True, exist_ok=True)

    optimized_glb = optimize_dir / "asset.glb"
    shutil.copy2(raw_glb, optimized_glb)

    thumbnail = previews_dir / "thumbnail.png"
    with Image.open(concept_image) as source:
        image = ImageOps.contain(source.convert("RGB"), (512, 512), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (512, 512), color=(245, 245, 245))
    canvas.paste(image, ((512 - image.width) // 2, (512 - image.height) // 2))
    canvas.save(thumbnail)

    turntable = previews_dir / "turntable.webm"
    _write_turntable(canvas, turntable)

    return OptimizedAsset(optimized_glb=optimized_glb, thumbnail=thumbnail, turntable=turntable)


def _write_turntable(canvas: Image.Image, turntable: Path) -> None:
    base = np.asarray(canvas)
    shifts = (0, 16, 32, 48, 64, 48, 32, 16)
    frames = np.stack([np.roll(base, shift=shift, axis=1) for shift in shifts])

    try:
        iio.imwrite(turntable, frames, fps=8, codec="libvpx-vp9")
    except Exception:
        pil_frames = [Image.fromarray(frame) for frame in frames]
        pil_frames[0].save(
            turntable,
            format="GIF",
            save_all=True,
            append_images=pil_frames[1:],
            duration=125,
            loop=0,
        )
