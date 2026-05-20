# EdTech 3D Asset Factory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a CLI-first developer tool that converts educational science asset specs into reproducible 3D asset run directories with OpenAI-generated concept images, runner-produced GLBs, QA reports, export bundles, and a local review dashboard.

**Architecture:** Create a Python package with small modules for spec validation, prompt generation, image generation, run directories, runner execution, GLB inspection, QA, optimization, export profiles, review state, and CLI orchestration. Build against a mock runner first so the full artifact pipeline works on ordinary machines, then add a local TRELLIS.2 command runner behind the same interface.

**Tech Stack:** Python 3.11, Typer, Pydantic v2, PyYAML, OpenAI Python SDK, Pillow, imageio, trimesh, pygltflib, pytest, Ruff.

---

## Scope Check

This plan implements the v1 MVP from the approved design spec. Remote GPU runners, team review workflows, curriculum standards mapping, advanced mesh simplification, texture compression, and external source images remain outside this implementation.

## File Structure

All paths are rooted at `/Users/SuperBuilder/dev/3d`.

- `pyproject.toml`: package metadata, console script, runtime dependencies, test/lint configuration.
- `README.md`: local setup and basic CLI usage.
- `src/asset_factory/__init__.py`: package version.
- `src/asset_factory/__main__.py`: `python -m asset_factory` entrypoint.
- `src/asset_factory/cli.py`: Typer commands: `generate`, `qa`, `export`, `review`.
- `src/asset_factory/models.py`: Pydantic models and enums for specs, manifests, QA, files, provenance, review state, runner reports.
- `src/asset_factory/specs.py`: YAML load and validation helpers.
- `src/asset_factory/prompts.py`: style-specific OpenAI prompt builder.
- `src/asset_factory/runs.py`: immutable run directory creation and artifact path helpers.
- `src/asset_factory/manifest.py`: manifest creation, read/write, and review state updates.
- `src/asset_factory/images.py`: OpenAI image generation with injectable client for tests.
- `src/asset_factory/runners/base.py`: runner protocol and shared request/result models.
- `src/asset_factory/runners/mock.py`: deterministic local GLB runner for tests and development.
- `src/asset_factory/runners/trellis.py`: local TRELLIS.2 command runner.
- `src/asset_factory/glb.py`: GLB parsing and metric extraction.
- `src/asset_factory/qa.py`: deterministic blocking checks and warning generation.
- `src/asset_factory/optimize.py`: conservative GLB copy/normalization boundary and preview generation hook.
- `src/asset_factory/exports.py`: web, Unity, and Unreal export profiles.
- `src/asset_factory/pipeline.py`: end-to-end generation orchestration.
- `src/asset_factory/review.py`: static review dashboard generation and local server.
- `src/asset_factory/testing.py`: test helpers for minimal specs and fake image clients.
- `assets/seeds/*.yaml`: 10 seed science asset specs.
- `tests/*.py`: focused unit/integration tests.

## Task 1: Project Scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `README.md`
- Create: `src/asset_factory/__init__.py`
- Create: `src/asset_factory/__main__.py`
- Create: `src/asset_factory/cli.py`
- Create: `tests/test_import.py`

- [ ] **Step 1: Write the failing import and CLI smoke tests**

Create `tests/test_import.py`:

```python
from typer.testing import CliRunner

from asset_factory import __version__
from asset_factory.cli import app


def test_package_version_is_exposed():
    assert __version__ == "0.1.0"


def test_cli_help_renders():
    result = CliRunner().invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "generate" in result.output
    assert "review" in result.output
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
pytest tests/test_import.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'asset_factory'`.

- [ ] **Step 3: Add package metadata and minimal CLI**

Create `pyproject.toml`:

```toml
[project]
name = "asset-factory"
version = "0.1.0"
description = "CLI-first educational 3D asset factory for EdTech engineers"
requires-python = ">=3.11"
dependencies = [
  "typer>=0.12.5",
  "pydantic>=2.8.2",
  "pyyaml>=6.0.2",
  "openai>=1.99.0",
  "pillow>=10.4.0",
  "imageio>=2.35.1",
  "imageio-ffmpeg>=0.5.1",
  "trimesh>=4.4.9",
  "pygltflib>=1.16.2",
  "numpy>=2.0.1"
]

[project.optional-dependencies]
dev = [
  "pytest>=8.3.2",
  "ruff>=0.6.4"
]

[project.scripts]
asset-factory = "asset_factory.cli:app"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]
```

Create `src/asset_factory/__init__.py`:

```python
__version__ = "0.1.0"
```

Create `src/asset_factory/cli.py`:

```python
import typer

app = typer.Typer(help="Generate educational 3D asset bundles from science specs.")


@app.command()
def generate(spec_path: str) -> None:
    """Generate a complete asset run from an asset.yaml spec."""
    typer.echo(f"Generation pipeline is not wired yet: {spec_path}")


@app.command()
def qa(run_dir: str) -> None:
    """Run deterministic QA checks against an existing run directory."""
    typer.echo(f"QA pipeline is not wired yet: {run_dir}")


@app.command()
def export(run_dir: str, profile: str = "web") -> None:
    """Rebuild an export profile from an existing run directory."""
    typer.echo(f"Export pipeline is not wired yet: {run_dir} ({profile})")


@app.command()
def review(run_dir: str, port: int = 8765) -> None:
    """Open a local browser review dashboard for an existing run directory."""
    typer.echo(f"Review server is not wired yet: {run_dir} on port {port}")
```

Create `src/asset_factory/__main__.py`:

```python
from asset_factory.cli import app

if __name__ == "__main__":
    app()
```

Create `README.md`:

````markdown
# EdTech 3D Asset Factory

CLI-first developer tool for generating educational science 3D assets from checked-in specs.

## Development

```bash
python -m pip install -e ".[dev]"
pytest
```

## Commands

```bash
asset-factory generate assets/seeds/chloroplast_conceptual.yaml
asset-factory qa runs/chloroplast_001/<timestamp>
asset-factory export runs/chloroplast_001/<timestamp> --profile web
asset-factory review runs/chloroplast_001/<timestamp>
```
````

- [ ] **Step 4: Run the test to verify it passes**

Run:

```bash
python -m pip install -e ".[dev]"
pytest tests/test_import.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml README.md src/asset_factory tests/test_import.py
git commit -m "chore: scaffold asset factory package"
```

## Task 2: Spec Models and YAML Loading

**Files:**
- Create: `src/asset_factory/models.py`
- Create: `src/asset_factory/specs.py`
- Create: `tests/test_specs.py`

- [ ] **Step 1: Write failing spec validation tests**

Create `tests/test_specs.py`:

```python
from pathlib import Path

import pytest
from pydantic import ValidationError

from asset_factory.models import ExportProfile, ScienceSubject, StyleMode
from asset_factory.specs import load_asset_spec


def test_loads_valid_asset_spec(tmp_path: Path):
    spec_path = tmp_path / "asset.yaml"
    spec_path.write_text(
        """
id: chloroplast_001
subject: biology
object: chloroplast
grade_band: "6-8"
style: conceptual
learning_goal: Identify the outer membrane, stroma, thylakoids, and grana.
exports: ["web", "unity", "unreal"]
qa:
  max_triangles: 150000
  max_glb_mb: 25
""".strip(),
        encoding="utf-8",
    )

    spec = load_asset_spec(spec_path)

    assert spec.id == "chloroplast_001"
    assert spec.subject is ScienceSubject.BIOLOGY
    assert spec.style is StyleMode.CONCEPTUAL
    assert spec.exports == [ExportProfile.WEB, ExportProfile.UNITY, ExportProfile.UNREAL]
    assert spec.qa.max_triangles == 150000
    assert spec.qa.max_glb_mb == 25


def test_rejects_invalid_style(tmp_path: Path):
    spec_path = tmp_path / "asset.yaml"
    spec_path.write_text(
        """
id: bad_style
subject: biology
object: cell
grade_band: "6-8"
style: cinematic
learning_goal: Identify a cell.
exports: ["web"]
qa:
  max_triangles: 1000
  max_glb_mb: 10
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError):
        load_asset_spec(spec_path)


def test_rejects_empty_exports(tmp_path: Path):
    spec_path = tmp_path / "asset.yaml"
    spec_path.write_text(
        """
id: no_exports
subject: physics
object: lever
grade_band: "3-5"
style: conceptual
learning_goal: Identify the fulcrum and load.
exports: []
qa:
  max_triangles: 1000
  max_glb_mb: 10
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError, match="at least one export"):
        load_asset_spec(spec_path)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
pytest tests/test_specs.py -v
```

