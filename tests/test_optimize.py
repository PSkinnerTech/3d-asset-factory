from pathlib import Path

import trimesh
from PIL import Image

from asset_factory.optimize import optimize_asset


def write_box(path: Path) -> None:
    mesh = trimesh.creation.box(extents=(1, 1, 1))
    mesh.visual = trimesh.visual.ColorVisuals(mesh, vertex_colors=[120, 160, 220, 255])
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
