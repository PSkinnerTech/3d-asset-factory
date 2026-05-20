from __future__ import annotations

import json
import shutil
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import typer
from PIL import Image, ImageDraw

from asset_factory.exports import export_profiles
from asset_factory.images import OpenAIImageGenerator
from asset_factory.manifest import read_manifest, write_manifest
from asset_factory.models import AssetManifest, AssetSpec, ExportProfile, QaThresholds
from asset_factory.pipeline import generate_asset
from asset_factory.qa import run_qa
from asset_factory.runners.mock import MockRunner
from asset_factory.specs import load_asset_spec

app = typer.Typer(help="Generate educational 3D asset bundles from science specs.")


@dataclass(frozen=True)
class _GeneratedConceptImage:
    image_path: Path
    prompt_path: Path
    model: str


class _LocalConceptImageGenerator:
    model = "local-mock-image"

    def generate(self, prompt: str, image_path: Path, prompt_path: Path) -> _GeneratedConceptImage:
        image_path.parent.mkdir(parents=True, exist_ok=True)
        prompt_path.parent.mkdir(parents=True, exist_ok=True)

        image = Image.new("RGB", (512, 512), color=(235, 241, 248))
        draw = ImageDraw.Draw(image)
        draw.rectangle((72, 116, 440, 396), fill=(92, 139, 203), outline=(28, 62, 99), width=8)
        draw.ellipse((156, 172, 356, 372), fill=(245, 181, 85), outline=(92, 67, 35), width=6)
        draw.line((256, 88, 256, 424), fill=(28, 62, 99), width=6)
        image.save(image_path)

        prompt_path.write_text(prompt, encoding="utf-8")
        return _GeneratedConceptImage(
            image_path=image_path,
            prompt_path=prompt_path,
            model=self.model,
        )


@app.command()
def generate(
    spec_path: Path,
    root_dir: Annotated[Path, typer.Option()] = Path("."),
    runner: Annotated[str, typer.Option()] = "mock",
) -> None:
    """Generate a complete asset run from an asset.yaml spec."""
    spec = load_asset_spec(spec_path)
    if runner == "mock":
        asset_runner = MockRunner()
        image_generator = _LocalConceptImageGenerator()
    elif runner == "trellis":
        from asset_factory.runners.trellis import TrellisCommandRunner

        asset_runner = TrellisCommandRunner.from_env()
        image_generator = OpenAIImageGenerator()
    else:
        raise typer.BadParameter("runner must be mock or trellis", param_hint="runner")

    result = generate_asset(
        spec=spec,
        root_dir=root_dir,
        image_generator=image_generator,
        runner=asset_runner,
    )
    typer.echo(f"Generated run: {result.run_dir}")


