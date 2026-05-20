from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from asset_factory.models import (
    AssetIdentity,
    AssetManifest,
    AssetSpec,
    EducationMetadata,
    ExportProfile,
    FileManifest,
    Provenance,
    QaSummary,
    ReviewInfo,
    ReviewState,
)
from asset_factory.runs import RunLayout


def create_initial_manifest(
    spec: AssetSpec,
    layout: RunLayout,
    created_at: datetime,
) -> AssetManifest:
    run_timestamp = layout.run_dir.name
    return AssetManifest(
        asset=AssetIdentity(
            id=spec.id,
            object=spec.object,
            subject=spec.subject,
            run_timestamp=run_timestamp,
        ),
        education=EducationMetadata(
            grade_band=spec.grade_band,
            learning_goal=spec.learning_goal,
            style=spec.style,
            tags=[spec.subject.value, spec.object, spec.style.value],
        ),
        provenance=Provenance(
            source_spec=str(spec.source_path) if spec.source_path else None,
            created_at=created_at,
        ),
        files=FileManifest(),
    )


def write_manifest(path: Path, manifest: AssetManifest) -> None:
    path.write_text(
        json.dumps(manifest.model_dump(mode="json"), indent=2, sort_keys=True),
        encoding="utf-8",
    )


def package_local_manifest(manifest: AssetManifest, profile: ExportProfile) -> AssetManifest:
    package_manifest = manifest.model_copy(deep=True)
    package_manifest.files.concept_image = None
    package_manifest.files.raw_glb = None
    package_manifest.files.optimized_glb = "asset.glb"
    package_manifest.files.thumbnail = "thumbnail.png"
    package_manifest.files.turntable = "turntable.webm"
    package_manifest.files.qa_report = "qa.json"
    package_manifest.files.review_html = None
    package_manifest.files.exports = {profile: "."}
    return package_manifest


def write_package_manifest(path: Path, manifest: AssetManifest, profile: ExportProfile) -> None:
    write_manifest(path, package_local_manifest(manifest, profile))


def read_manifest(path: Path) -> AssetManifest:
    return AssetManifest.model_validate_json(path.read_text(encoding="utf-8"))


def set_review_state(
    path: Path,
    state: ReviewState,
    notes: str = "",
    reviewer: str = "",
    reviewed_at: datetime | None = None,
) -> AssetManifest:
    manifest = read_manifest(path)
    manifest.review = ReviewInfo(
        state=state,
        notes=notes,
        reviewer=reviewer,
        reviewed_at=reviewed_at,
    )
    write_manifest(path, manifest)
    return manifest


def apply_pipeline_outputs(
    manifest: AssetManifest,
    *,
    prompt_path: Path,
    concept_image: Path,
    image_model: str,
    raw_glb: Path,
    runner_type: str,
    runner_version: str,
    optimized_glb: Path,
    thumbnail: Path,
    turntable: Path,
    qa_report: Path,
    review_html: Path | None,
    exports: dict[ExportProfile, Path],
    qa_summary: QaSummary,
) -> AssetManifest:
    manifest.provenance.image_prompt = str(prompt_path)
    manifest.provenance.openai_model = image_model
    manifest.provenance.runner_type = runner_type
    manifest.provenance.runner_version = runner_version
    manifest.files.concept_image = str(concept_image)
    manifest.files.raw_glb = str(raw_glb)
    manifest.files.optimized_glb = str(optimized_glb)
    manifest.files.thumbnail = str(thumbnail)
    manifest.files.turntable = str(turntable)
    manifest.files.qa_report = str(qa_report)
    manifest.files.review_html = str(review_html) if review_html else None
    manifest.files.exports = {profile: str(path) for profile, path in exports.items()}
    manifest.qa = qa_summary
    return manifest
