from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from asset_factory.exports import export_profiles
from asset_factory.manifest import apply_pipeline_outputs, create_initial_manifest, write_manifest
from asset_factory.models import AssetManifest, AssetSpec
from asset_factory.optimize import optimize_asset
from asset_factory.prompts import build_image_prompt
from asset_factory.qa import run_qa
from asset_factory.runners.base import AssetRunner, RunnerRequest
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
    exports = export_profiles(layout.run_dir, spec.exports) if qa_summary.passed else {}

    manifest = apply_pipeline_outputs(
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
        review_html=None,
        exports=exports,
        qa_summary=qa_summary,
    )
    write_manifest(layout.manifest_path, manifest)
    return PipelineResult(run_dir=layout.run_dir, layout=layout, manifest=manifest)
