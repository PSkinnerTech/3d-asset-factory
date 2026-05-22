# Export Formats Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add GLB/STL export format selection so each destination profile can package a textured GLB, a best-effort CAD/3D-printing STL derivative, or both.

**Architecture:** Keep `ExportProfile` as the destination model (`web`, `unity`, `unreal`) and add a separate `ExportFormat` model (`glb`, `stl`). Put STL conversion and print-readiness reporting in a focused `src/asset_factory/stl.py` module. Update exports, manifests, CLI package validation, tests, and README without changing TRELLIS generation or QA semantics.

**Tech Stack:** Python 3.11, Typer, Pydantic v2, Trimesh, PyYAML, pytest, Ruff.

---

## File Structure

- Modify `src/asset_factory/models.py`: add `ExportFormat`, `AssetSpec.export_formats`, validators, and STL manifest fields.
- Modify `src/asset_factory/specs.py`: no parser changes expected because Pydantic validates the new optional field.
- Create `src/asset_factory/stl.py`: convert optimized GLB to STL and write `stl_report.json`.
- Modify `src/asset_factory/exports.py`: accept export formats, copy GLB conditionally, generate STL conditionally, and write format-aware import notes.
- Modify `src/asset_factory/manifest.py`: write package-local manifests that reflect package formats.
- Modify `src/asset_factory/pipeline.py`: pass `spec.export_formats` into export generation and package manifest writing.
- Modify `src/asset_factory/cli.py`: add `--format`, dynamic package-completeness checks, and format-aware package manifest sync.
- Modify `tests/test_specs.py`: cover `export_formats` defaults and validation.
- Modify `tests/test_seed_specs.py`: confirm seed specs default to GLB.
- Modify `tests/test_exports.py`: cover GLB-only, STL-only, and dual-format packages.
- Modify `tests/test_cli.py`: cover `--format stl`, package sync, failed QA behavior, and stale package filtering.
- Modify `tests/test_pipeline.py`: cover pipeline-generated dual-format exports.
- Modify `README.md`: document `export_formats` and CLI `--format`.

## Task 1: Add Export Format Model

**Files:**
- Modify: `src/asset_factory/models.py`
- Test: `tests/test_specs.py`
- Test: `tests/test_seed_specs.py`

- [ ] **Step 1: Write failing spec tests**

Add `ExportFormat` imports and assertions in `tests/test_specs.py`:

```python
from asset_factory.models import ExportFormat, ExportProfile, ScienceSubject, StyleMode
```

Update `write_asset_spec` to accept optional extra spec text:

```python
def write_asset_spec(
    path: Path,
    *,
    asset_id: str = "chloroplast_001",
    subject: str = "biology",
    object_name: str = "chloroplast",
    grade_band: str = "6-8",
    style: str = "conceptual",
    learning_goal: str = "Identify the outer membrane, stroma, thylakoids, and grana.",
    exports: str = '["web", "unity", "unreal"]',
    extra_fields: str = "",
    max_triangles: int = 150000,
    max_glb_mb: int = 25,
) -> None:
    path.write_text(
        f"""
id: {asset_id!r}
subject: {subject}
object: {object_name!r}
grade_band: {grade_band!r}
style: {style}
learning_goal: {learning_goal!r}
exports: {exports}
{extra_fields}
qa:
  max_triangles: {max_triangles}
  max_glb_mb: {max_glb_mb}
""".strip(),
        encoding="utf-8",
    )
```

Add these tests:

```python
def test_defaults_export_formats_to_glb(tmp_path: Path):
    spec_path = tmp_path / "asset.yaml"
    write_asset_spec(spec_path)

    spec = load_asset_spec(spec_path)

    assert spec.export_formats == [ExportFormat.GLB]


def test_accepts_glb_and_stl_export_formats(tmp_path: Path):
    spec_path = tmp_path / "asset.yaml"
    write_asset_spec(spec_path, extra_fields='export_formats: ["glb", "stl"]')

    spec = load_asset_spec(spec_path)

    assert spec.export_formats == [ExportFormat.GLB, ExportFormat.STL]


def test_rejects_empty_export_formats(tmp_path: Path):
    spec_path = tmp_path / "asset.yaml"
    write_asset_spec(spec_path, extra_fields="export_formats: []")

    with pytest.raises(ValidationError, match="at least one export format"):
        load_asset_spec(spec_path)


def test_rejects_unknown_export_format(tmp_path: Path):
    spec_path = tmp_path / "asset.yaml"
    write_asset_spec(spec_path, extra_fields='export_formats: ["obj"]')

    with pytest.raises(ValidationError):
        load_asset_spec(spec_path)
```

