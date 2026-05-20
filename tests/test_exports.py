import json
from pathlib import Path

from asset_factory.exports import export_profiles
from asset_factory.models import ExportProfile


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


def test_exports_web_unity_and_unreal_profiles(tmp_path: Path):
    run_dir = tmp_path / "runs" / "demo" / "20260520T120000Z"
    write_artifacts(run_dir)

    results = export_profiles(
        run_dir, [ExportProfile.WEB, ExportProfile.UNITY, ExportProfile.UNREAL]
    )

    assert set(results) == {ExportProfile.WEB, ExportProfile.UNITY, ExportProfile.UNREAL}
    for profile, export_dir in results.items():
        assert (export_dir / "asset.glb").read_bytes() == b"glTF-demo"
        assert not (export_dir / "manifest.json").exists()
        assert (export_dir / "thumbnail.png").exists()
        assert (export_dir / "turntable.webm").exists()
        assert (export_dir / "qa.json").exists()
        notes = (export_dir / "IMPORT_NOTES.md").read_text(encoding="utf-8")
        assert profile.value in notes
