from __future__ import annotations

import shutil
from pathlib import Path

from asset_factory.models import ExportProfile


def export_profiles(run_dir: Path, profiles: list[ExportProfile]) -> dict[ExportProfile, Path]:
    results: dict[ExportProfile, Path] = {}
    for profile in profiles:
        export_dir = run_dir / "exports" / profile.value
        export_dir.mkdir(parents=True, exist_ok=True)
        for source_name, target_name in (
            ("optimize/asset.glb", "asset.glb"),
            ("previews/thumbnail.png", "thumbnail.png"),
            ("previews/turntable.webm", "turntable.webm"),
            ("reports/qa.json", "qa.json"),
        ):
            source = run_dir / source_name
            if not source.exists():
                raise FileNotFoundError(f"Cannot export {profile.value}: missing {source}")
            shutil.copy2(source, export_dir / target_name)
        (export_dir / "IMPORT_NOTES.md").write_text(import_notes(profile), encoding="utf-8")
        results[profile] = export_dir
    return results


def import_notes(profile: ExportProfile) -> str:
    if profile is ExportProfile.WEB:
        return (
            "# web import notes\n\n"
            "Use asset.glb with Three.js, React Three Fiber, Babylon.js, "
            "or another web GLB loader. "
            "Read manifest.json before showing the asset in a lesson.\n"
        )
    if profile is ExportProfile.UNITY:
        return (
            "# unity import notes\n\n"
            "Import asset.glb with a Unity GLTF importer. Keep manifest.json with the asset so "
            "review state, learning goal, and QA metrics remain visible to build tooling.\n"
        )
    return (
        "# unreal import notes\n\n"
        "Import asset.glb through Unreal's glTF importer or an approved project plugin. Keep "
        "manifest.json beside the asset for review state and educational metadata.\n"
    )
