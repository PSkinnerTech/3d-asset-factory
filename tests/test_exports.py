import json
import shutil
from pathlib import Path

import pytest
import trimesh

from asset_factory.exports import _replace_export_package, export_profiles, import_notes
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


def test_replace_export_package_restores_existing_files_when_copy_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    export_dir = tmp_path / "exports" / "web"
    export_dir.mkdir(parents=True)
    existing_files = {
        "asset.glb": b"old glb",
        "thumbnail.png": b"old png",
        "turntable.webm": b"old webm",
        "qa.json": b'{"old": true}',
        "IMPORT_NOTES.md": b"old notes",
    }
    for name, contents in existing_files.items():
        (export_dir / name).write_bytes(contents)
    (export_dir / "manifest.json").write_text('{"keep": true}\n', encoding="utf-8")

    staging_dir = tmp_path / "staging"
    staging_dir.mkdir()
    for name in existing_files:
        (staging_dir / name).write_bytes(f"new {name}".encode())

    original_copy2 = shutil.copy2
    final_copy_count = 0

    def fail_after_first_copy(src: Path, dst: Path):
        nonlocal final_copy_count
        if Path(dst).parent == export_dir:
            final_copy_count += 1
            if final_copy_count == 2:
                raise OSError("simulated final copy failure")
        return original_copy2(src, dst)

    monkeypatch.setattr(shutil, "copy2", fail_after_first_copy)

    with pytest.raises(OSError, match="simulated final copy failure"):
        _replace_export_package(staging_dir, export_dir, [ExportFormat.GLB])

    for name, contents in existing_files.items():
        assert (export_dir / name).read_bytes() == contents
    assert (export_dir / "manifest.json").read_text(encoding="utf-8") == '{"keep": true}\n'


def test_replace_export_package_restores_existing_files_when_stale_removal_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    export_dir = tmp_path / "exports" / "web"
    export_dir.mkdir(parents=True)
    existing_files = {
        "asset.glb": b"old glb",
        "thumbnail.png": b"old png",
        "turntable.webm": b"old webm",
        "qa.json": b'{"old": true}',
        "IMPORT_NOTES.md": b"old notes",
    }
    for name, contents in existing_files.items():
        (export_dir / name).write_bytes(contents)

    staging_dir = tmp_path / "staging"
    staging_dir.mkdir()
    staged_files = {
        "asset.stl": b"new stl",
        "stl_report.json": b'{"new": true}',
        "thumbnail.png": b"new png",
        "turntable.webm": b"new webm",
        "qa.json": b'{"new": true}',
        "IMPORT_NOTES.md": b"new notes",
    }
    for name, contents in staged_files.items():
        (staging_dir / name).write_bytes(contents)

    original_unlink = Path.unlink

    def fail_removing_stale_glb(self: Path, *args, **kwargs):
        if self == export_dir / "asset.glb":
            raise OSError("simulated stale removal failure")
        return original_unlink(self, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", fail_removing_stale_glb)

    with pytest.raises(OSError, match="simulated stale removal failure"):
        _replace_export_package(staging_dir, export_dir, [ExportFormat.STL])

    for name, contents in existing_files.items():
        assert (export_dir / name).read_bytes() == contents
    assert not (export_dir / "asset.stl").exists()
    assert not (export_dir / "stl_report.json").exists()


def test_replace_export_package_continues_rollback_after_restore_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    export_dir = tmp_path / "exports" / "web"
    export_dir.mkdir(parents=True)
    existing_files = {
        "asset.glb": b"old glb",
        "thumbnail.png": b"old png",
        "turntable.webm": b"old webm",
        "qa.json": b'{"old": true}',
        "IMPORT_NOTES.md": b"old notes",
    }
    for name, contents in existing_files.items():
        (export_dir / name).write_bytes(contents)

    staging_dir = tmp_path / "staging"
    staging_dir.mkdir()
    staged_files = {
        "asset.stl": b"new stl",
        "stl_report.json": b'{"new": true}',
        "thumbnail.png": b"new png",
        "turntable.webm": b"new webm",
        "qa.json": b'{"new": true}',
        "IMPORT_NOTES.md": b"new notes",
    }
    for name, contents in staged_files.items():
        (staging_dir / name).write_bytes(contents)

    original_replace = Path.replace
    original_unlink = Path.unlink

    def fail_thumbnail_restore(self: Path, target: Path):
        if self.name == "thumbnail.png" and Path(target) == export_dir / "thumbnail.png":
            raise OSError("simulated thumbnail restore failure")
        return original_replace(self, target)

    def fail_removing_stale_glb(self: Path, *args, **kwargs):
        if self == export_dir / "asset.glb":
            raise OSError("simulated stale removal failure")
        return original_unlink(self, *args, **kwargs)

    monkeypatch.setattr(Path, "replace", fail_thumbnail_restore)
    monkeypatch.setattr(Path, "unlink", fail_removing_stale_glb)

    with pytest.raises(OSError, match="simulated stale removal failure") as exc_info:
        _replace_export_package(staging_dir, export_dir, [ExportFormat.STL])

    notes = getattr(exc_info.value, "__notes__", [])
    assert any("simulated thumbnail restore failure" in note for note in notes)
    assert (export_dir / "asset.glb").read_bytes() == existing_files["asset.glb"]
    assert (export_dir / "turntable.webm").read_bytes() == existing_files["turntable.webm"]
    assert (export_dir / "qa.json").read_bytes() == existing_files["qa.json"]
    assert (export_dir / "IMPORT_NOTES.md").read_bytes() == existing_files["IMPORT_NOTES.md"]
    assert (export_dir / "thumbnail.png").read_bytes() == staged_files["thumbnail.png"]
    assert not (export_dir / "asset.stl").exists()
    assert not (export_dir / "stl_report.json").exists()
