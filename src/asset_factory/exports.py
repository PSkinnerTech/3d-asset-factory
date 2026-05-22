from __future__ import annotations

import shutil
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
        export_dir.mkdir(parents=True, exist_ok=True)
        _write_format_artifacts(run_dir, export_dir, selected_formats)
        for source_name, target_name in COMMON_EXPORT_FILES:
            source = run_dir / source_name
            if not source.exists():
                raise FileNotFoundError(f"Cannot export {profile.value}: missing {source}")
            shutil.copy2(source, export_dir / target_name)
        (export_dir / "IMPORT_NOTES.md").write_text(
            import_notes(profile, selected_formats),
            encoding="utf-8",
        )
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
    else:
        (export_dir / "asset.stl").unlink(missing_ok=True)
        (export_dir / "stl_report.json").unlink(missing_ok=True)


def import_notes(profile: ExportProfile, formats: list[ExportFormat] | None = None) -> str:
    selected_formats = _select_formats(formats)
    lines = [f"# {profile.value} import notes", ""]
    if ExportFormat.GLB in selected_formats:
        lines.append(
            "Use asset.glb as the textured runtime asset for web, Unity, Unreal, "
            "and learning-app rendering."
        )
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


def _select_formats(formats: list[ExportFormat] | None) -> list[ExportFormat]:
    if formats is None:
        return [ExportFormat.GLB]
    if not formats:
        raise ValueError("export package must request at least one export format")
    return formats