Update `tests/test_seed_specs.py`:

```python
from asset_factory.models import ExportFormat, ExportProfile
```

Inside `test_all_seed_specs_validate`, add:

```python
assert spec.export_formats == [ExportFormat.GLB]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/test_specs.py tests/test_seed_specs.py -q
```

Expected: FAIL with an import or attribute error for `ExportFormat` / `export_formats`.

- [ ] **Step 3: Implement the model changes**

In `src/asset_factory/models.py`, add after `ExportProfile`:

```python
class ExportFormat(StrEnum):
    GLB = "glb"
    STL = "stl"
```

Update `AssetSpec`:

```python
class AssetSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    id: str = Field(min_length=1, pattern=r"^[a-z0-9][a-z0-9_\\-]*$")
    subject: ScienceSubject
    object: str = Field(min_length=1)
    grade_band: str = Field(min_length=1)
    style: StyleMode
    learning_goal: str = Field(min_length=1)
    exports: list[ExportProfile]
    export_formats: list[ExportFormat] = Field(default_factory=lambda: [ExportFormat.GLB])
    qa: QaThresholds
    source_path: Path | None = None

    @field_validator("exports")
    @classmethod
    def require_exports(cls, value: list[ExportProfile]) -> list[ExportProfile]:
        if not value:
            raise ValueError("asset spec must request at least one export")
        return value

    @field_validator("export_formats")
    @classmethod
    def require_export_formats(cls, value: list[ExportFormat]) -> list[ExportFormat]:
        if not value:
            raise ValueError("asset spec must request at least one export format")
        return value
```

Update `FileManifest`:

```python
class FileManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    manifest: str = "manifest.json"
    concept_image: str | None = None
    raw_glb: str | None = None
    optimized_glb: str | None = None
    stl: str | None = None
    stl_report: str | None = None
    thumbnail: str | None = None
    turntable: str | None = None
    qa_report: str | None = None
    review_html: str | None = None
    exports: dict[ExportProfile, str] = Field(default_factory=dict)
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
.venv/bin/python -m pytest tests/test_specs.py tests/test_seed_specs.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/asset_factory/models.py tests/test_specs.py tests/test_seed_specs.py
git commit -m "Add export format model"
```

## Task 2: Add STL Conversion And Report Module

**Files:**
- Create: `src/asset_factory/stl.py`
- Test: `tests/test_stl.py`

- [ ] **Step 1: Write failing STL tests**

Create `tests/test_stl.py`:

```python
import json
from pathlib import Path

import trimesh

from asset_factory.stl import export_stl


def write_box_glb(path: Path) -> None:
    mesh = trimesh.creation.box(extents=(1, 1, 1))
    path.parent.mkdir(parents=True, exist_ok=True)
    mesh.export(path)


def write_plane_glb(path: Path) -> None:
    mesh = trimesh.Trimesh(
        vertices=[
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [1.0, 1.0, 0.0],
            [0.0, 1.0, 0.0],
        ],
        faces=[[0, 1, 2], [0, 2, 3]],
        process=False,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    mesh.export(path)


def test_export_stl_writes_binary_stl_and_report(tmp_path: Path):
    source_glb = tmp_path / "optimize" / "asset.glb"
    output_stl = tmp_path / "exports" / "web" / "asset.stl"
    report_path = tmp_path / "exports" / "web" / "stl_report.json"
    write_box_glb(source_glb)

    report = export_stl(source_glb, output_stl, report_path)

    report_json = json.loads(report_path.read_text(encoding="utf-8"))
    assert output_stl.is_file()
    assert output_stl.stat().st_size > 0
    assert report.exported is True
    assert report.output_stl == str(output_stl)
    assert report_json["exported"] is True
    assert report_json["triangle_count"] == 12
    assert report_json["body_count"] == 1
    assert report_json["is_watertight"] is True
    assert report_json["is_volume"] is True
    assert any("geometry-only" in warning for warning in report_json["warnings"])


def test_export_stl_warns_for_non_watertight_mesh_without_failing(tmp_path: Path):
    source_glb = tmp_path / "optimize" / "asset.glb"
    output_stl = tmp_path / "exports" / "web" / "asset.stl"
    report_path = tmp_path / "exports" / "web" / "stl_report.json"
    write_plane_glb(source_glb)

    report = export_stl(source_glb, output_stl, report_path)

    assert output_stl.is_file()
    assert report.exported is True
    assert report.is_watertight is False
    assert report.is_volume is False
    assert any("not watertight" in warning for warning in report.warnings)
    assert any("not a valid volume" in warning for warning in report.warnings)
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/test_stl.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'asset_factory.stl'`.

