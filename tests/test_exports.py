import json
from pathlib import Path

import pytest
import trimesh

from asset_factory.exports import export_profiles, import_notes
from asset_factory.models import ExportFormat, ExportProfile


def write_artifacts(run_dir: Path) -> None:
    (run_dir / "optimize").mkdir(parents=True)
    (run_dir / "previews").mkdir(parents=True)
    (run_dir / "reports").mkdir(parents=True)
    (run_dir / "optimize" / "asset.glb").write_bytes(b"glTF-demo")
    (run_dir / "previews" / "thumbnail.png").write_bytes(b"png")
    (run_dir / "previews" / "turntable.webm").write_bytes(b"webm")
    (run_dir / "reports" / "qa.json").write_text("{}", encoding="utf-8")
    (run_dir / "manifest.json").write_text(
        json.dumps({"asset": {"id": "demo"}, "files": {"optimized_glb": "root"}}),
        encoding="utf-8",
    )


def write_mesh_artifacts(run_dir: Path) -> None:
    write_artifacts(run_dir)
    mesh = trimesh.creation.box(extents=(1, 1, 1))
    mesh.export(run_dir / "optimize" / "asset.glb")


def test_exports_glb_only_by_default(tmp_path: Path):
    run_dir = tmp_path / "runs" / "demo" / "20260520T120000Z"
    write_artifacts(run_dir)

    results = export_profiles(run_dir, [ExportProfile.WEB])

    export_dir = results[ExportProfile.WEB]
    assert (export_dir / "asset.glb").read_bytes() == b"glTF-demo"
    assert not (export_dir / "asset.stl").exists()
    assert not (export_dir / "stl_report.json").exists()
    assert (export_dir / "thumbnail.png").exists()
    assert (export_dir / "turntable.webm").exists()
    assert (export_dir / "qa.json").exists()
    notes = (export_dir / "IMPORT_NOTES.md").read_text(encoding="utf-8")
    assert "Use asset.glb" in notes


def test_exports_stl_only_package(tmp_path: Path):
    run_dir = tmp_path / "runs" / "demo" / "20260520T120000Z"
    write_mesh_artifacts(run_dir)

    results = export_profiles(run_dir, [ExportProfile.WEB], formats=[ExportFormat.STL])

    export_dir = results[ExportProfile.WEB]
    assert not (export_dir / "asset.glb").exists()
    assert (export_dir / "asset.stl").is_file()
    assert (export_dir / "stl_report.json").is_file()
    assert (export_dir / "thumbnail.png").exists()
    assert (export_dir / "turntable.webm").exists()
    assert (export_dir / "qa.json").exists()
    notes = (export_dir / "IMPORT_NOTES.md").read_text(encoding="utf-8")
    assert "geometry-only" in notes
    assert "3D printing" in notes


def test_exports_glb_and_stl_package(tmp_path: Path):
    run_dir = tmp_path / "runs" / "demo" / "20260520T120000Z"
    write_mesh_artifacts(run_dir)

    results = export_profiles(
        run_dir,
        [ExportProfile.WEB, ExportProfile.UNITY, ExportProfile.UNREAL],
        formats=[ExportFormat.GLB, ExportFormat.STL],
    )

    assert set(results) == {ExportProfile.WEB, ExportProfile.UNITY, ExportProfile.UNREAL}
    for profile, export_dir in results.items():
        assert (export_dir / "asset.glb").exists()
        assert (export_dir / "asset.stl").exists()
        assert (export_dir / "stl_report.json").exists()
        assert not (export_dir / "manifest.json").exists()
        notes = (export_dir / "IMPORT_NOTES.md").read_text(encoding="utf-8")
        assert profile.value in notes
        assert "asset.glb" in notes
        assert "asset.stl" in notes


def test_exports_rejects_explicit_empty_formats(tmp_path: Path):
    run_dir = tmp_path / "runs" / "demo" / "20260520T120000Z"
    write_artifacts(run_dir)

    with pytest.raises(ValueError, match="at least one export format"):
        export_profiles(run_dir, [ExportProfile.WEB], formats=[])


def test_import_notes_rejects_explicit_empty_formats():
    with pytest.raises(ValueError, match="at least one export format"):
        import_notes(ExportProfile.WEB, formats=[])


def test_import_notes_use_profile_specific_glb_guidance():
    web_notes = import_notes(ExportProfile.WEB, [ExportFormat.GLB])
    unity_notes = import_notes(ExportProfile.UNITY, [ExportFormat.GLB])
    unreal_notes = import_notes(ExportProfile.UNREAL, [ExportFormat.GLB])

    assert "Three.js" in web_notes
    assert "React Three Fiber" in web_notes
    assert "Babylon.js" in web_notes
    assert "Unity GLTF importer" in unity_notes
    assert "Unreal" in unreal_notes
    assert "glTF importer" in unreal_notes
    assert "plugin" in unreal_notes


def test_import_notes_keep_stl_guidance_when_selected():
    notes = import_notes(ExportProfile.UNITY, [ExportFormat.GLB, ExportFormat.STL])

    assert "Unity GLTF importer" in notes
    assert "geometry-only" in notes
    assert "Review stl_report.json" in notes


def test_exports_remove_stale_format_artifacts(tmp_path: Path):
    run_dir = tmp_path / "runs" / "demo" / "20260520T120000Z"
    write_mesh_artifacts(run_dir)

    export_profiles(
        run_dir,
        [ExportProfile.WEB],
        formats=[ExportFormat.GLB, ExportFormat.STL],
    )
    export_dir = run_dir / "exports" / ExportProfile.WEB.value
    assert (export_dir / "asset.glb").exists()
    assert (export_dir / "asset.stl").exists()
    assert (export_dir / "stl_report.json").exists()

    export_profiles(run_dir, [ExportProfile.WEB], formats=[ExportFormat.STL])
    assert not (export_dir / "asset.glb").exists()
    assert (export_dir / "asset.stl").exists()
    assert (export_dir / "stl_report.json").exists()

    export_profiles(run_dir, [ExportProfile.WEB], formats=[ExportFormat.GLB])
    assert (export_dir / "asset.glb").exists()
    assert not (export_dir / "asset.stl").exists()
    assert not (export_dir / "stl_report.json").exists()
