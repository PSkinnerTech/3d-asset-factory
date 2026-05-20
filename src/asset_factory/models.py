from __future__ import annotations

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
    model_config = ConfigDict(extra="forbid")

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