- [ ] **Step 3: Implement STL export module**

Create `src/asset_factory/stl.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

import trimesh
from pydantic import BaseModel, ConfigDict
from trimesh import Trimesh


GEOMETRY_ONLY_WARNING = (
    "STL is geometry-only; materials, colors, and textures are not preserved."
)


class StlReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    exported: bool
    source_glb: str
    output_stl: str
    triangle_count: int
    body_count: int
    is_watertight: bool
    is_winding_consistent: bool
    is_volume: bool
    warnings: list[str]


def export_stl(source_glb: Path, output_stl: Path, report_path: Path) -> StlReport:
    mesh = _load_mesh(source_glb)
    if len(mesh.faces) == 0:
        raise ValueError(f"Cannot export STL because {source_glb} has no geometry")

    output_stl.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    mesh.export(output_stl, file_type="stl")
    if not output_stl.exists() or output_stl.stat().st_size == 0:
        raise RuntimeError(f"STL export produced no file at {output_stl}")

    report = _build_report(mesh, source_glb, output_stl)
    report_path.write_text(
        json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return report


def _load_mesh(source_glb: Path) -> Trimesh:
    loaded = trimesh.load(source_glb, force="mesh")
    if isinstance(loaded, Trimesh):
        return loaded
    raise ValueError(f"Cannot export STL because {source_glb} did not load as a mesh")


def _build_report(mesh: Trimesh, source_glb: Path, output_stl: Path) -> StlReport:
    bodies = list(mesh.split(only_watertight=False))
    body_count = len(bodies) or 1
    warnings = [GEOMETRY_ONLY_WARNING]
    if not mesh.is_watertight:
        warnings.append("Mesh is not watertight; 3D printing may require repair.")
    if not mesh.is_winding_consistent:
        warnings.append("Mesh winding is inconsistent; CAD tools may need to repair normals.")
    if not mesh.is_volume:
        warnings.append("Mesh is not a valid volume; 3D printing may require repair.")
    if body_count > 1:
        warnings.append(f"Mesh has {body_count} disconnected bodies; printability needs review.")

    return StlReport(
        exported=True,
        source_glb=str(source_glb),
        output_stl=str(output_stl),
        triangle_count=len(mesh.faces),
        body_count=body_count,
        is_watertight=bool(mesh.is_watertight),
        is_winding_consistent=bool(mesh.is_winding_consistent),
        is_volume=bool(mesh.is_volume),
        warnings=warnings,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
.venv/bin/python -m pytest tests/test_stl.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/asset_factory/stl.py tests/test_stl.py
git commit -m "Add STL export reporting"
```

## Task 3: Make Export Packages Format-Aware

**Files:**
- Modify: `src/asset_factory/exports.py`
- Test: `tests/test_exports.py`

- [ ] **Step 1: Write failing export package tests**

Update imports in `tests/test_exports.py`:

```python
from asset_factory.models import ExportFormat, ExportProfile
```

Replace `test_exports_web_unity_and_unreal_profiles` with:

```python
def test_exports_glb_only_by_default(tmp_path: Path):
    run_dir = tmp_path / "runs" / "demo" / "20260520T120000Z"
    write_artifacts(run_dir)

    results = export_profiles(run_dir, [ExportProfile.WEB])

    export_dir = results[ExportProfile.WEB]
    assert (export_dir / "asset.glb").read_bytes() == b"glTF-demo"
    assert not (export_dir / "asset.stl").exists()
    assert not (export_dir / "stl_report.json").exists()
    assert (export_dir / "thumbnail.png").exists()
    assert (export_dir / "turntable.webm").exists()
    assert (export_dir / "qa.json").exists()
    notes = (export_dir / "IMPORT_NOTES.md").read_text(encoding="utf-8")
    assert "Use asset.glb" in notes


def test_exports_stl_only_package(tmp_path: Path):
    run_dir = tmp_path / "runs" / "demo" / "20260520T120000Z"
    write_mesh_artifacts(run_dir)

    results = export_profiles(run_dir, [ExportProfile.WEB], formats=[ExportFormat.STL])

    export_dir = results[ExportProfile.WEB]
    assert not (export_dir / "asset.glb").exists()
    assert (export_dir / "asset.stl").is_file()
    assert (export_dir / "stl_report.json").is_file()
    assert (export_dir / "thumbnail.png").exists()
    assert (export_dir / "turntable.webm").exists()
    assert (export_dir / "qa.json").exists()
    notes = (export_dir / "IMPORT_NOTES.md").read_text(encoding="utf-8")
    assert "geometry-only" in notes
    assert "3D printing" in notes


def test_exports_glb_and_stl_package(tmp_path: Path):
    run_dir = tmp_path / "runs" / "demo" / "20260520T120000Z"
    write_mesh_artifacts(run_dir)

    results = export_profiles(
        run_dir,
        [ExportProfile.WEB, ExportProfile.UNITY, ExportProfile.UNREAL],
        formats=[ExportFormat.GLB, ExportFormat.STL],
    )

    assert set(results) == {ExportProfile.WEB, ExportProfile.UNITY, ExportProfile.UNREAL}
    for profile, export_dir in results.items():
        assert (export_dir / "asset.glb").exists()
        assert (export_dir / "asset.stl").exists()
        assert (export_dir / "stl_report.json").exists()
        assert not (export_dir / "manifest.json").exists()
        notes = (export_dir / "IMPORT_NOTES.md").read_text(encoding="utf-8")
        assert profile.value in notes
        assert "asset.glb" in notes
        assert "asset.stl" in notes
```

Add this helper above the tests:

```python
def write_mesh_artifacts(run_dir: Path) -> None:
    write_artifacts(run_dir)
    mesh = trimesh.creation.box(extents=(1, 1, 1))
    mesh.export(run_dir / "optimize" / "asset.glb")
```

Add `import trimesh` at the top.

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/test_exports.py -q
```

Expected: FAIL because `ExportFormat` support and `formats=` are not wired into `export_profiles`.

- [ ] **Step 3: Implement format-aware exports**

Update `src/asset_factory/exports.py`:

```python
from __future__ import annotations

import shutil
from pathlib import Path

from asset_factory.models import ExportFormat, ExportProfile
from asset_factory.stl import export_stl


COMMON_EXPORT_FILES = (
    ("previews/thumbnail.png", "thumbnail.png"),
    ("previews/turntable.webm", "turntable.webm"),
    ("reports/qa.json", "qa.json"),
)


def export_profiles(
    run_dir: Path,
    profiles: list[ExportProfile],
    *,
    formats: list[ExportFormat] | None = None,
) -> dict[ExportProfile, Path]:
    selected_formats = formats or [ExportFormat.GLB]
    results: dict[ExportProfile, Path] = {}
    for profile in profiles:
        export_dir = run_dir / "exports" / profile.value
        export_dir.mkdir(parents=True, exist_ok=True)
        _write_format_artifacts(run_dir, export_dir, selected_formats)
        for source_name, target_name in COMMON_EXPORT_FILES:
            source = run_dir / source_name
            if not source.exists():
                raise FileNotFoundError(f"Cannot export {profile.value}: missing {source}")
            shutil.copy2(source, export_dir / target_name)
        (export_dir / "IMPORT_NOTES.md").write_text(
            import_notes(profile, selected_formats),
            encoding="utf-8",
        )
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
    else:
        (export_dir / "asset.stl").unlink(missing_ok=True)
        (export_dir / "stl_report.json").unlink(missing_ok=True)