Expected: FAIL with import errors for `asset_factory.models` and `asset_factory.specs`.

- [ ] **Step 3: Implement spec models and loader**

Create `src/asset_factory/models.py`:

```python
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

    id: str = Field(min_length=1, pattern=r"^[a-z0-9][a-z0-9_\\-]*$")
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
```

Create `src/asset_factory/specs.py`:

```python
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from asset_factory.models import AssetSpec


def load_asset_spec(path: Path | str) -> AssetSpec:
    spec_path = Path(path)
    raw = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"Asset spec must be a YAML mapping: {spec_path}")
    data: dict[str, Any] = dict(raw)
    data["source_path"] = spec_path
    return AssetSpec.model_validate(data)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:

```bash
pytest tests/test_specs.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/asset_factory/models.py src/asset_factory/specs.py tests/test_specs.py
git commit -m "feat: validate science asset specs"
```

## Task 3: Prompt Generation

**Files:**
- Create: `src/asset_factory/prompts.py`
- Create: `tests/test_prompts.py`

- [ ] **Step 1: Write failing prompt tests**

Create `tests/test_prompts.py`:

```python
from asset_factory.models import AssetSpec, ExportProfile, QaThresholds, ScienceSubject, StyleMode
from asset_factory.prompts import build_image_prompt


def make_spec(style: StyleMode) -> AssetSpec:
    return AssetSpec(
        id="chloroplast_001",
        subject=ScienceSubject.BIOLOGY,
        object="chloroplast",
        grade_band="6-8",
        style=style,
        learning_goal="Identify the outer membrane, stroma, thylakoids, and grana.",
        exports=[ExportProfile.WEB],
        qa=QaThresholds(max_triangles=150000, max_glb_mb=25),
    )


def test_conceptual_prompt_prioritizes_readable_structure():
    prompt = build_image_prompt(make_spec(StyleMode.CONCEPTUAL))

    assert "single isolated chloroplast" in prompt
    assert "conceptual educational 3D asset reference" in prompt
    assert "simplified readable parts" in prompt
    assert "no labels" in prompt
    assert "plain neutral background" in prompt


def test_realistic_prompt_prioritizes_recognition():
    prompt = build_image_prompt(make_spec(StyleMode.REALISTIC))

    assert "single isolated chloroplast" in prompt
    assert "realistic educational 3D asset reference" in prompt
    assert "recognizable natural form" in prompt
    assert "no labels" in prompt
    assert "plain neutral background" in prompt
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
pytest tests/test_prompts.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'asset_factory.prompts'`.

- [ ] **Step 3: Implement style-specific prompt generation**

Create `src/asset_factory/prompts.py`:

```python
from __future__ import annotations

from asset_factory.models import AssetSpec, StyleMode


def build_image_prompt(spec: AssetSpec) -> str:
    base = (
        f"Create a single isolated {spec.object} as an educational science object for "
        f"grade band {spec.grade_band}. Learning goal: {spec.learning_goal} "
        "Use a plain neutral background, centered composition, full object visible, "
        "no labels, no arrows, no text, no watermark, no surrounding scene. "
        "The image must be suitable as a source image for image-to-3D asset generation."
    )
    if spec.style is StyleMode.CONCEPTUAL:
        style = (
            "Style: conceptual educational 3D asset reference with simplified readable parts, "
            "clean forms, clear silhouette, gentle color separation, and structure accuracy over realism."
        )
    else:
        style = (
            "Style: realistic educational 3D asset reference with recognizable natural form, "
            "plausible material detail, accurate silhouette, and object isolation over dramatic lighting."
        )
    return f"{base} {style}"
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:

```bash
pytest tests/test_prompts.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/asset_factory/prompts.py tests/test_prompts.py
git commit -m "feat: generate style-aware image prompts"
```

## Task 4: Run Directories and Manifest

**Files:**
- Modify: `src/asset_factory/models.py`
- Create: `src/asset_factory/runs.py`
- Create: `src/asset_factory/manifest.py`
- Create: `tests/test_runs_manifest.py`

- [ ] **Step 1: Write failing run and manifest tests**

Create `tests/test_runs_manifest.py`:

```python
import json
from datetime import UTC, datetime
from pathlib import Path

from asset_factory.manifest import create_initial_manifest, read_manifest, write_manifest
from asset_factory.models import AssetSpec, ExportProfile, QaThresholds, ScienceSubject, StyleMode
from asset_factory.runs import create_run_layout


def make_spec() -> AssetSpec:
    return AssetSpec(
        id="lever_001",
        subject=ScienceSubject.PHYSICS,
        object="lever",
        grade_band="3-5",
        style=StyleMode.CONCEPTUAL,
        learning_goal="Identify the fulcrum, effort, and load.",
        exports=[ExportProfile.WEB, ExportProfile.UNITY],
        qa=QaThresholds(max_triangles=100000, max_glb_mb=20),
        source_path=Path("assets/seeds/lever_conceptual.yaml"),
    )


def test_create_run_layout_writes_expected_directories(tmp_path: Path):
    layout = create_run_layout(make_spec(), tmp_path, timestamp="20260520T120000Z")

    assert layout.run_dir == tmp_path / "runs" / "lever_001" / "20260520T120000Z"
    assert layout.input_dir.is_dir()
    assert layout.image_dir.is_dir()
    assert layout.trellis_dir.is_dir()
    assert layout.optimize_dir.is_dir()
    assert layout.previews_dir.is_dir()
    assert layout.exports_dir.is_dir()
    assert layout.reports_dir.is_dir()


def test_manifest_round_trip(tmp_path: Path):
    spec = make_spec()
    layout = create_run_layout(spec, tmp_path, timestamp="20260520T120000Z")
    manifest = create_initial_manifest(spec, layout, datetime(2026, 5, 20, 12, tzinfo=UTC))

    write_manifest(layout.manifest_path, manifest)
    loaded = read_manifest(layout.manifest_path)

    assert loaded.asset.id == "lever_001"
    assert loaded.education.learning_goal == "Identify the fulcrum, effort, and load."
    assert loaded.review.state == "generated"
    assert loaded.files.manifest == "manifest.json"
    assert json.loads(layout.manifest_path.read_text(encoding="utf-8"))["asset"]["id"] == "lever_001"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
pytest tests/test_runs_manifest.py -v
```

Expected: FAIL with import errors for `asset_factory.runs` and `asset_factory.manifest`.

- [ ] **Step 3: Add manifest models**

Append to `src/asset_factory/models.py`:

```python
from datetime import datetime


class AssetIdentity(BaseModel):
    id: str
    object: str
    subject: ScienceSubject
    version: str = "0.1.0"
    run_timestamp: str


class EducationMetadata(BaseModel):
    grade_band: str
    learning_goal: str
    style: StyleMode
    tags: list[str] = Field(default_factory=list)


class Provenance(BaseModel):
    source_spec: str | None = None
    image_prompt: str | None = None
    openai_model: str | None = None
    runner_type: str | None = None
    runner_version: str | None = None
    created_at: datetime


class FileManifest(BaseModel):
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
    scale: float = 1.0
    orientation: str = "y-up"
    canonical_cameras: list[str] = Field(default_factory=lambda: ["front", "three_quarter", "top"])
    suggested_labels: list[str] = Field(default_factory=list)
    suggested_hotspots: list[str] = Field(default_factory=list)
    interaction_notes: list[str] = Field(default_factory=list)


class QaSummary(BaseModel):
    passed: bool = False
    blocking_failures: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    metrics: dict[str, int | float | str | bool] = Field(default_factory=dict)


class ReviewInfo(BaseModel):
    state: ReviewState = ReviewState.GENERATED
    notes: str = ""
    reviewer: str = ""
    reviewed_at: datetime | None = None


class AssetManifest(BaseModel):
    asset: AssetIdentity
    education: EducationMetadata
    provenance: Provenance
    files: FileManifest
    runtime: RuntimeHints = Field(default_factory=RuntimeHints)
    qa: QaSummary = Field(default_factory=QaSummary)
    review: ReviewInfo = Field(default_factory=ReviewInfo)
```

- [ ] **Step 4: Implement run layout and manifest IO**

Create `src/asset_factory/runs.py`:

