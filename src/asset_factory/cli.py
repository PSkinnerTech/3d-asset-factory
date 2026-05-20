from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import typer
from PIL import Image, ImageDraw

from asset_factory.exports import export_profiles
from asset_factory.images import OpenAIImageGenerator
from asset_factory.manifest import read_manifest, write_manifest
from asset_factory.models import AssetSpec, ExportProfile, QaThresholds
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

    summary = run_qa(spec, run_dir / "optimize" / "asset.glb")
    manifest.qa = summary
    write_manifest(manifest_path, manifest)

    qa_report = run_dir / "reports" / "qa.json"
    qa_report.parent.mkdir(parents=True, exist_ok=True)
    qa_report.write_text(
        json.dumps(summary.model_dump(mode="json"), indent=2, sort_keys=True),
        encoding="utf-8",
    )

    typer.echo(f"QA passed: {summary.passed}")


@app.command()
def export(run_dir: Path, profile: ExportProfile = ExportProfile.WEB) -> None:
    """Rebuild an export profile from an existing run directory."""
    outputs = export_profiles(run_dir, [profile])
    manifest_path = run_dir / "manifest.json"
    manifest = read_manifest(manifest_path)
    manifest.files.exports.update(
        {export_profile: str(path) for export_profile, path in outputs.items()}
    )
    write_manifest(manifest_path, manifest)

    for export_profile, output_dir in outputs.items():
        write_manifest(output_dir / "manifest.json", manifest)
        typer.echo(f"Exported {export_profile.value}: {output_dir}")


@app.command()
def review(run_dir: Path, port: int = 8765) -> None:
    """Open a local browser review dashboard for an existing run directory."""
    from asset_factory.review import serve_review

    serve_review(run_dir, port=port)


def _spec_from_manifest(run_dir: Path, manifest_path: Path) -> AssetSpec:
    manifest = read_manifest(manifest_path)
    source_spec = Path(manifest.provenance.source_spec) if manifest.provenance.source_spec else None
    if source_spec and source_spec.exists():
        return load_asset_spec(source_spec)

    copied_spec = run_dir / "input" / "asset.yaml"
    if copied_spec.exists():
        return load_asset_spec(copied_spec)

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