def import_notes(profile: ExportProfile, formats: list[ExportFormat] | None = None) -> str:
    selected_formats = formats or [ExportFormat.GLB]
    lines = [f"# {profile.value} import notes", ""]
    if ExportFormat.GLB in selected_formats:
        lines.append(
            "Use asset.glb as the textured runtime asset for web, Unity, Unreal, "
            "and learning-app rendering."
        )
    if ExportFormat.STL in selected_formats:
        lines.append(
            "Use asset.stl only as a geometry-only CAD/3D-printing derivative. "
            "STL does not preserve TRELLIS textures, materials, vertex colors, "
            "PBR values, or opacity. Review stl_report.json before printing."
        )
    lines.append("Keep manifest.json with the asset so review state, learning goal, and QA metrics remain visible to build tooling.")
    return "\\n\\n".join(lines) + "\\n"
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
.venv/bin/python -m pytest tests/test_exports.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/asset_factory/exports.py tests/test_exports.py
git commit -m "Support GLB and STL export formats"
```

## Task 4: Write Format-Aware Package Manifests

**Files:**
- Modify: `src/asset_factory/manifest.py`
- Test: `tests/test_pipeline.py`

- [ ] **Step 1: Write failing manifest tests**

Update `tests/test_pipeline.py` imports:

```python
from asset_factory.models import (
    AssetSpec,
    ExportFormat,
    ExportProfile,
    QaThresholds,
    ScienceSubject,
    StyleMode,
)
```

Update `make_spec` to request both formats:

```python
def make_spec() -> AssetSpec:
    return AssetSpec(
        id="pulley_001",
        subject=ScienceSubject.PHYSICS,
        object="pulley",
        grade_band="3-5",
        style=StyleMode.CONCEPTUAL,
        learning_goal="Identify the wheel, axle, rope, and load.",
        exports=[ExportProfile.WEB, ExportProfile.UNITY],
        export_formats=[ExportFormat.GLB, ExportFormat.STL],
        qa=QaThresholds(max_triangles=150000, max_glb_mb=25),
    )
```

In `test_generate_asset_creates_complete_run`, add:

```python
assert (run_dir / "exports" / "web" / "asset.stl").exists()
assert (run_dir / "exports" / "web" / "stl_report.json").exists()
assert (run_dir / "exports" / "unity" / "asset.stl").exists()
assert (run_dir / "exports" / "unity" / "stl_report.json").exists()
```

Inside the package manifest loop, add:

```python
assert exported_manifest.files.stl == "asset.stl"
assert exported_manifest.files.stl_report == "stl_report.json"
```

Add a separate test:

```python
def test_generate_asset_glb_only_package_manifest_omits_stl(tmp_path: Path):
    spec = make_spec().model_copy(update={"export_formats": [ExportFormat.GLB]})

    result = generate_asset(
        spec=spec,
        root_dir=tmp_path,
        image_generator=FakeImageGenerator(),
        runner=MockRunner(),
        timestamp="20260520T120000Z",
    )

    web_manifest = read_manifest(result.run_dir / "exports" / "web" / "manifest.json")
    assert web_manifest.files.optimized_glb == "asset.glb"
    assert web_manifest.files.stl is None
    assert web_manifest.files.stl_report is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/test_pipeline.py -q
```

Expected: FAIL because package manifests do not know which formats were exported.

- [ ] **Step 3: Update manifest helpers**

Modify imports in `src/asset_factory/manifest.py`:

```python
from asset_factory.models import (
    AssetIdentity,
    AssetManifest,
    AssetSpec,
    EducationMetadata,
    ExportFormat,
    ExportProfile,
    FileManifest,
    Provenance,
    QaSummary,
    ReviewInfo,
    ReviewState,
)
```

Replace `package_local_manifest` and `write_package_manifest`:

```python
def package_local_manifest(
    manifest: AssetManifest,
    profile: ExportProfile,
    formats: list[ExportFormat] | None = None,
) -> AssetManifest:
    selected_formats = formats or [ExportFormat.GLB]
    package_manifest = manifest.model_copy(deep=True)
    package_manifest.files.concept_image = None
    package_manifest.files.raw_glb = None
    package_manifest.files.optimized_glb = (
        "asset.glb" if ExportFormat.GLB in selected_formats else None
    )
    package_manifest.files.stl = "asset.stl" if ExportFormat.STL in selected_formats else None
    package_manifest.files.stl_report = (
        "stl_report.json" if ExportFormat.STL in selected_formats else None
    )
    package_manifest.files.thumbnail = "thumbnail.png"
    package_manifest.files.turntable = "turntable.webm"
    package_manifest.files.qa_report = "qa.json"
    package_manifest.files.review_html = None
    package_manifest.files.exports = {profile: "."}
    return package_manifest