```python
from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from asset_factory.models import AssetSpec


@dataclass(frozen=True)
class RunLayout:
    root_dir: Path
    run_dir: Path
    input_dir: Path
    image_dir: Path
    trellis_dir: Path
    optimize_dir: Path
    previews_dir: Path
    exports_dir: Path
    reports_dir: Path
    manifest_path: Path


def utc_timestamp() -> str:
    return datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")


def create_run_layout(spec: AssetSpec, root_dir: Path | str, timestamp: str | None = None) -> RunLayout:
    root = Path(root_dir)
    stamp = timestamp or utc_timestamp()
    run_dir = root / "runs" / spec.id / stamp
    layout = RunLayout(
        root_dir=root,
        run_dir=run_dir,
        input_dir=run_dir / "input",
        image_dir=run_dir / "image",
        trellis_dir=run_dir / "trellis",
        optimize_dir=run_dir / "optimize",
        previews_dir=run_dir / "previews",
        exports_dir=run_dir / "exports",
        reports_dir=run_dir / "reports",
        manifest_path=run_dir / "manifest.json",
    )
    for directory in (
        layout.input_dir,
        layout.image_dir,
        layout.trellis_dir,
        layout.optimize_dir,
        layout.previews_dir,
        layout.exports_dir,
        layout.reports_dir,
    ):
        directory.mkdir(parents=True, exist_ok=False)
    if spec.source_path and spec.source_path.exists():
        shutil.copy2(spec.source_path, layout.input_dir / "asset.yaml")
    return layout
```

Create `src/asset_factory/manifest.py`:

```python
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
```

- [ ] **Step 5: Run the tests to verify they pass**

Run:

```bash
pytest tests/test_runs_manifest.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/asset_factory/models.py src/asset_factory/runs.py src/asset_factory/manifest.py tests/test_runs_manifest.py
git commit -m "feat: create immutable asset run manifests"
```

## Task 5: OpenAI Image Generation Module

**Files:**
- Create: `src/asset_factory/images.py`
- Create: `tests/test_images.py`

- [ ] **Step 1: Write failing image generation tests**

Create `tests/test_images.py`:

```python
import base64
from pathlib import Path

from PIL import Image

from asset_factory.images import OpenAIImageGenerator


class FakeImageData:
    def __init__(self, b64_json: str):
        self.b64_json = b64_json


class FakeImageResponse:
    def __init__(self, b64_json: str):
        self.data = [FakeImageData(b64_json)]


class FakeImages:
    def __init__(self, b64_json: str):
        self.b64_json = b64_json
        self.calls = []

    def generate(self, **kwargs):
        self.calls.append(kwargs)
        return FakeImageResponse(self.b64_json)


class FakeClient:
    def __init__(self, b64_json: str):
        self.images = FakeImages(b64_json)


def tiny_png_b64() -> str:
    image = Image.new("RGB", (4, 4), color=(40, 80, 120))
    data = Path("tiny.png")
    image.save(data)
    raw = data.read_bytes()
    data.unlink()
    return base64.b64encode(raw).decode("ascii")


def test_generate_image_writes_prompt_and_png(tmp_path: Path):
    client = FakeClient(tiny_png_b64())
    generator = OpenAIImageGenerator(client=client)

    output = generator.generate(prompt="single isolated lever", image_path=tmp_path / "concept.png", prompt_path=tmp_path / "prompt.txt")

    assert output.image_path == tmp_path / "concept.png"
    assert output.prompt_path == tmp_path / "prompt.txt"
    assert output.model == "gpt-image-2"
    assert (tmp_path / "concept.png").read_bytes().startswith(b"\\x89PNG")
    assert (tmp_path / "prompt.txt").read_text(encoding="utf-8") == "single isolated lever"
    assert client.images.calls[0]["model"] == "gpt-image-2"
    assert client.images.calls[0]["prompt"] == "single isolated lever"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
pytest tests/test_images.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'asset_factory.images'`.

- [ ] **Step 3: Implement injectable OpenAI image generation**

Create `src/asset_factory/images.py`:

```python
from __future__ import annotations

import base64
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from openai import OpenAI


class ImagesClient(Protocol):
    def generate(self, **kwargs: object) -> object:
        pass


class OpenAIClient(Protocol):
    images: ImagesClient


@dataclass(frozen=True)
class GeneratedImage:
    image_path: Path
    prompt_path: Path
    model: str


class OpenAIImageGenerator:
    def __init__(self, client: OpenAIClient | None = None, model: str = "gpt-image-2"):
        self.client = client or OpenAI()
        self.model = model

    def generate(self, prompt: str, image_path: Path, prompt_path: Path) -> GeneratedImage:
        response = self.client.images.generate(
            model=self.model,
            prompt=prompt,
            size="1024x1024",
        )
        data = getattr(response, "data")
        if not data:
            raise RuntimeError("OpenAI image generation returned no image data")
        b64_json = getattr(data[0], "b64_json", None)
        if not b64_json:
            raise RuntimeError("OpenAI image generation returned no b64_json image")
        image_path.parent.mkdir(parents=True, exist_ok=True)
        prompt_path.parent.mkdir(parents=True, exist_ok=True)
        image_path.write_bytes(base64.b64decode(b64_json))
        prompt_path.write_text(prompt, encoding="utf-8")
        return GeneratedImage(image_path=image_path, prompt_path=prompt_path, model=self.model)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:

```bash
pytest tests/test_images.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/asset_factory/images.py tests/test_images.py
git commit -m "feat: generate auditable OpenAI concept images"
```

## Task 6: Runner Interface and Mock Runner

**Files:**
- Create: `src/asset_factory/runners/__init__.py`
- Create: `src/asset_factory/runners/base.py`
- Create: `src/asset_factory/runners/mock.py`
- Create: `tests/test_runners.py`

- [ ] **Step 1: Write failing runner tests**

Create `tests/test_runners.py`:

```python
from pathlib import Path

from PIL import Image

from asset_factory.runners.base import RunnerRequest
from asset_factory.runners.mock import MockRunner


def test_mock_runner_writes_raw_glb_and_report(tmp_path: Path):
    image_path = tmp_path / "concept.png"
    Image.new("RGB", (16, 16), color=(120, 80, 40)).save(image_path)
    output_dir = tmp_path / "trellis"

    result = MockRunner().run(RunnerRequest(concept_image=image_path, output_dir=output_dir, resolution=512))

    assert result.raw_glb_path == output_dir / "raw.glb"
    assert result.report_path == output_dir / "raw_report.json"
    assert result.raw_glb_path.read_bytes()[:4] == b"glTF"
    assert '"runner_type": "mock"' in result.report_path.read_text(encoding="utf-8")
    assert result.runner_type == "mock"
    assert result.success is True
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
pytest tests/test_runners.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'asset_factory.runners'`.

- [ ] **Step 3: Implement runner protocol and mock runner**

Create `src/asset_factory/runners/__init__.py`:

```python
from asset_factory.runners.base import RunnerRequest, RunnerResult
from asset_factory.runners.mock import MockRunner

__all__ = ["MockRunner", "RunnerRequest", "RunnerResult"]
```

Create `src/asset_factory/runners/base.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class RunnerRequest:
    concept_image: Path
    output_dir: Path
    resolution: int = 1024


@dataclass(frozen=True)
class RunnerResult:
    raw_glb_path: Path
    report_path: Path
    runner_type: str
    runner_version: str
    success: bool


class AssetRunner(Protocol):
    def run(self, request: RunnerRequest) -> RunnerResult:
        pass
```

Create `src/asset_factory/runners/mock.py`:

```python
from __future__ import annotations

import json
from datetime import UTC, datetime

import trimesh

from asset_factory.runners.base import RunnerRequest, RunnerResult


class MockRunner:
    runner_type = "mock"
    runner_version = "0.1.0"

    def run(self, request: RunnerRequest) -> RunnerResult:
        request.output_dir.mkdir(parents=True, exist_ok=True)
        raw_glb_path = request.output_dir / "raw.glb"
        report_path = request.output_dir / "raw_report.json"

        mesh = trimesh.creation.box(extents=(1.0, 1.0, 1.0))
        mesh.visual = trimesh.visual.ColorVisuals(mesh, vertex_colors=[90, 140, 210, 255])
        mesh.export(raw_glb_path)

        report = {
            "runner_type": self.runner_type,
            "runner_version": self.runner_version,
            "resolution": request.resolution,
            "concept_image": str(request.concept_image),
            "raw_glb": str(raw_glb_path),
            "started_at": datetime.now(tz=UTC).isoformat(),
            "ended_at": datetime.now(tz=UTC).isoformat(),
            "success": True,
        }
        report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
        return RunnerResult(
            raw_glb_path=raw_glb_path,
            report_path=report_path,
            runner_type=self.runner_type,
            runner_version=self.runner_version,
            success=True,
        )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:

