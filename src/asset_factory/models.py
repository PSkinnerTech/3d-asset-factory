from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ScienceSubject(StrEnum):
    BIOLOGY = "biology"
    CHEMISTRY = "chemistry"
    PHYSICS = "physics"
    EARTH_SCIENCE = "earth_science"
    ASTRONOMY = "astronomy"


class StyleMode(StrEnum):
    CONCEPTUAL = "conceptual"
    REALISTIC = "realistic"


class ExportProfile(StrEnum):
    WEB = "web"
    UNITY = "unity"
    UNREAL = "unreal"


class ReviewState(StrEnum):
    GENERATED = "generated"
    NEEDS_REVIEW = "needs_review"
    NEEDS_CHANGES = "needs_changes"
    APPROVED = "approved"
    REJECTED = "rejected"


class QaThresholds(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_triangles: int = Field(gt=0)
    max_glb_mb: int = Field(gt=0)
    max_texture_px: int = Field(default=4096, gt=0)


class AssetSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    id: str = Field(min_length=1, pattern=r"^[a-z0-9][a-z0-9_\-]*$")
    subject: ScienceSubject
    object: str = Field(min_length=1)
    grade_band: str = Field(min_length=1)
    style: StyleMode
    learning_goal: str = Field(min_length=1)
    exports: list[ExportProfile]
    qa: QaThresholds
    source_path: Path | None = None

    @field_validator("exports")
    @classmethod
    def require_exports(cls, value: list[ExportProfile]) -> list[ExportProfile]:
        if not value:
            raise ValueError("asset spec must request at least one export")
        return value


class AssetIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    object: str
    subject: ScienceSubject
    version: str = "0.1.0"
    run_timestamp: str


class EducationMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    grade_band: str
    learning_goal: str
    style: StyleMode
    tags: list[str] = Field(default_factory=list)


class Provenance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_spec: str | None = None
    image_prompt: str | None = None
    openai_model: str | None = None
    runner_type: str | None = None
    runner_version: str | None = None
    created_at: datetime


class FileManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    manifest: str = "manifest.json"
    concept_image: str | None = None
    raw_glb: str | None = None
    optimized_glb: str | None = None
    thumbnail: str | None = None
    turntable: str | None = None
    qa_report: str | None = None
    review_html: str | None = None
    exports: dict[ExportProfile, str] = Field(default_factory=dict)


class RuntimeHints(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scale: float = 1.0
    orientation: str = "y-up"
    canonical_cameras: list[str] = Field(default_factory=lambda: ["front", "three_quarter", "top"])
    suggested_labels: list[str] = Field(default_factory=list)
    suggested_hotspots: list[str] = Field(default_factory=list)
    interaction_notes: list[str] = Field(default_factory=list)


class QaSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    passed: bool = False
    blocking_failures: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    metrics: dict[str, int | float | str | bool] = Field(default_factory=dict)


class ReviewInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: ReviewState = ReviewState.GENERATED
    notes: str = ""
    reviewer: str = ""
    reviewed_at: datetime | None = None


class AssetManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset: AssetIdentity
    education: EducationMetadata
    provenance: Provenance
    files: FileManifest
    runtime: RuntimeHints = Field(default_factory=RuntimeHints)
    qa: QaSummary = Field(default_factory=QaSummary)
    review: ReviewInfo = Field(default_factory=ReviewInfo)