def write_package_manifest(
    path: Path,
    manifest: AssetManifest,
    profile: ExportProfile,
    formats: list[ExportFormat] | None = None,
) -> None:
    write_manifest(path, package_local_manifest(manifest, profile, formats))
```

In `apply_pipeline_outputs`, clear root STL fields because STL paths are package-local derivatives:

```python
manifest.files.stl = None
manifest.files.stl_report = None
```

Add those lines before setting `manifest.files.exports`.

- [ ] **Step 4: Update pipeline to pass formats**

In `src/asset_factory/pipeline.py`, update the export call:

```python
exports = (
    export_profiles(layout.run_dir, spec.exports, formats=spec.export_formats)
    if qa_summary.passed
    else {}
)
```

Update `_write_export_manifests` signature and implementation:

```python
def _write_export_manifests(
    exports: dict[ExportProfile, Path],
    manifest: AssetManifest,
    formats: list[ExportFormat],
) -> None:
    for profile, export_dir in exports.items():
        write_package_manifest(export_dir / "manifest.json", manifest, profile, formats)
```

Update the call:

```python
_write_export_manifests(exports, manifest, spec.export_formats)
```

Import `ExportFormat` from `asset_factory.models`.

- [ ] **Step 5: Run tests to verify they pass**

Run:

```bash
.venv/bin/python -m pytest tests/test_pipeline.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/asset_factory/manifest.py src/asset_factory/pipeline.py tests/test_pipeline.py
git commit -m "Write package manifests for export formats"
```

## Task 5: Add CLI Format Selection And Dynamic Package Validation

**Files:**
- Modify: `src/asset_factory/cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write failing CLI tests**

Update `tests/test_cli.py` package assertion helper:

```python
def assert_package_local_manifest(
    manifest: dict,
    profile: str,
    *,
    has_glb: bool = True,
    has_stl: bool = False,
) -> None:
    assert manifest["files"]["optimized_glb"] == ("asset.glb" if has_glb else None)
    assert manifest["files"]["stl"] == ("asset.stl" if has_stl else None)
    assert manifest["files"]["stl_report"] == ("stl_report.json" if has_stl else None)
    assert manifest["files"]["thumbnail"] == "thumbnail.png"
    assert manifest["files"]["turntable"] == "turntable.webm"
    assert manifest["files"]["qa_report"] == "qa.json"
    assert manifest["files"]["raw_glb"] is None
    assert manifest["files"]["concept_image"] is None
    assert manifest["files"]["review_html"] is None
    assert manifest["files"]["exports"] == {profile: "."}
```

Add tests:

```python
def test_export_command_can_create_stl_only_package(tmp_path: Path):
    runner, run_dir = generate_run(tmp_path)

    export_result = runner.invoke(app, ["export", str(run_dir), "--profile", "unity", "--format", "stl"])

    assert export_result.exit_code == 0, export_result.output
    root_manifest = read_json(run_dir / "manifest.json")
    unity_manifest = read_json(run_dir / "exports" / "unity" / "manifest.json")
    assert root_manifest["files"]["exports"] == {
        "web": str(run_dir / "exports" / "web"),
        "unity": str(run_dir / "exports" / "unity"),
    }
    assert not (run_dir / "exports" / "unity" / "asset.glb").exists()
    assert (run_dir / "exports" / "unity" / "asset.stl").exists()
    assert (run_dir / "exports" / "unity" / "stl_report.json").exists()
    assert_package_local_manifest(unity_manifest, "unity", has_glb=False, has_stl=True)


def test_export_command_can_create_glb_and_stl_package(tmp_path: Path):
    runner, run_dir = generate_run(tmp_path)

    export_result = runner.invoke(
        app,
        [
            "export",
            str(run_dir),
            "--profile",
            "unity",
            "--format",
            "glb",
            "--format",
            "stl",
        ],
    )

    assert export_result.exit_code == 0, export_result.output
    unity_manifest = read_json(run_dir / "exports" / "unity" / "manifest.json")
    assert (run_dir / "exports" / "unity" / "asset.glb").exists()
    assert (run_dir / "exports" / "unity" / "asset.stl").exists()
    assert (run_dir / "exports" / "unity" / "stl_report.json").exists()
    assert_package_local_manifest(unity_manifest, "unity", has_glb=True, has_stl=True)
```

