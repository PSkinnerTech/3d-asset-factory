from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

import fast_simplification
import imageio.v3 as iio
import numpy as np
from fast_simplification import replay_simplification
from PIL import Image, ImageOps
from trimesh import Trimesh
from trimesh import load as load_mesh
from trimesh.visual import ColorVisuals

_MIN_SIMPLIFY_TRIANGLES = 50


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
    max_triangles: int | None = None,
) -> OptimizedAsset:
    optimize_dir.mkdir(parents=True, exist_ok=True)
    previews_dir.mkdir(parents=True, exist_ok=True)

    optimized_glb = optimize_dir / "asset.glb"
    _write_optimized_glb(raw_glb, optimized_glb, max_triangles=max_triangles)

    thumbnail = previews_dir / "thumbnail.png"
    with Image.open(concept_image) as source:
        image = ImageOps.contain(source.convert("RGB"), (512, 512), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (512, 512), color=(245, 245, 245))
    canvas.paste(image, ((512 - image.width) // 2, (512 - image.height) // 2))
    canvas.save(thumbnail)

    turntable = previews_dir / "turntable.webm"
    _write_turntable(canvas, turntable)

    return OptimizedAsset(optimized_glb=optimized_glb, thumbnail=thumbnail, turntable=turntable)


def _write_optimized_glb(raw_glb: Path, optimized_glb: Path, max_triangles: int | None) -> None:
    target_triangles = _target_triangle_count(max_triangles)
    if target_triangles is None:
        shutil.copy2(raw_glb, optimized_glb)
        return

    mesh = load_mesh(raw_glb, force="mesh")
    if not isinstance(mesh, Trimesh) or len(mesh.faces) <= target_triangles:
        shutil.copy2(raw_glb, optimized_glb)
        return

    simplified = _simplify_mesh(mesh, target_triangles)
    simplified.export(optimized_glb)


def _target_triangle_count(max_triangles: int | None) -> int | None:
    if max_triangles is None:
        return None
    return max(max_triangles, _MIN_SIMPLIFY_TRIANGLES)


def _simplify_mesh(mesh: Trimesh, target_triangles: int) -> Trimesh:
    points = np.asarray(mesh.vertices, dtype=np.float64)
    faces = np.asarray(mesh.faces, dtype=np.int32)
    source_colors = _vertex_colors_for_mesh(mesh)

    _points, _faces, collapses = fast_simplification.simplify(
        points,
        faces,
        target_count=target_triangles,
        return_collapses=True,
    )
    simplified_points, simplified_faces, mapping = replay_simplification(
        points.astype(np.float32),
        faces,
        collapses,
    )
    simplified = Trimesh(vertices=simplified_points, faces=simplified_faces, process=False)

    if source_colors is not None:
        simplified.visual = ColorVisuals(
            mesh=simplified,
            vertex_colors=_average_mapped_colors(source_colors, mapping, len(simplified.vertices)),
        )

    return simplified


def _vertex_colors_for_mesh(mesh: Trimesh) -> np.ndarray | None:
    colors = getattr(mesh.visual, "vertex_colors", None)
    if colors is not None:
        vertex_colors = np.asarray(colors)
        if vertex_colors.shape == (len(mesh.vertices), 4):
            return vertex_colors.astype(np.float64)

    texture_colors = _sample_texture_vertex_colors(mesh)
    if texture_colors is not None:
        return texture_colors

    material = getattr(mesh.visual, "material", None)
    main_color = getattr(material, "main_color", None)
    if main_color is None:
        return None

    color = np.asarray(main_color)
    if color.shape != (4,):
        return None
    return np.repeat(color[np.newaxis, :], len(mesh.vertices), axis=0).astype(np.float64)


def _sample_texture_vertex_colors(mesh: Trimesh) -> np.ndarray | None:
    uv = getattr(mesh.visual, "uv", None)
    if uv is None:
        return None

    uv_array = np.asarray(uv)
    if uv_array.shape != (len(mesh.vertices), 2):
        return None

    material = getattr(mesh.visual, "material", None)
    texture = getattr(material, "baseColorTexture", None) or getattr(material, "image", None)
    if texture is None:
        return None

    image = np.asarray(texture.convert("RGBA"))
    height, width = image.shape[:2]
    clamped_uv = np.clip(uv_array, 0.0, 1.0)
    x = np.minimum(np.rint(clamped_uv[:, 0] * (width - 1)).astype(np.int64), width - 1)
    y = np.minimum(np.rint((1.0 - clamped_uv[:, 1]) * (height - 1)).astype(np.int64), height - 1)
    return image[y, x].astype(np.float64)


def _average_mapped_colors(
    source_colors: np.ndarray,
    mapping: np.ndarray,
    vertex_count: int,
) -> np.ndarray:
    color_sums = np.zeros((vertex_count, 4), dtype=np.float64)
    color_counts = np.zeros(vertex_count, dtype=np.int64)
    np.add.at(color_sums, mapping, source_colors)
    np.add.at(color_counts, mapping, 1)
    averaged = np.divide(
        color_sums,
        color_counts[:, np.newaxis],
        out=np.zeros_like(color_sums),
        where=color_counts[:, np.newaxis] > 0,
    )
    return np.clip(np.rint(averaged), 0, 255).astype(np.uint8)


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