@app.command()
def qa(run_dir: Path) -> None:
    """Run deterministic QA checks against an existing run directory."""
    manifest_path = run_dir / "manifest.json"
    manifest = read_manifest(manifest_path)
    spec = _spec_from_manifest(run_dir, manifest_path)
    previous_export_dirs = _export_package_dirs(run_dir, manifest)

    summary = run_qa(spec, run_dir / "optimize" / "asset.glb")
    manifest.qa = summary
    if not summary.passed:
        manifest.files.exports = {}
    write_manifest(manifest_path, manifest)

    qa_report = run_dir / "reports" / "qa.json"
    qa_report.parent.mkdir(parents=True, exist_ok=True)
    qa_report.write_text(
        json.dumps(summary.model_dump(mode="json"), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    export_dirs = _export_package_dirs(run_dir, manifest, extra_dirs=previous_export_dirs)
    _sync_export_packages(
        manifest,
        qa_report,
        run_dir / "exports",
        export_dirs=export_dirs,
    )

    typer.echo(f"QA passed: {summary.passed}")


@app.command()
def export(run_dir: Path, profile: ExportProfile = ExportProfile.WEB) -> None:
    """Rebuild an export profile from an existing run directory."""
    manifest_path = run_dir / "manifest.json"
    manifest = read_manifest(manifest_path)
    if manifest.qa.passed is False:
        raise typer.BadParameter(
            "Cannot export run because QA has not passed",
            param_hint="run_dir",
        )

    previous_export_dirs = _export_package_dirs(run_dir, manifest)
    outputs = export_profiles(run_dir, [profile])
    export_dirs = _export_package_dirs(
        run_dir,
        manifest,
        extra_dirs=[*previous_export_dirs, *outputs.values()],
    )
    manifest.files.exports = _exports_from_package_dirs(export_dirs)
    write_manifest(manifest_path, manifest)
    _sync_export_packages(
        manifest,
        run_dir / "reports" / "qa.json",
        run_dir / "exports",
        export_dirs=export_dirs,
    )

    for export_profile, output_dir in outputs.items():
        typer.echo(f"Exported {export_profile.value}: {output_dir}")


@app.command()
def review(run_dir: Path, port: int = 8765) -> None:
    """Open a local browser review dashboard for an existing run directory."""
    from asset_factory.review import serve_review

    serve_review(run_dir, port=port)


def _spec_from_manifest(run_dir: Path, manifest_path: Path) -> AssetSpec:
    manifest = read_manifest(manifest_path)
    copied_spec = run_dir / "input" / "asset.yaml"
    if copied_spec.exists():
        return load_asset_spec(copied_spec)

    source_spec = Path(manifest.provenance.source_spec) if manifest.provenance.source_spec else None
    if source_spec and source_spec.exists():
        return load_asset_spec(source_spec)

    return AssetSpec(
        id=manifest.asset.id,
        subject=manifest.asset.subject,
        object=manifest.asset.object,
        grade_band=manifest.education.grade_band,
        style=manifest.education.style,
        learning_goal=manifest.education.learning_goal,
        exports=list(manifest.files.exports) or [ExportProfile.WEB],
        qa=QaThresholds(max_triangles=150000, max_glb_mb=25),
    )


def _export_package_dirs(
    run_dir: Path,
    manifest: AssetManifest,
    extra_dirs: Iterable[Path] = (),
) -> list[Path]:
    export_dirs = [Path(export_path) for export_path in manifest.files.exports.values()]
    export_dirs.extend(extra_dirs)
    exports_root = (run_dir / "exports").resolve()
    if exports_root.is_dir():
        export_dirs.extend(path for path in exports_root.iterdir() if path.is_dir())

    deduped: dict[Path, None] = {}
    for export_dir in export_dirs:
        resolved = export_dir.resolve()
        if not _is_export_package_dir(resolved, exports_root):
            continue
        if not resolved.is_dir():
            continue
        deduped[resolved] = None
    return list(deduped)


def _exports_from_package_dirs(export_dirs: Iterable[Path]) -> dict[ExportProfile, str]:
    exports: dict[ExportProfile, str] = {}
    for export_dir in export_dirs:
        try:
            profile = ExportProfile(export_dir.name)
        except ValueError:
            continue
        exports[profile] = str(export_dir)
    return exports


def _is_export_package_dir(path: Path, exports_root: Path) -> bool:
    if path == exports_root:
        return False
    try:
        path.relative_to(exports_root)
    except ValueError:
        return False
    return True


def _sync_export_packages(
    manifest: AssetManifest,
    qa_report: Path,
    exports_root: Path,
    export_dirs: Iterable[Path] | None = None,
) -> None:
    resolved_exports_root = exports_root.resolve()
    if export_dirs is None:
        package_dirs = (Path(export_path) for export_path in manifest.files.exports.values())
    else:
        package_dirs = export_dirs

    for export_dir in package_dirs:
        resolved_export_dir = export_dir.resolve()
        if not _is_export_package_dir(resolved_export_dir, resolved_exports_root):
            continue
        if not resolved_export_dir.is_dir():
            continue

        write_manifest(resolved_export_dir / "manifest.json", manifest)
        if qa_report.exists():
            shutil.copy2(qa_report, resolved_export_dir / "qa.json")