```bash
pytest tests/test_runners.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/asset_factory/runners tests/test_runners.py
git commit -m "feat: add runner interface and mock GLB runner"
```

## Task 7: GLB Inspection and QA Gate

**Files:**
- Create: `src/asset_factory/glb.py`
- Create: `src/asset_factory/qa.py`
- Create: `tests/test_qa.py`

- [ ] **Step 1: Write failing QA tests**

Create `tests/test_qa.py`:

```python
from pathlib import Path

import trimesh

from asset_factory.models import AssetSpec, ExportProfile, QaThresholds, ScienceSubject, StyleMode
from asset_factory.qa import run_qa


def make_spec(max_triangles: int = 1000, max_glb_mb: int = 10) -> AssetSpec:
    return AssetSpec(
        id="qa_asset",
        subject=ScienceSubject.PHYSICS,
        object="cube",
        grade_band="3-5",
        style=StyleMode.CONCEPTUAL,
        learning_goal="Inspect a cube.",
        exports=[ExportProfile.WEB],
        qa=QaThresholds(max_triangles=max_triangles, max_glb_mb=max_glb_mb),
    )


def write_box(path: Path) -> None:
    mesh = trimesh.creation.box(extents=(1, 1, 1))
    mesh.visual = trimesh.visual.ColorVisuals(mesh, vertex_colors=[200, 120, 80, 255])
    mesh.export(path)


def test_qa_passes_valid_glb(tmp_path: Path):
    glb_path = tmp_path / "asset.glb"
    glb_path.parent.mkdir(parents=True, exist_ok=True)
    write_box(glb_path)

    report = run_qa(make_spec(), glb_path)

    assert report.passed is True
    assert report.blocking_failures == []
    assert report.metrics["triangles"] == 12
    assert report.metrics["file_size_bytes"] > 0


def test_qa_blocks_missing_glb(tmp_path: Path):
    report = run_qa(make_spec(), tmp_path / "missing.glb")

    assert report.passed is False
    assert "GLB file is missing" in report.blocking_failures


def test_qa_blocks_triangle_budget(tmp_path: Path):
    glb_path = tmp_path / "asset.glb"
    write_box(glb_path)

    report = run_qa(make_spec(max_triangles=1), glb_path)

    assert report.passed is False
    assert "Triangle count 12 exceeds max_triangles 1" in report.blocking_failures
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
pytest tests/test_qa.py -v
```

Expected: FAIL with import errors for `asset_factory.qa`.

- [ ] **Step 3: Implement GLB metrics and QA checks**

Create `src/asset_factory/glb.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import trimesh


@dataclass(frozen=True)
class GlbMetrics:
    triangles: int
    file_size_bytes: int
    has_geometry: bool
    has_material: bool
    has_base_color: bool


def inspect_glb(path: Path) -> GlbMetrics:
    loaded = trimesh.load(path, force="scene")
    geometries = list(getattr(loaded, "geometry", {}).values())
    if not geometries and hasattr(loaded, "faces"):
        geometries = [loaded]

    triangles = 0
    has_material = False
    has_base_color = False
    for geometry in geometries:
        faces = getattr(geometry, "faces", [])
        triangles += len(faces)
        visual = getattr(geometry, "visual", None)
        material = getattr(visual, "material", None)
        if material is not None:
            has_material = True
            has_base_color = True
        vertex_colors = getattr(visual, "vertex_colors", None)
        if vertex_colors is not None and len(vertex_colors) > 0:
            has_material = True
            has_base_color = True

    return GlbMetrics(
        triangles=triangles,
        file_size_bytes=path.stat().st_size,
        has_geometry=triangles > 0,
        has_material=has_material,
        has_base_color=has_base_color,
    )
```

Create `src/asset_factory/qa.py`:

```python
from __future__ import annotations

from pathlib import Path

from asset_factory.glb import inspect_glb
from asset_factory.models import AssetSpec, QaSummary


def run_qa(spec: AssetSpec, glb_path: Path) -> QaSummary:
    failures: list[str] = []
    warnings: list[str] = []
    metrics: dict[str, int | float | str | bool] = {}

    if not glb_path.exists():
        return QaSummary(
            passed=False,
            blocking_failures=["GLB file is missing"],
            warnings=[],
            metrics={},
        )

    try:
        glb_metrics = inspect_glb(glb_path)
    except Exception as exc:
        return QaSummary(
            passed=False,
            blocking_failures=[f"GLB cannot be parsed: {exc}"],
            warnings=[],
            metrics={},
        )

    metrics.update(
        {
            "triangles": glb_metrics.triangles,
            "file_size_bytes": glb_metrics.file_size_bytes,
            "has_geometry": glb_metrics.has_geometry,
            "has_material": glb_metrics.has_material,
            "has_base_color": glb_metrics.has_base_color,
        }
    )

    max_bytes = spec.qa.max_glb_mb * 1024 * 1024
    if not glb_metrics.has_geometry:
        failures.append("Required mesh data is missing")
    if not glb_metrics.has_material:
        failures.append("Required material data is missing")
    if not glb_metrics.has_base_color:
        failures.append("Required base color data is missing")
    if glb_metrics.triangles > spec.qa.max_triangles:
        failures.append(
            f"Triangle count {glb_metrics.triangles} exceeds max_triangles {spec.qa.max_triangles}"
        )
    if glb_metrics.file_size_bytes > max_bytes:
        failures.append(
            f"GLB size {glb_metrics.file_size_bytes} bytes exceeds max_glb_mb {spec.qa.max_glb_mb}"
        )
    if glb_metrics.triangles < 50:
        warnings.append("Asset has very low triangle count; visual quality needs review")

    return QaSummary(
        passed=not failures,
        blocking_failures=failures,
        warnings=warnings,
        metrics=metrics,
    )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:

```bash
pytest tests/test_qa.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/asset_factory/glb.py src/asset_factory/qa.py tests/test_qa.py
git commit -m "feat: block unusable GLB outputs"
```

## Task 8: Optimization and Preview Generation

**Files:**
- Create: `src/asset_factory/optimize.py`
- Create: `tests/test_optimize.py`

- [ ] **Step 1: Write failing optimization tests**

Create `tests/test_optimize.py`:

```python
from pathlib import Path

from PIL import Image
import trimesh

from asset_factory.optimize import optimize_asset


def write_box(path: Path) -> None:
    mesh = trimesh.creation.box(extents=(1, 1, 1))
    mesh.visual = trimesh.visual.ColorVisuals(mesh, vertex_colors=[120, 160, 220, 255])
    mesh.export(path)


def test_optimize_copies_glb_and_generates_previews(tmp_path: Path):
    raw_glb = tmp_path / "trellis" / "raw.glb"
    concept = tmp_path / "image" / "concept.png"
    optimized_dir = tmp_path / "optimize"
    previews_dir = tmp_path / "previews"
    raw_glb.parent.mkdir(parents=True)
    concept.parent.mkdir(parents=True)
    write_box(raw_glb)
    Image.new("RGB", (64, 64), color=(20, 70, 120)).save(concept)

    result = optimize_asset(raw_glb, concept, optimized_dir, previews_dir)

    assert result.optimized_glb == optimized_dir / "asset.glb"
    assert result.thumbnail == previews_dir / "thumbnail.png"
    assert result.turntable == previews_dir / "turntable.webm"
    assert result.optimized_glb.read_bytes()[:4] == b"glTF"
    assert Image.open(result.thumbnail).size == (512, 512)
    assert result.turntable.stat().st_size > 0
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
pytest tests/test_optimize.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'asset_factory.optimize'`.

- [ ] **Step 3: Implement conservative optimization and previews**

Create `src/asset_factory/optimize.py`:

```python
from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

import imageio.v3 as iio
import numpy as np
from PIL import Image, ImageOps


@dataclass(frozen=True)
class OptimizedAsset:
    optimized_glb: Path
    thumbnail: Path
    turntable: Path


