import json
from pathlib import Path

import trimesh

from asset_factory.stl import export_stl


def write_box_glb(path: Path) -> None:
    mesh = trimesh.creation.box(extents=(1, 1, 1))
    path.parent.mkdir(parents=True, exist_ok=True)
    mesh.export(path)


def write_two_boxes_glb(path: Path) -> None:
    first_box = trimesh.creation.box(extents=(1, 1, 1))
    second_box = trimesh.creation.box(extents=(1, 1, 1))
    second_box.apply_translation((3, 0, 0))
    mesh = trimesh.util.concatenate([first_box, second_box])
    path.parent.mkdir(parents=True, exist_ok=True)
    mesh.export(path)


def write_plane_glb(path: Path) -> None:
    mesh = trimesh.Trimesh(
        vertices=[
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [1.0, 1.0, 0.0],
            [0.0, 1.0, 0.0],
        ],
        faces=[[0, 1, 2], [0, 2, 3]],
        process=False,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    mesh.export(path)


def test_export_stl_writes_binary_stl_and_report(tmp_path: Path):
    source_glb = tmp_path / "optimize" / "asset.glb"
    output_stl = tmp_path / "exports" / "web" / "asset.stl"
    report_path = tmp_path / "exports" / "web" / "stl_report.json"
    write_box_glb(source_glb)

    report = export_stl(source_glb, output_stl, report_path)

    report_json = json.loads(report_path.read_text(encoding="utf-8"))
    assert output_stl.is_file()
    assert output_stl.stat().st_size > 0
    assert report.exported is True
    assert report.output_stl == str(output_stl)
    assert report_json["exported"] is True
    assert report_json["triangle_count"] == 12
    assert report_json["body_count"] == 1
    assert report_json["is_watertight"] is True
    assert report_json["is_volume"] is True
    assert any("geometry-only" in warning for warning in report_json["warnings"])


def test_export_stl_warns_for_non_watertight_mesh_without_failing(tmp_path: Path):
    source_glb = tmp_path / "optimize" / "asset.glb"
    output_stl = tmp_path / "exports" / "web" / "asset.stl"
    report_path = tmp_path / "exports" / "web" / "stl_report.json"
    write_plane_glb(source_glb)

    report = export_stl(source_glb, output_stl, report_path)

    assert output_stl.is_file()
    assert report.exported is True
    assert report.is_watertight is False
    assert report.is_volume is False
    assert any("not watertight" in warning for warning in report.warnings)
    assert any("not a valid volume" in warning for warning in report.warnings)


def test_export_stl_reports_disconnected_bodies(tmp_path: Path):
    source_glb = tmp_path / "optimize" / "asset.glb"
    output_stl = tmp_path / "exports" / "web" / "asset.stl"
    report_path = tmp_path / "exports" / "web" / "stl_report.json"
    write_two_boxes_glb(source_glb)

    report = export_stl(source_glb, output_stl, report_path)

    assert output_stl.is_file()
    assert report.body_count == 2
    assert any("disconnected bodies" in warning for warning in report.warnings)
