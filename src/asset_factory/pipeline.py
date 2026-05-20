from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from asset_factory.exports import export_profiles
from asset_factory.manifest import (
    apply_pipeline_outputs,
    create_initial_manifest,
    write_manifest,
    write_package_manifest,
)
from asset_factory.models import AssetManifest, AssetSpec, ExportProfile, QaSummary
from asset_factory.optimize import OptimizedAsset, optimize_asset
from asset_factory.prompts import build_image_prompt
from asset_factory.qa import run_qa
from asset_factory.runners.base import AssetRunner, RunnerRequest, RunnerResult
from asset_factory.runs import RunLayout, create_run_layout


class GeneratedConceptImage(Protocol):
    image_path: Path
    prompt_path: Path
    model: str


class ImageGenerator(Protocol):
    def generate(self, prompt: str, image_path: Path, prompt_path: Path) -> GeneratedConceptImage:
        pass


@dataclass(frozen=True)
class PipelineResult:
    run_dir: Path
    layout: RunLayout
    manifest: AssetManifest


def generate_asset(
    *,
    spec: AssetSpec,
    root_dir: Path,
    image_generator: ImageGenerator,
    runner: AssetRunner,
    timestamp: str | None = None,
) -> PipelineResult:
    layout = create_run_layout(spec, root_dir, timestamp=timestamp)
    manifest = create_initial_manifest(spec, layout, datetime.now(tz=UTC))
    write_manifest(layout.manifest_path, manifest)

    prompt = build_image_prompt(spec)
    generated_image = image_generator.generate(
        prompt=prompt,
        image_path=layout.image_dir / "concept.png",
        prompt_path=layout.image_dir / "prompt.txt",
    )
    runner_result = runner.run(
        RunnerRequest(
            concept_image=generated_image.image_path,
            output_dir=layout.trellis_dir,
            resolution=1024,
        )
    )
    if not runner_result.success:
        raise RuntimeError(
            f"Asset runner {runner_result.runner_type} failed; report: {runner_result.report_path}"
        )

    optimized = optimize_asset(
        runner_result.raw_glb_path,
        generated_image.image_path,
        layout.optimize_dir,
        layout.previews_dir,
    )
    qa_summary = run_qa(spec, optimized.optimized_glb)
    qa_report = layout.reports_dir / "qa.json"
    qa_report.write_text(
        json.dumps(qa_summary.model_dump(mode="json"), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    from asset_factory.review import write_review_html

    review_html = write_review_html(
        layout.run_dir,
        asset_id=spec.id,
        concept_image="image/concept.png",
        glb_path="optimize/asset.glb",
        thumbnail="previews/thumbnail.png",
        qa_passed=qa_summary.passed,
        warnings=qa_summary.warnings,
    )

    manifest = _apply_outputs(
        manifest=manifest,
        generated_image=generated_image,
        runner_result=runner_result,
        optimized=optimized,
        qa_report=qa_report,
        review_html=review_html,
        qa_summary=qa_summary,
        exports={},
    )
    write_manifest(layout.manifest_path, manifest)

    exports = export_profiles(layout.run_dir, spec.exports) if qa_summary.passed else {}

    manifest = _apply_outputs(
        manifest=manifest,
        generated_image=generated_image,
        runner_result=runner_result,
        optimized=optimized,
        qa_report=qa_report,
        review_html=review_html,
        qa_summary=qa_summary,
        exports=exports,
    )
    write_manifest(layout.manifest_path, manifest)
    _write_export_manifests(exports, manifest)
    return PipelineResult(run_dir=layout.run_dir, layout=layout, manifest=manifest)


def _apply_outputs(
    *,
    manifest: AssetManifest,
    generated_image: GeneratedConceptImage,
    runner_result: RunnerResult,
    optimized: OptimizedAsset,
    qa_report: Path,
    review_html: Path,
    qa_summary: QaSummary,
    exports: dict[ExportProfile, Path],
) -> AssetManifest:
    return apply_pipeline_outputs(
        manifest,
        prompt_path=generated_image.prompt_path,
        concept_image=generated_image.image_path,
        image_model=generated_image.model,
        raw_glb=runner_result.raw_glb_path,
        runner_type=runner_result.runner_type,
        runner_version=runner_result.runner_version,
        optimized_glb=optimized.optimized_glb,
        thumbnail=optimized.thumbnail,
        turntable=optimized.turntable,
        qa_report=qa_report,
        review_html=review_html,
        exports=exports,
        qa_summary=qa_summary,
    )


def _write_export_manifests(
    exports: dict[ExportProfile, Path],
    manifest: AssetManifest,
) -> None:
    for profile, export_dir in exports.items():
        write_package_manifest(export_dir / "manifest.json", manifest, profile)
