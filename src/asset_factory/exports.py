from __future__ import annotations

import os
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
FORMAT_EXPORT_FILES = {
    ExportFormat.GLB: ("asset.glb",),
    ExportFormat.STL: ("asset.stl", "stl_report.json"),
}


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

    staged_files = sorted(
        (package_file for package_file in staging_dir.iterdir() if package_file.is_file()),
        key=lambda package_file: package_file.name,
    )
    final_files = {export_dir / package_file.name: package_file for package_file in staged_files}
    stale_files = [
        export_dir / file_name
        for export_format, file_names in FORMAT_EXPORT_FILES.items()
        if export_format not in formats
        for file_name in file_names
        if export_dir / file_name not in final_files
    ]
    managed_files = set(final_files) | set(stale_files)
    existing_managed_files = [file_path for file_path in managed_files if file_path.exists()]

    with tempfile.TemporaryDirectory(
        dir=export_dir.parent,
        prefix=f".{export_dir.name}-backup-",
    ) as backup_root:
        backup_dir = Path(backup_root)
        backups: dict[Path, Path] = {}
        temporary_files: list[Path] = []
        for file_path in existing_managed_files:
            backup_path = backup_dir / file_path.name
            shutil.copy2(file_path, backup_path)
            backups[file_path] = backup_path

        try:
            replacements: list[tuple[Path, Path]] = []
            for final_path, staged_path in final_files.items():
                temporary_path = _temporary_export_path(final_path)
                temporary_files.append(temporary_path)
                shutil.copy2(staged_path, temporary_path)
                replacements.append((temporary_path, final_path))

            for temporary_path, final_path in replacements:
                temporary_path.replace(final_path)

            for stale_file in stale_files:
                stale_file.unlink(missing_ok=True)
        except Exception:
            _rollback_export_package(managed_files, backups, temporary_files)
            raise
        finally:
            for temporary_file in temporary_files:
                temporary_file.unlink(missing_ok=True)


def _temporary_export_path(final_path: Path) -> Path:
    fd, temporary_name = tempfile.mkstemp(
        dir=final_path.parent,
        prefix=f".{final_path.name}.tmp-",
    )
    os.close(fd)
    return Path(temporary_name)


def _rollback_export_package(
    managed_files: set[Path],
    backups: dict[Path, Path],
    temporary_files: list[Path],
) -> None:
    for temporary_file in temporary_files:
        temporary_file.unlink(missing_ok=True)

    for managed_file in managed_files:
        backup_path = backups.get(managed_file)
        if backup_path is not None:
            backup_path.replace(managed_file)
        else:
            managed_file.unlink(missing_ok=True)


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
