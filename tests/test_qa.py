from pathlib import Path

import trimesh

from asset_factory.models import AssetSpec, ExportProfile, QaThresholds, ScienceSubject, StyleMode
from asset_factory.qa import run_qa


def make_spec(max_triangles: int = 1000, max_glb_mb: int = 10) -> AssetSpec:
    return AssetSpec(
        id="qa_asset",
        subject=ScienceSubject.PHYSICS,
        object="cube",
        grade_band="3-5",
        style=StyleMode.CONCEPTUAL,
        learning_goal="Inspect a cube.",
        exports=[ExportProfile.WEB],
        qa=QaThresholds(max_triangles=max_triangles, max_glb_mb=max_glb_mb),
    )


def write_box(path: Path) -> None:
    mesh = trimesh.creation.box(extents=(1, 1, 1))
    material = trimesh.visual.material.PBRMaterial(baseColorFactor=[0.78, 0.47, 0.31, 1.0])
    mesh.visual = trimesh.visual.TextureVisuals(material=material)
    mesh.export(path)


def write_box_without_material(path: Path) -> None:
    mesh = trimesh.creation.box(extents=(1, 1, 1))
    mesh.visual = None
    mesh.export(path)


def test_qa_passes_valid_glb(tmp_path: Path):
    glb_path = tmp_path / "asset.glb"
    glb_path.parent.mkdir(parents=True, exist_ok=True)
    write_box(glb_path)

    report = run_qa(make_spec(), glb_path)

    assert report.passed is True
    assert report.blocking_failures == []
    assert report.metrics["triangles"] == 12
    assert report.metrics["file_size_bytes"] > 0


def test_qa_blocks_missing_glb(tmp_path: Path):
    report = run_qa(make_spec(), tmp_path / "missing.glb")

    assert report.passed is False
    assert "GLB file is missing" in report.blocking_failures


def test_qa_blocks_triangle_budget(tmp_path: Path):
    glb_path = tmp_path / "asset.glb"
    write_box(glb_path)

    report = run_qa(make_spec(max_triangles=1), glb_path)

    assert report.passed is False
    assert "Triangle count 12 exceeds max_triangles 1" in report.blocking_failures


def test_qa_blocks_missing_material_and_base_color(tmp_path: Path):
    glb_path = tmp_path / "asset.glb"
    write_box_without_material(glb_path)

    report = run_qa(make_spec(), glb_path)

    assert report.passed is False
    assert "Required material data is missing" in report.blocking_failures
    assert "Required base color data is missing" in report.blocking_failures
    assert report.metrics["triangles"] == 12
    assert report.metrics["file_size_bytes"] > 0