Update `test_export_does_not_advertise_incomplete_profile_dirs` to create a stale STL dir:

```python
(partial_export_dir / "asset.stl").write_bytes(b"solid stale")
```

Keep the assertion that `"unreal" not in root_manifest["files"]["exports"]` until the package also has required common files and `stl_report.json`.

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/test_cli.py -q
```

Expected: FAIL because `--format` is not accepted and package completeness still requires `asset.glb`.

- [ ] **Step 3: Update CLI imports and required files**

In `src/asset_factory/cli.py`, update imports:

```python
from asset_factory.models import (
    AssetManifest,
    AssetSpec,
    ExportFormat,
    ExportProfile,
    QaThresholds,
)
```

Replace `_REQUIRED_EXPORT_PACKAGE_FILES` with:

```python
_COMMON_EXPORT_PACKAGE_FILES = (
    "thumbnail.png",
    "turntable.webm",
    "qa.json",
    "IMPORT_NOTES.md",
)
_PACKAGE_MANIFEST_FILE = "manifest.json"
```

- [ ] **Step 4: Add repeated `--format` option**

Replace the export command signature:

```python
@app.command()
def export(
    run_dir: Path,
    profile: ExportProfile = ExportProfile.WEB,
    formats: Annotated[
        list[ExportFormat] | None,
        typer.Option("--format", help="Export file format. Repeat for multiple formats."),
    ] = None,
) -> None:
```

Inside the command before calling `export_profiles`, add:

```python
selected_formats = formats or [ExportFormat.GLB]
```

Replace:

```python
outputs = export_profiles(run_dir, [profile])
```

with:

```python
outputs = export_profiles(run_dir, [profile], formats=selected_formats)
```

In the final echo loop, replace:

```python
typer.echo(f"Exported {export_profile.value}: {output_dir}")
```

with:

```python
format_label = ", ".join(export_format.value for export_format in selected_formats)
typer.echo(f"Exported {export_profile.value} ({format_label}): {output_dir}")
```

- [ ] **Step 5: Update dynamic package format helpers**

Add these helpers above `_exports_from_package_dirs`:

```python
def _formats_from_package_dir(export_dir: Path) -> list[ExportFormat]:
    formats: list[ExportFormat] = []
    if (export_dir / "asset.glb").is_file():
        formats.append(ExportFormat.GLB)
    if (export_dir / "asset.stl").is_file() and (export_dir / "stl_report.json").is_file():
        formats.append(ExportFormat.STL)
    return formats
```

Replace `_is_complete_export_package`:

```python
def _is_complete_export_package(export_dir: Path) -> bool:
    return _has_export_package_payload(export_dir) and (
        export_dir / _PACKAGE_MANIFEST_FILE
    ).is_file()
```

Replace `_has_export_package_payload`:

```python
def _has_export_package_payload(export_dir: Path) -> bool:
    has_common_files = all(
        (export_dir / required_file).is_file()
        for required_file in _COMMON_EXPORT_PACKAGE_FILES
    )
    return has_common_files and bool(_formats_from_package_dir(export_dir))
```

Update `_remove_export_package_dirs` to keep using `_is_complete_export_package`.

- [ ] **Step 6: Sync package manifests with detected package formats**

In `_sync_export_packages`, replace:

```python
write_package_manifest(resolved_export_dir / "manifest.json", manifest, profile)
```

with:

```python
package_formats = _formats_from_package_dir(resolved_export_dir)
if not package_formats:
    continue
