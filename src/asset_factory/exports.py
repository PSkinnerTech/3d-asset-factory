from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from asset_factory.models import ExportFormat, ExportProfile
from asset_factory.stl import export_stl

COMMON_EXPORT_FILES = (
    ("previews/thumbnail.png", "thumbnail.png"),
    ("previews/turntable.webm", "turntable.webm"),
    ("reports/qa.json", "qa.json"),
)


def export_profiles(
    run_dir: Path,
    profiles: list[ExportProfile],
    *,
    formats: list[ExportFormat] | None = None,
) -> dict[ExportProfile, Path]:
    selected_formats = _select_formats(formats)
    results: dict[ExportProfile, Path] = {}
    for profile in profiles:
        export_dir = run_dir / "exports" / profile.value
        export_root = export_dir.parent
        export_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(
            dir=export_root,
            prefix=f".{profile.value}-staging-",
        ) as staging_root:
            staging_dir = Path(staging_root)
            _write_format_artifacts(run_dir, staging_dir, selected_formats)
            for source_name, target_name in COMMON_EXPORT_FILES:
                source = run_dir / source_name
                if not source.exists():
                    raise FileNotFoundError(f"Cannot export {profile.value}: missing {source}")
                shutil.copy2(source, staging_dir / target_name)
            (staging_dir / "IMPORT_NOTES.md").write_text(
                import_notes(profile, selected_formats),
                encoding="utf-8",
            )
            _replace_export_package(staging_dir, export_dir, selected_formats)
        results[profile] = export_dir
    return results


def _write_format_artifacts(
    run_dir: Path,
    export_dir: Path,
    formats: list[ExportFormat],
) -> None:
    source_glb = run_dir / "optimize" / "asset.glb"
    if not source_glb.exists():
        raise FileNotFoundError(f"Cannot export asset: missing {source_glb}")

    if ExportFormat.GLB in formats:
        shutil.copy2(source_glb, export_dir / "asset.glb")
    else:
        (export_dir / "asset.glb").unlink(missing_ok=True)

    if ExportFormat.STL in formats:
        export_stl(source_glb, export_dir / "asset.stl", export_dir / "stl_report.json")


def _replace_export_package(
    staging_dir: Path,
    export_dir: Path,
    formats: list[ExportFormat],
) -> None:
    export_dir.mkdir(parents=True, exist_ok=True)
    for package_file in staging_dir.iterdir():
        if package_file.is_file():
            shutil.copy2(package_file, export_dir / package_file.name)

    if ExportFormat.GLB not in formats:
        (export_dir / "asset.glb").unlink(missing_ok=True)
    if ExportFormat.STL not in formats:
        (export_dir / "asset.stl").unlink(missing_ok=True)
        (export_dir / "stl_report.json").unlink(missing_ok=True)


def import_notes(profile: ExportProfile, formats: list[ExportFormat] | None = None) -> str:
    selected_formats = _select_formats(formats)
    lines = [f"# {profile.value} import notes", ""]
    if ExportFormat.GLB in selected_formats:
        lines.append(_glb_import_note(profile))
    if ExportFormat.STL in selected_formats:
        lines.append(
            "Use asset.stl only as a geometry-only CAD/3D printing derivative. "
            "STL does not preserve TRELLIS textures, materials, vertex colors, "
            "PBR values, or opacity. Review stl_report.json before printing."
        )
    lines.append(
        "Keep manifest.json with the asset so review state, learning goal, and QA metrics "
        "remain visible to build tooling."
    )
    return "\n\n".join(lines) + "\n"


def _glb_import_note(profile: ExportProfile) -> str:
    if profile is ExportProfile.WEB:
        return (
            "Use asset.glb as the textured runtime asset with Three.js, "
            "React Three Fiber, Babylon.js, or another web GLB loader."
        )
    if profile is ExportProfile.UNITY:
        return "Use asset.glb as the textured runtime asset with the Unity GLTF importer."
    if profile is ExportProfile.UNREAL:
        return (
            "Use asset.glb as the textured runtime asset with the Unreal glTF importer "
            "or an approved project plugin."
        )
    return "Use asset.glb as the textured runtime asset."


def _select_formats(formats: list[ExportFormat] | None) -> list[ExportFormat]:
    if formats is None:
        return [ExportFormat.GLB]
    if not formats:
        raise ValueError("export package must request at least one export format")
    return formats
