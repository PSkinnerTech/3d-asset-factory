from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from asset_factory.models import (
    AssetIdentity,
    AssetManifest,
    AssetSpec,
    EducationMetadata,
    FileManifest,
    Provenance,
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


def read_manifest(path: Path) -> AssetManifest:
    return AssetManifest.model_validate_json(path.read_text(encoding="utf-8"))
