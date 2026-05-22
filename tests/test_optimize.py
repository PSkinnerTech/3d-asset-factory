from pathlib import Path

import numpy as np
import trimesh
from PIL import Image

from asset_factory.glb import inspect_glb
from asset_factory.optimize import optimize_asset


def write_box(path: Path) -> None:
    mesh = trimesh.creation.box(extents=(1, 1, 1))
    mesh.visual = trimesh.visual.ColorVisuals(mesh, vertex_colors=[120, 160, 220, 255])
    mesh.export(path)


def write_textured_grid(path: Path, subdivisions: int = 32) -> None:
    vertices = []
    uvs = []
    for y in range(subdivisions + 1):
        for x in range(subdivisions + 1):
            vertices.append([x / subdivisions, y / subdivisions, 0.0])
            uvs.append([x / subdivisions, y / subdivisions])

    faces = []
    row_width = subdivisions + 1
    for y in range(subdivisions):
        for x in range(subdivisions):
            top_left = y * row_width + x
            top_right = top_left + 1
            bottom_left = top_left + row_width
            bottom_right = bottom_left + 1
            faces.append([top_left, top_right, bottom_right])
            faces.append([top_left, bottom_right, bottom_left])

    mesh = trimesh.Trimesh(vertices=np.array(vertices), faces=np.array(faces), process=False)
    texture = Image.new("RGBA", (8, 8), color=(40, 180, 90, 255))
    mesh.visual = trimesh.visual.TextureVisuals(uv=np.array(uvs), image=texture)
    mesh.export(path)


def test_optimize_copies_glb_and_generates_previews(tmp_path: Path):
    raw_glb = tmp_path / "trellis" / "raw.glb"
    concept = tmp_path / "image" / "concept.png"
    optimized_dir = tmp_path / "optimize"
    previews_dir = tmp_path / "previews"
    raw_glb.parent.mkdir(parents=True)
    concept.parent.mkdir(parents=True)
    write_box(raw_glb)
    Image.new("RGB", (64, 64), color=(20, 70, 120)).save(concept)

    result = optimize_asset(raw_glb, concept, optimized_dir, previews_dir)

    assert result.optimized_glb == optimized_dir / "asset.glb"
    assert result.thumbnail == previews_dir / "thumbnail.png"
    assert result.turntable == previews_dir / "turntable.webm"
    assert result.optimized_glb.read_bytes()[:4] == b"glTF"
    assert Image.open(result.thumbnail).size == (512, 512)
    assert result.turntable.stat().st_size > 0


def test_optimize_simplifies_textured_mesh_to_triangle_budget(tmp_path: Path):
    raw_glb = tmp_path / "trellis" / "raw.glb"
    concept = tmp_path / "image" / "concept.png"
    optimized_dir = tmp_path / "optimize"
    previews_dir = tmp_path / "previews"
    raw_glb.parent.mkdir(parents=True)
    concept.parent.mkdir(parents=True)
    write_textured_grid(raw_glb)
    Image.new("RGB", (64, 64), color=(20, 70, 120)).save(concept)

    result = optimize_asset(
        raw_glb,
        concept,
        optimized_dir,
        previews_dir,
        max_triangles=500,
    )
    metrics = inspect_glb(result.optimized_glb)

    assert metrics.triangles <= 500
    assert metrics.has_base_color is True
    assert metrics.file_size_bytes < raw_glb.stat().st_size