write_package_manifest(
    resolved_export_dir / "manifest.json",
    manifest,
    profile,
    package_formats,
)
```

- [ ] **Step 7: Include export formats in fallback specs**

In `_spec_from_manifest`, update the fallback `AssetSpec`:

```python
return AssetSpec(
    id=manifest.asset.id,
    subject=manifest.asset.subject,
    object=manifest.asset.object,
    grade_band=manifest.education.grade_band,
    style=manifest.education.style,
    learning_goal=manifest.education.learning_goal,
    exports=list(manifest.files.exports) or [ExportProfile.WEB],
    export_formats=[ExportFormat.GLB],
    qa=QaThresholds(max_triangles=150000, max_glb_mb=25),
)
```

- [ ] **Step 8: Run CLI tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_cli.py -q
```

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add src/asset_factory/cli.py tests/test_cli.py
git commit -m "Add CLI export format selection"
```

## Task 6: Wire Spec Export Formats Through Full Generation

**Files:**
- Modify: `tests/test_pipeline.py`
- Modify: `src/asset_factory/pipeline.py` if Task 4 did not already pass `spec.export_formats`
- Modify: `src/asset_factory/manifest.py` if Task 4 did not already support package formats

- [ ] **Step 1: Run full pipeline tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_pipeline.py tests/test_exports.py tests/test_cli.py -q
```

Expected: PASS. If any failure shows `asset.stl` missing for specs with `export_formats=[ExportFormat.GLB, ExportFormat.STL]`, confirm `generate_asset` calls:

```python
export_profiles(layout.run_dir, spec.exports, formats=spec.export_formats)
```

and `_write_export_manifests` receives `spec.export_formats`.

- [ ] **Step 2: Commit any missing pipeline wiring**

If Step 1 required changes:

```bash
git add src/asset_factory/pipeline.py src/asset_factory/manifest.py tests/test_pipeline.py
git commit -m "Wire spec export formats through pipeline"
```

If Step 1 required no changes, skip this commit.

## Task 7: Update README Usage

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add export format documentation**

In the spec example, show optional format selection:

```yaml
exports: ["web", "unity", "unreal"]
export_formats: ["glb", "stl"]
```

In the export section, add:

```markdown
### Export Formats

`exports` chooses destination packages (`web`, `unity`, `unreal`). `export_formats`
chooses asset file formats inside each package.

```bash
asset-factory export runs/chloroplast_001/<timestamp> --profile web --format glb
asset-factory export runs/chloroplast_001/<timestamp> --profile web --format stl
asset-factory export runs/chloroplast_001/<timestamp> --profile web --format glb --format stl
```

GLB is the canonical textured runtime asset for apps and engines. STL is a
geometry-only CAD/3D-printing derivative and does not preserve TRELLIS textures,
materials, vertex colors, PBR values, or opacity. Review `stl_report.json`
before printing.
```
```

- [ ] **Step 2: Run README-related smoke check**

Run:

```bash
rg -n "export_formats|--format stl|stl_report|geometry-only" README.md
```

Expected: output includes all four terms.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "Document GLB and STL export formats"
```

## Task 8: Final Verification And Real Run Check

**Files:**
- No planned source edits.
- Uses existing run directory when available: `runs/chloroplast_001/20260522T182623Z`

- [ ] **Step 1: Run full checks**

Run:

```bash
.venv/bin/python -m ruff check .
.venv/bin/python -m pytest -q
uv lock --check
git diff --check
```

Expected:

```text
All checks passed!
at least 111 passed
Resolved 45 packages
```

The exact pytest count may increase after adding tests.

- [ ] **Step 2: Export both formats from the real chloroplast run**

Run if the run directory exists:

```bash
.venv/bin/python -m asset_factory export \
  runs/chloroplast_001/20260522T182623Z \
  --profile web \
  --format glb \
  --format stl
```

Expected:

```text
Exported web (glb, stl): runs/chloroplast_001/20260522T182623Z/exports/web
```

- [ ] **Step 3: Verify real package artifacts**

Run:

```bash
test -s runs/chloroplast_001/20260522T182623Z/exports/web/asset.glb
test -s runs/chloroplast_001/20260522T182623Z/exports/web/asset.stl
jq '.files.optimized_glb, .files.stl, .files.stl_report' \
  runs/chloroplast_001/20260522T182623Z/exports/web/manifest.json
jq '.exported, .warnings' \
  runs/chloroplast_001/20260522T182623Z/exports/web/stl_report.json
```

Expected:

```text
"asset.glb"
"asset.stl"
"stl_report.json"
true
an array containing at least the geometry-only STL warning
```

- [ ] **Step 4: Commit any final fixes**

If verification required fixes:

```bash
git add src tests README.md
git commit -m "Finish GLB and STL export formats"
```

If no fixes were required, do not create an empty commit.

- [ ] **Step 5: Push branch**

```bash
git push origin HEAD:main
```

Expected: push succeeds.