def optimize_asset(
    raw_glb: Path,
    concept_image: Path,
    optimize_dir: Path,
    previews_dir: Path,
) -> OptimizedAsset:
    optimize_dir.mkdir(parents=True, exist_ok=True)
    previews_dir.mkdir(parents=True, exist_ok=True)

    optimized_glb = optimize_dir / "asset.glb"
    shutil.copy2(raw_glb, optimized_glb)

    thumbnail = previews_dir / "thumbnail.png"
    image = Image.open(concept_image).convert("RGB")
    image = ImageOps.contain(image, (512, 512), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (512, 512), color=(245, 245, 245))
    canvas.paste(image, ((512 - image.width) // 2, (512 - image.height) // 2))
    canvas.save(thumbnail)

    turntable = previews_dir / "turntable.webm"
    frames = []
    base = np.asarray(canvas)
    for shift in (0, 16, 32, 48, 64, 48, 32, 16):
        frames.append(np.roll(base, shift=shift, axis=1))
    iio.imwrite(turntable, frames, fps=8, codec="libvpx-vp9")

    return OptimizedAsset(optimized_glb=optimized_glb, thumbnail=thumbnail, turntable=turntable)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:

```bash
pytest tests/test_optimize.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/asset_factory/optimize.py tests/test_optimize.py
git commit -m "feat: create optimized asset previews"
```

## Task 9: Export Profiles

**Files:**
- Create: `src/asset_factory/exports.py`
- Create: `tests/test_exports.py`

- [ ] **Step 1: Write failing export profile tests**

Create `tests/test_exports.py`:

```python
import json
from pathlib import Path

from asset_factory.exports import export_profiles
from asset_factory.models import ExportProfile


def write_artifacts(run_dir: Path) -> None:
    (run_dir / "optimize").mkdir(parents=True)
    (run_dir / "previews").mkdir(parents=True)
    (run_dir / "reports").mkdir(parents=True)
    (run_dir / "optimize" / "asset.glb").write_bytes(b"glTF-demo")
    (run_dir / "previews" / "thumbnail.png").write_bytes(b"png")
    (run_dir / "previews" / "turntable.webm").write_bytes(b"webm")
    (run_dir / "reports" / "qa.json").write_text("{}", encoding="utf-8")
    (run_dir / "manifest.json").write_text('{"asset":{"id":"demo"}}', encoding="utf-8")


def test_exports_web_unity_and_unreal_profiles(tmp_path: Path):
    run_dir = tmp_path / "runs" / "demo" / "20260520T120000Z"
    write_artifacts(run_dir)

    results = export_profiles(run_dir, [ExportProfile.WEB, ExportProfile.UNITY, ExportProfile.UNREAL])

    assert set(results) == {ExportProfile.WEB, ExportProfile.UNITY, ExportProfile.UNREAL}
    for profile, export_dir in results.items():
        assert (export_dir / "asset.glb").read_bytes() == b"glTF-demo"
        assert (export_dir / "manifest.json").exists()
        assert (export_dir / "thumbnail.png").exists()
        assert (export_dir / "turntable.webm").exists()
        notes = (export_dir / "IMPORT_NOTES.md").read_text(encoding="utf-8")
        assert profile.value in notes
    web_manifest = json.loads((results[ExportProfile.WEB] / "manifest.json").read_text(encoding="utf-8"))
    assert web_manifest["asset"]["id"] == "demo"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
pytest tests/test_exports.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'asset_factory.exports'`.

- [ ] **Step 3: Implement export profile packaging**

Create `src/asset_factory/exports.py`:

```python
from __future__ import annotations

import shutil
from pathlib import Path

from asset_factory.models import ExportProfile


def export_profiles(run_dir: Path, profiles: list[ExportProfile]) -> dict[ExportProfile, Path]:
    results: dict[ExportProfile, Path] = {}
    for profile in profiles:
        export_dir = run_dir / "exports" / profile.value
        export_dir.mkdir(parents=True, exist_ok=True)
        for source_name, target_name in (
            ("optimize/asset.glb", "asset.glb"),
            ("manifest.json", "manifest.json"),
            ("previews/thumbnail.png", "thumbnail.png"),
            ("previews/turntable.webm", "turntable.webm"),
            ("reports/qa.json", "qa.json"),
        ):
            source = run_dir / source_name
            if not source.exists():
                raise FileNotFoundError(f"Cannot export {profile.value}: missing {source}")
            shutil.copy2(source, export_dir / target_name)
        (export_dir / "IMPORT_NOTES.md").write_text(import_notes(profile), encoding="utf-8")
        results[profile] = export_dir
    return results


def import_notes(profile: ExportProfile) -> str:
    if profile is ExportProfile.WEB:
        return (
            "# web import notes\n\n"
            "Use asset.glb with Three.js, React Three Fiber, Babylon.js, or another web GLB loader. "
            "Read manifest.json before showing the asset in a lesson.\n"
        )
    if profile is ExportProfile.UNITY:
        return (
            "# unity import notes\n\n"
            "Import asset.glb with a Unity GLTF importer. Keep manifest.json with the asset so "
            "review state, learning goal, and QA metrics remain visible to build tooling.\n"
        )
    return (
        "# unreal import notes\n\n"
        "Import asset.glb through Unreal's glTF importer or an approved project plugin. Keep "
        "manifest.json beside the asset for review state and educational metadata.\n"
    )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:

```bash
pytest tests/test_exports.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/asset_factory/exports.py tests/test_exports.py
git commit -m "feat: package web unity and unreal exports"
```

## Task 10: Pipeline Orchestration

**Files:**
- Modify: `src/asset_factory/manifest.py`
- Create: `src/asset_factory/pipeline.py`
- Create: `tests/test_pipeline.py`

- [ ] **Step 1: Write failing end-to-end pipeline test with fake image generator and mock runner**

Create `tests/test_pipeline.py`:

```python
from pathlib import Path

from PIL import Image

from asset_factory.models import AssetSpec, ExportProfile, QaThresholds, ScienceSubject, StyleMode
from asset_factory.pipeline import generate_asset
from asset_factory.runners.mock import MockRunner


class FakeImageGenerator:
    model = "fake-image-model"

    def generate(self, prompt: str, image_path: Path, prompt_path: Path):
        Image.new("RGB", (64, 64), color=(30, 90, 150)).save(image_path)
        prompt_path.write_text(prompt, encoding="utf-8")
        return type(
            "GeneratedImage",
            (),
            {"image_path": image_path, "prompt_path": prompt_path, "model": self.model},
        )()


def make_spec() -> AssetSpec:
    return AssetSpec(
        id="pulley_001",
        subject=ScienceSubject.PHYSICS,
        object="pulley",
        grade_band="3-5",
        style=StyleMode.CONCEPTUAL,
        learning_goal="Identify the wheel, axle, rope, and load.",
        exports=[ExportProfile.WEB, ExportProfile.UNITY],
        qa=QaThresholds(max_triangles=150000, max_glb_mb=25),
    )


def test_generate_asset_creates_complete_run(tmp_path: Path):
    result = generate_asset(
        spec=make_spec(),
        root_dir=tmp_path,
        image_generator=FakeImageGenerator(),
        runner=MockRunner(),
        timestamp="20260520T120000Z",
    )

    run_dir = result.run_dir
    assert (run_dir / "image" / "concept.png").exists()
    assert (run_dir / "image" / "prompt.txt").exists()
    assert (run_dir / "trellis" / "raw.glb").exists()
    assert (run_dir / "optimize" / "asset.glb").exists()
    assert (run_dir / "previews" / "thumbnail.png").exists()
    assert (run_dir / "previews" / "turntable.webm").exists()
    assert (run_dir / "exports" / "web" / "asset.glb").exists()
    assert (run_dir / "exports" / "unity" / "asset.glb").exists()
    assert result.manifest.qa.passed is True
    assert result.manifest.provenance.openai_model == "fake-image-model"
    assert result.manifest.provenance.runner_type == "mock"
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
pytest tests/test_pipeline.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'asset_factory.pipeline'`.

- [ ] **Step 3: Add manifest update helpers**

Append to `src/asset_factory/manifest.py`:

```python
from asset_factory.models import ExportProfile, QaSummary, ReviewInfo, ReviewState


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
```

- [ ] **Step 4: Implement pipeline orchestration**

Create `src/asset_factory/pipeline.py`:

```python
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from asset_factory.exports import export_profiles
from asset_factory.images import OpenAIImageGenerator
from asset_factory.manifest import apply_pipeline_outputs, create_initial_manifest, write_manifest
from asset_factory.models import AssetManifest, AssetSpec
from asset_factory.optimize import optimize_asset
from asset_factory.prompts import build_image_prompt
from asset_factory.qa import run_qa
from asset_factory.runs import RunLayout, create_run_layout
from asset_factory.runners.base import AssetRunner, RunnerRequest


@dataclass(frozen=True)
class PipelineResult:
    run_dir: Path
    layout: RunLayout
    manifest: AssetManifest


def generate_asset(
    *,
    spec: AssetSpec,
    root_dir: Path,
    image_generator: OpenAIImageGenerator,
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
    if not qa_summary.passed:
        exports = {}
    else:
        exports = export_profiles(layout.run_dir, spec.exports)
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
```

- [ ] **Step 5: Run the test to verify it passes**

Run:

```bash
pytest tests/test_pipeline.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/asset_factory/manifest.py src/asset_factory/pipeline.py tests/test_pipeline.py
git commit -m "feat: orchestrate complete asset generation runs"
```

## Task 11: CLI Commands

**Files:**
- Modify: `src/asset_factory/cli.py`
- Create: `tests/test_cli.py`

- [ ] **Step 1: Write failing CLI tests**

Create `tests/test_cli.py`:

```python
from pathlib import Path

from typer.testing import CliRunner

from asset_factory.cli import app


runner = CliRunner()


def write_spec(path: Path) -> None:
    path.write_text(
        """
id: cli_pulley
subject: physics
object: pulley
grade_band: "3-5"
style: conceptual
learning_goal: Identify the wheel, axle, rope, and load.
exports: ["web"]
qa:
  max_triangles: 150000
  max_glb_mb: 25
""".strip(),
        encoding="utf-8",
    )


def test_generate_with_mock_runner(tmp_path: Path):
    spec_path = tmp_path / "pulley.yaml"
    write_spec(spec_path)

    result = runner.invoke(
        app,
        ["generate", str(spec_path), "--root-dir", str(tmp_path), "--runner", "mock"],
    )

    assert result.exit_code == 0
    assert "Generated run:" in result.output
    assert (tmp_path / "runs" / "cli_pulley").exists()


def test_qa_command_reports_existing_run(tmp_path: Path):
    spec_path = tmp_path / "pulley.yaml"
    write_spec(spec_path)
    generated = runner.invoke(
        app,
        ["generate", str(spec_path), "--root-dir", str(tmp_path), "--runner", "mock"],
    )
    run_dir = Path(generated.output.strip().split("Generated run: ")[1])

    result = runner.invoke(app, ["qa", str(run_dir)])

    assert result.exit_code == 0
    assert "QA passed: True" in result.output
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
pytest tests/test_cli.py -v
```

Expected: FAIL because the CLI still prints the scaffold messages.

- [ ] **Step 3: Implement real CLI wiring for mock runner**

Replace `src/asset_factory/cli.py` with:

```python
from __future__ import annotations

from pathlib import Path

import typer

from asset_factory.exports import export_profiles
from asset_factory.images import OpenAIImageGenerator
from asset_factory.manifest import read_manifest, write_manifest
from asset_factory.models import ExportProfile
from asset_factory.pipeline import generate_asset
from asset_factory.qa import run_qa
from asset_factory.runners.mock import MockRunner
from asset_factory.specs import load_asset_spec

app = typer.Typer(help="Generate educational 3D asset bundles from science specs.")


@app.command()
def generate(
    spec_path: Path,
    root_dir: Path = typer.Option(Path("."), help="Workspace root for runs/ output."),
    runner: str = typer.Option("mock", help="Runner type: mock or trellis."),
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
        raise typer.BadParameter("runner must be mock or trellis")
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
    manifest = read_manifest(run_dir / "manifest.json")
    spec_exports = list(manifest.files.exports) or [ExportProfile.WEB]
    spec = load_asset_spec(Path(manifest.provenance.source_spec)) if manifest.provenance.source_spec else None
    if spec is None:
        from asset_factory.models import AssetSpec, QaThresholds

        spec = AssetSpec(
            id=manifest.asset.id,
            subject=manifest.asset.subject,
            object=manifest.asset.object,
            grade_band=manifest.education.grade_band,
            style=manifest.education.style,
            learning_goal=manifest.education.learning_goal,
            exports=spec_exports,
            qa=QaThresholds(max_triangles=150000, max_glb_mb=25),
        )
    summary = run_qa(spec, run_dir / "optimize" / "asset.glb")
    manifest.qa = summary
    write_manifest(run_dir / "manifest.json", manifest)
    typer.echo(f"QA passed: {summary.passed}")


@app.command()
def export(run_dir: Path, profile: ExportProfile = ExportProfile.WEB) -> None:
    """Rebuild an export profile from an existing run directory."""
    results = export_profiles(run_dir, [profile])
    typer.echo(f"Exported {profile.value}: {results[profile]}")


@app.command()
def review(run_dir: Path, port: int = 8765) -> None:
    """Open a local browser review dashboard for an existing run directory."""
    from asset_factory.review import serve_review

    serve_review(run_dir, port=port)


class _LocalConceptImageGenerator:
    model = "local-mock-image"

    def generate(self, prompt: str, image_path: Path, prompt_path: Path):
        from PIL import Image, ImageDraw

        image_path.parent.mkdir(parents=True, exist_ok=True)
        prompt_path.parent.mkdir(parents=True, exist_ok=True)
        image = Image.new("RGB", (1024, 1024), color=(240, 244, 248))
        draw = ImageDraw.Draw(image)
        draw.ellipse((312, 312, 712, 712), fill=(80, 140, 210))
        draw.text((80, 900), "mock concept image", fill=(20, 30, 40))
        image.save(image_path)
        prompt_path.write_text(prompt, encoding="utf-8")
        return type(
            "GeneratedImage",
            (),
            {"image_path": image_path, "prompt_path": prompt_path, "model": self.model},
        )()
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:

```bash
pytest tests/test_cli.py -v
```

Expected: PASS.

- [ ] **Step 5: Run the full test suite**

Run:

```bash
pytest -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/asset_factory/cli.py tests/test_cli.py
git commit -m "feat: wire CLI to asset generation pipeline"
```

## Task 12: Review Dashboard

**Files:**
- Create: `src/asset_factory/review.py`
- Create: `tests/test_review.py`

- [ ] **Step 1: Write failing review dashboard tests**

Create `tests/test_review.py`:

```python
from pathlib import Path

from asset_factory.review import build_review_html, write_review_html


def test_build_review_html_contains_manifest_and_viewer():
    html = build_review_html(
        asset_id="chloroplast_001",
        concept_image="image/concept.png",
        glb_path="optimize/asset.glb",
        thumbnail="previews/thumbnail.png",
        qa_passed=True,
        warnings=["Science correctness needs review"],
    )

    assert "chloroplast_001" in html
    assert "image/concept.png" in html
    assert "optimize/asset.glb" in html
    assert "Science correctness needs review" in html
    assert "GLTFLoader" in html


def test_write_review_html(tmp_path: Path):
    path = write_review_html(
        tmp_path,
        asset_id="demo",
        concept_image="image/concept.png",
        glb_path="optimize/asset.glb",
        thumbnail="previews/thumbnail.png",
        qa_passed=False,
        warnings=["Bad silhouette"],
    )

    assert path == tmp_path / "reports" / "review.html"
    assert path.exists()
    assert "Bad silhouette" in path.read_text(encoding="utf-8")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
pytest tests/test_review.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'asset_factory.review'`.

- [ ] **Step 3: Implement static review HTML and local server**

Create `src/asset_factory/review.py`:

```python
from __future__ import annotations

import html
import http.server
import socketserver
from pathlib import Path


def build_review_html(
    *,
    asset_id: str,
    concept_image: str,
    glb_path: str,
    thumbnail: str,
    qa_passed: bool,
    warnings: list[str],
) -> str:
    warning_items = "".join(f"<li>{html.escape(warning)}</li>" for warning in warnings)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Review {html.escape(asset_id)}</title>
  <style>
    body {{ margin: 0; font-family: Inter, system-ui, sans-serif; background: #f6f7f9; color: #16202a; }}
    header {{ padding: 20px 28px; background: white; border-bottom: 1px solid #d7dde5; }}
    main {{ display: grid; grid-template-columns: 360px 1fr; gap: 24px; padding: 24px; }}
    img {{ max-width: 100%; border: 1px solid #d7dde5; background: white; }}
    #viewer {{ min-height: 560px; background: #111827; border-radius: 8px; overflow: hidden; }}
    .panel {{ background: white; border: 1px solid #d7dde5; border-radius: 8px; padding: 16px; }}
    .status {{ font-weight: 700; color: {"#047857" if qa_passed else "#b91c1c"}; }}
    button {{ margin-right: 8px; padding: 8px 12px; border: 1px solid #aab4c0; background: #fff; border-radius: 6px; }}
  </style>
</head>
<body>
  <header>
    <h1>{html.escape(asset_id)}</h1>
    <div class="status">QA passed: {str(qa_passed)}</div>
  </header>
  <main>
    <aside class="panel">
      <h2>Concept Image</h2>
      <img src="../{html.escape(concept_image)}" alt="Concept image">
      <h2>Warnings</h2>
      <ul>{warning_items}</ul>
      <h2>Review</h2>
      <button>Approve</button>
      <button>Needs changes</button>
      <button>Reject</button>
      <p>Review state editing is stored through the CLI in v1.</p>
    </aside>
    <section class="panel">
      <h2>3D Preview</h2>
      <div id="viewer"></div>
      <p>GLB path: {html.escape(glb_path)}</p>
      <p>Thumbnail: {html.escape(thumbnail)}</p>
    </section>
  </main>
  <script type="module">
    import * as THREE from 'https://cdn.jsdelivr.net/npm/three@0.165.0/build/three.module.js';
    import {{ GLTFLoader }} from 'https://cdn.jsdelivr.net/npm/three@0.165.0/examples/jsm/loaders/GLTFLoader.js';
    const viewer = document.getElementById('viewer');
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x111827);
    const camera = new THREE.PerspectiveCamera(45, viewer.clientWidth / viewer.clientHeight, 0.1, 100);
    camera.position.set(2.5, 2, 2.5);
    const renderer = new THREE.WebGLRenderer({{ antialias: true }});
    renderer.setSize(viewer.clientWidth, viewer.clientHeight);
    viewer.appendChild(renderer.domElement);
    scene.add(new THREE.HemisphereLight(0xffffff, 0x223344, 3));
    const loader = new GLTFLoader();
    loader.load('../{html.escape(glb_path)}', gltf => {{
      scene.add(gltf.scene);
      renderer.setAnimationLoop(() => {{
        gltf.scene.rotation.y += 0.01;
        renderer.render(scene, camera);
      }});
    }});
  </script>
</body>
</html>
"""


def write_review_html(
    run_dir: Path,
    *,
    asset_id: str,
    concept_image: str,
    glb_path: str,
    thumbnail: str,
    qa_passed: bool,
    warnings: list[str],
) -> Path:
    reports_dir = run_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    path = reports_dir / "review.html"
    path.write_text(
        build_review_html(
            asset_id=asset_id,
            concept_image=concept_image,
            glb_path=glb_path,
            thumbnail=thumbnail,
            qa_passed=qa_passed,
            warnings=warnings,
        ),
        encoding="utf-8",
    )
    return path


def serve_review(run_dir: Path, port: int) -> None:
    handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("", port), handler) as httpd:
        print(f"Serving review for {run_dir} at http://localhost:{port}/reports/review.html")
        httpd.serve_forever()
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:

```bash
pytest tests/test_review.py -v
```

Expected: PASS.

- [ ] **Step 5: Integrate review HTML into the pipeline**

Modify `src/asset_factory/pipeline.py` after QA report creation and before export:

```python
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
```

Then change the `apply_pipeline_outputs` call argument from:

```python
        review_html=None,
```

to:

```python
        review_html=review_html,
```

- [ ] **Step 6: Run review and pipeline tests**

Run:

```bash
pytest tests/test_review.py tests/test_pipeline.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/asset_factory/review.py src/asset_factory/pipeline.py tests/test_review.py
git commit -m "feat: generate local asset review dashboard"
```

## Task 13: Local TRELLIS.2 Command Runner

**Files:**
- Create: `src/asset_factory/runners/trellis.py`
- Create: `tests/test_trellis_runner.py`

- [ ] **Step 1: Write failing TRELLIS runner command tests**

Create `tests/test_trellis_runner.py`:

```python
import os
from pathlib import Path

from asset_factory.runners.base import RunnerRequest
from asset_factory.runners.trellis import TrellisCommandRunner


def test_trellis_runner_requires_env(monkeypatch):
    monkeypatch.delenv("TRELLIS2_COMMAND", raising=False)

    try:
        TrellisCommandRunner.from_env()
    except RuntimeError as exc:
        assert "TRELLIS2_COMMAND" in str(exc)
    else:
        raise AssertionError("TrellisCommandRunner.from_env should require TRELLIS2_COMMAND")


def test_trellis_runner_executes_command_template(tmp_path: Path, monkeypatch):
    script = tmp_path / "fake_trellis.py"
    script.write_text(
        """
from pathlib import Path
import sys
out = Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
(out / "raw.glb").write_bytes(b"glTF-fake")
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setenv("TRELLIS2_COMMAND", f"python {script} {{image}} {{output}}")
    image = tmp_path / "concept.png"
    image.write_bytes(b"png")

    runner = TrellisCommandRunner.from_env()
    result = runner.run(RunnerRequest(concept_image=image, output_dir=tmp_path / "trellis"))

    assert result.raw_glb_path.read_bytes() == b"glTF-fake"
    assert result.report_path.exists()
    assert result.runner_type == "trellis"
    assert result.success is True
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
pytest tests/test_trellis_runner.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'asset_factory.runners.trellis'`.

- [ ] **Step 3: Implement TRELLIS command runner**

Create `src/asset_factory/runners/trellis.py`:

```python
from __future__ import annotations

import json
import os
import shlex
import subprocess
from datetime import UTC, datetime

from asset_factory.runners.base import RunnerRequest, RunnerResult


class TrellisCommandRunner:
    runner_type = "trellis"
    runner_version = "trellis2-command"

    def __init__(self, command_template: str):
        self.command_template = command_template

    @classmethod
    def from_env(cls) -> "TrellisCommandRunner":
        command_template = os.environ.get("TRELLIS2_COMMAND")
        if not command_template:
            raise RuntimeError(
                "TRELLIS2_COMMAND is required. Example: "
                "TRELLIS2_COMMAND='python /path/to/trellis_generate.py {image} {output}'"
            )
        return cls(command_template)

    def run(self, request: RunnerRequest) -> RunnerResult:
        request.output_dir.mkdir(parents=True, exist_ok=True)
        raw_glb_path = request.output_dir / "raw.glb"
        report_path = request.output_dir / "raw_report.json"
        started_at = datetime.now(tz=UTC)
        command = self.command_template.format(
            image=str(request.concept_image),
            output=str(request.output_dir),
            resolution=str(request.resolution),
        )
        completed = subprocess.run(
            shlex.split(command),
            check=False,
            capture_output=True,
            text=True,
        )
        ended_at = datetime.now(tz=UTC)
        success = completed.returncode == 0 and raw_glb_path.exists()
        report = {
            "runner_type": self.runner_type,
            "runner_version": self.runner_version,
            "resolution": request.resolution,
            "command": command,
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "started_at": started_at.isoformat(),
            "ended_at": ended_at.isoformat(),
            "raw_glb": str(raw_glb_path),
            "success": success,
        }
        report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
        if not success:
            raise RuntimeError(f"TRELLIS command failed; see {report_path}")
        return RunnerResult(
            raw_glb_path=raw_glb_path,
            report_path=report_path,
            runner_type=self.runner_type,
            runner_version=self.runner_version,
            success=True,
        )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:

```bash
pytest tests/test_trellis_runner.py -v
```

Expected: PASS.

- [ ] **Step 5: Run CLI import test to verify trellis import path**

Run:

```bash
pytest tests/test_import.py tests/test_cli.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/asset_factory/runners/trellis.py tests/test_trellis_runner.py
git commit -m "feat: add local trellis command runner"
```

## Task 14: Seed Science Asset Specs

**Files:**
- Create: `assets/seeds/chloroplast_conceptual.yaml`
- Create: `assets/seeds/plant_cell_conceptual.yaml`
- Create: `assets/seeds/mitochondrion_conceptual.yaml`
- Create: `assets/seeds/lever_conceptual.yaml`
- Create: `assets/seeds/pulley_conceptual.yaml`
- Create: `assets/seeds/trilobite_fossil_realistic.yaml`
- Create: `assets/seeds/basalt_rock_realistic.yaml`
- Create: `assets/seeds/quartz_crystal_realistic.yaml`
- Create: `assets/seeds/human_tooth_cross_section_realistic.yaml`
- Create: `assets/seeds/fern_spores_realistic.yaml`
- Create: `tests/test_seed_specs.py`
- Modify: `README.md`

- [ ] **Step 1: Write failing seed validation test**

Create `tests/test_seed_specs.py`:

```python
from pathlib import Path

from asset_factory.specs import load_asset_spec


def test_all_seed_specs_validate():
    seed_paths = sorted(Path("assets/seeds").glob("*.yaml"))

    assert len(seed_paths) == 10
    for path in seed_paths:
        spec = load_asset_spec(path)
        assert spec.id
        assert spec.learning_goal
        assert spec.exports
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
pytest tests/test_seed_specs.py -v
```

Expected: FAIL because `assets/seeds` does not exist.

- [ ] **Step 3: Add the 10 seed specs**

Create `assets/seeds/chloroplast_conceptual.yaml`:

```yaml
id: chloroplast_001
subject: biology
object: chloroplast
grade_band: "6-8"
style: conceptual
learning_goal: Identify the outer membrane, stroma, thylakoids, and grana.
exports: ["web", "unity", "unreal"]
qa:
  max_triangles: 150000
  max_glb_mb: 25
```

Create `assets/seeds/plant_cell_conceptual.yaml`:

```yaml
id: plant_cell_001
subject: biology
object: plant cell
grade_band: "6-8"
style: conceptual
learning_goal: Identify the cell wall, nucleus, chloroplasts, vacuole, and cytoplasm.
exports: ["web", "unity", "unreal"]
qa:
  max_triangles: 180000
  max_glb_mb: 30
```

Create `assets/seeds/mitochondrion_conceptual.yaml`:

```yaml
id: mitochondrion_001
subject: biology
object: mitochondrion
grade_band: "6-8"
style: conceptual
learning_goal: Identify the outer membrane, inner membrane, matrix, and cristae.
exports: ["web", "unity", "unreal"]
qa:
  max_triangles: 150000
  max_glb_mb: 25
```

Create `assets/seeds/lever_conceptual.yaml`:

```yaml
id: lever_001
subject: physics
object: lever
grade_band: "3-5"
style: conceptual
learning_goal: Identify the fulcrum, effort, load, and lever arm.
exports: ["web", "unity", "unreal"]
qa:
  max_triangles: 100000
  max_glb_mb: 20
```

Create `assets/seeds/pulley_conceptual.yaml`:

```yaml
id: pulley_001
subject: physics
object: pulley
grade_band: "3-5"
style: conceptual
learning_goal: Identify the wheel, axle, rope, and load direction.
exports: ["web", "unity", "unreal"]
qa:
  max_triangles: 120000
  max_glb_mb: 22
```

Create `assets/seeds/trilobite_fossil_realistic.yaml`:

```yaml
id: trilobite_fossil_001
subject: earth_science
object: trilobite fossil
grade_band: "6-8"
style: realistic
learning_goal: Recognize fossil body segmentation and preserved exoskeleton structure.
exports: ["web", "unity", "unreal"]
qa:
  max_triangles: 180000
  max_glb_mb: 35
```

Create `assets/seeds/basalt_rock_realistic.yaml`:

```yaml
id: basalt_rock_001
subject: earth_science
object: basalt rock sample
grade_band: "6-8"
style: realistic
learning_goal: Recognize fine-grained igneous rock texture and dark basalt coloration.
exports: ["web", "unity", "unreal"]
qa:
  max_triangles: 160000
  max_glb_mb: 30
```

Create `assets/seeds/quartz_crystal_realistic.yaml`:

```yaml
id: quartz_crystal_001
subject: earth_science
object: quartz crystal
grade_band: "6-8"
style: realistic
learning_goal: Recognize hexagonal crystal form and translucent mineral appearance.
exports: ["web", "unity", "unreal"]
qa:
  max_triangles: 160000
  max_glb_mb: 30
```

Create `assets/seeds/human_tooth_cross_section_realistic.yaml`:

```yaml
id: human_tooth_cross_section_001
subject: biology
object: human tooth cross-section
grade_band: "6-8"
style: realistic
learning_goal: Identify enamel, dentin, pulp, crown, and root in a simplified tooth cross-section.
exports: ["web", "unity", "unreal"]
qa:
  max_triangles: 180000
  max_glb_mb: 35
```

Create `assets/seeds/fern_spores_realistic.yaml`:

```yaml
id: fern_spores_001
subject: biology
object: fern leaf underside with spores
grade_band: "6-8"
style: realistic
learning_goal: Recognize sori as spore-producing structures on the underside of fern leaves.
exports: ["web", "unity", "unreal"]
qa:
  max_triangles: 180000
  max_glb_mb: 35
```

- [ ] **Step 4: Document seed usage**

Append to `README.md`:

````markdown

## Seed Specs

The `assets/seeds` directory contains 10 initial science specs:

- 5 conceptual assets for biology and physics.
- 5 realistic assets for biology and earth science.

Generate one with the mock runner:

```bash
asset-factory generate assets/seeds/chloroplast_conceptual.yaml --runner mock
```

Generate one with TRELLIS.2 once `TRELLIS2_COMMAND` and OpenAI credentials are configured:

```bash
TRELLIS2_COMMAND='python /path/to/trellis_generate.py {image} {output}' \
asset-factory generate assets/seeds/chloroplast_conceptual.yaml --runner trellis
```
````

- [ ] **Step 5: Run seed tests**

Run:

```bash
pytest tests/test_seed_specs.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add assets/seeds README.md tests/test_seed_specs.py
git commit -m "feat: add initial science seed specs"
```

## Task 15: Final Verification and Documentation Pass

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Run all tests**

Run:

```bash
pytest -v
```

Expected: PASS.

- [ ] **Step 2: Run lint**

Run:

```bash
ruff check .
```

Expected: PASS.

- [ ] **Step 3: Run a full mock generation manually**

Run:

```bash
asset-factory generate assets/seeds/chloroplast_conceptual.yaml --runner mock
```

Expected: prints `Generated run: runs/chloroplast_001/<timestamp>` and creates a run directory containing `image/concept.png`, `trellis/raw.glb`, `optimize/asset.glb`, `previews/thumbnail.png`, `previews/turntable.webm`, `exports/web/asset.glb`, `exports/unity/asset.glb`, `exports/unreal/asset.glb`, `reports/qa.json`, `reports/review.html`, and `manifest.json`.

- [ ] **Step 4: Inspect the generated manifest**

Run:

```bash
python -m json.tool runs/chloroplast_001/*/manifest.json | head -80
```

Expected: JSON includes `asset.id` of `chloroplast_001`, `education.style` of `conceptual`, `provenance.runner_type` of `mock`, `qa.passed` of `true`, and export paths for `web`, `unity`, and `unreal`.

- [ ] **Step 5: Update README with verified commands**

Append this section to `README.md`, replacing the timestamp example with the timestamp produced during Step 3:

````markdown

## Verified Local Workflow

Mock generation works without OpenAI credentials or TRELLIS.2:

```bash
asset-factory generate assets/seeds/chloroplast_conceptual.yaml --runner mock
```

Expected output:

```text
Generated run: runs/chloroplast_001/<timestamp>
```

The generated run contains:

```text
image/concept.png
image/prompt.txt
trellis/raw.glb
trellis/raw_report.json
optimize/asset.glb
previews/thumbnail.png
previews/turntable.webm
exports/web/asset.glb
exports/unity/asset.glb
exports/unreal/asset.glb
reports/qa.json
reports/review.html
manifest.json
```

Inspect the manifest:

```bash
python -m json.tool runs/chloroplast_001/<timestamp>/manifest.json | head -80
```

The manifest should include:

```json
{
  "asset": {
    "id": "chloroplast_001"
  },
  "education": {
    "style": "conceptual"
  },
  "provenance": {
    "runner_type": "mock"
  },
  "qa": {
    "passed": true
  }
}
```

OpenAI + TRELLIS.2 generation uses the same spec and run layout:

```bash
export OPENAI_API_KEY="sk-your-development-key"
export TRELLIS2_COMMAND='python /path/to/trellis_generate.py {image} {output}'
asset-factory generate assets/seeds/chloroplast_conceptual.yaml --runner trellis
```
````

- [ ] **Step 6: Commit**

```bash
git add README.md
git commit -m "docs: document verified asset factory workflow"
```
