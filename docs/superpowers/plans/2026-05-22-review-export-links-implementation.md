# Review Export Links Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add direct GLB/STL export links to the generated review HTML left rail.

**Architecture:** Keep `build_review_html()` pure by passing it normalized export-link data. Add a small filesystem adapter that turns export package directories into that data, then call it from the pipeline and CLI when writing `reports/review.html`.

**Tech Stack:** Python 3.11, Typer CLI, Pydantic models, pytest, static HTML/CSS.

---

## File Structure

- Modify `src/asset_factory/review.py`
  - Add `ReviewExportLink`.
  - Add `collect_review_exports()`.
  - Render the left-rail Exports panel.
- Modify `src/asset_factory/pipeline.py`
  - Generate exports before writing final review HTML.
  - Pass collected export links into `write_review_html()`.
- Modify `src/asset_factory/cli.py`
  - Pass collected export links from `_write_review_html()`.
  - Refresh review HTML after `asset_factory export`.
- Modify `tests/test_review.py`
  - Cover HTML rendering, empty state, missing formats, escaping, and STL warning counts.
- Modify `tests/test_pipeline.py`
  - Prove full generation writes review HTML with export links.
- Modify `tests/test_cli.py`
  - Prove `asset_factory export` refreshes review HTML when formats change.

## Task 1: Render Export Links In Review HTML

**Files:**
- Modify: `tests/test_review.py`
- Modify: `src/asset_factory/review.py`

- [ ] **Step 1: Write failing render tests**

Add these tests to `tests/test_review.py` after `test_build_review_html_contains_manifest_and_viewer`:

```python
def test_build_review_html_renders_export_links():
    from asset_factory.review import ReviewExportLink

    html = build_review_html(
        asset_id="chloroplast_001",
        concept_image="image/concept.png",
        glb_path="optimize/asset.glb",
        thumbnail="previews/thumbnail.png",
        qa_passed=True,
        warnings=[],
        exports=[
            ReviewExportLink(
                profile="Web",
                glb_path="exports/web/asset.glb",
                stl_path="exports/web/asset.stl",
                stl_report_path="exports/web/stl_report.json",
                stl_warning_count=2,
            )
        ],
    )

    assert "<h2>Exports</h2>" in html
    assert "Web" in html
    assert 'href="../exports/web/asset.glb"' in html
    assert 'href="../exports/web/asset.stl"' in html
    assert 'download>GLB</a>' in html
    assert 'download>STL</a>' in html
    assert 'href="../exports/web/stl_report.json"' in html
    assert "2 STL warnings" in html
    assert "STL exports are geometry-only and may need repair before 3D printing." in html


def test_build_review_html_marks_missing_export_formats_unavailable():
    from asset_factory.review import ReviewExportLink

    html = build_review_html(
        asset_id="pulley_001",
        concept_image="image/concept.png",
        glb_path="optimize/asset.glb",
        thumbnail="previews/thumbnail.png",
        qa_passed=True,
        warnings=[],
        exports=[ReviewExportLink(profile="Unity", glb_path=None, stl_path="exports/unity/asset.stl")],
    )

    assert "Unity" in html
    assert 'aria-label="GLB unavailable for Unity"' in html
    assert '<span class="export-badge unavailable" aria-label="GLB unavailable for Unity">GLB</span>' in html
    assert 'href="../exports/unity/asset.stl"' in html


def test_build_review_html_renders_export_empty_state():
    html = build_review_html(
        asset_id="failed_001",
        concept_image="image/concept.png",
        glb_path="optimize/asset.glb",
        thumbnail="previews/thumbnail.png",
        qa_passed=False,
        warnings=["QA failed"],
        exports=[],
    )

    assert "<h2>Exports</h2>" in html
    assert "No export packages were created for this run." in html


def test_build_review_html_escapes_export_content():
    from asset_factory.review import ReviewExportLink

    html = build_review_html(
        asset_id="demo",
        concept_image="image/concept.png",
        glb_path="optimize/asset.glb",
        thumbnail="previews/thumbnail.png",
        qa_passed=True,
        warnings=[],
        exports=[
            ReviewExportLink(
                profile='Web <script>',
                glb_path='exports/web/asset" onclick="alert(1).glb',
            )
        ],
    )

    assert "Web &lt;script&gt;" in html
    assert 'href="../exports/web/asset&quot; onclick=&quot;alert(1).glb"' in html
    assert 'href="../exports/web/asset" onclick="alert(1).glb"' not in html
```

- [ ] **Step 2: Run render tests and verify they fail**

Run:

```bash
.venv/bin/pytest tests/test_review.py::test_build_review_html_renders_export_links tests/test_review.py::test_build_review_html_marks_missing_export_formats_unavailable tests/test_review.py::test_build_review_html_renders_export_empty_state tests/test_review.py::test_build_review_html_escapes_export_content -q
```

Expected: FAIL because `ReviewExportLink` does not exist and `build_review_html()` does not accept `exports`.

- [ ] **Step 3: Implement the minimal render model and panel**

In `src/asset_factory/review.py`, add imports:

```python
from collections.abc import Sequence
from dataclasses import dataclass
```

Add this dataclass below `_script_json()`:

```python
@dataclass(frozen=True)
class ReviewExportLink:
    profile: str
    glb_path: str | None = None
    stl_path: str | None = None
    stl_report_path: str | None = None
    stl_warning_count: int = 0
```

Change `build_review_html()` to accept exports:

```python
def build_review_html(
    *,
    asset_id: str,
    concept_image: str,
    glb_path: str,
    thumbnail: str,
    qa_passed: bool,
    warnings: list[str],
    exports: Sequence[ReviewExportLink] = (),
) -> str:
```

Add these helpers above `build_review_html()`:

```python
def _href(path: str) -> str:
    return f"../{path}"


def _export_badge(
    *,
    label: str,
    path: str | None,
    profile: str,
) -> str:
    escaped_label = html.escape(label, quote=True)
    escaped_profile = html.escape(profile, quote=True)
    if path is None:
        return (
            f'<span class="export-badge unavailable" '
            f'aria-label="{escaped_label} unavailable for {escaped_profile}">'
            f"{escaped_label}</span>"
        )
    escaped_href = html.escape(_href(path), quote=True)
    return f'<a class="export-badge" href="{escaped_href}" download>{escaped_label}</a>'


def _stl_warning_badge(export: ReviewExportLink) -> str:
    if export.stl_warning_count <= 0:
        return ""
    warning_label = (
        "1 STL warning" if export.stl_warning_count == 1 else f"{export.stl_warning_count} STL warnings"
    )
    escaped_label = html.escape(warning_label, quote=True)
    if export.stl_report_path:
        escaped_href = html.escape(_href(export.stl_report_path), quote=True)
        return f'<a class="export-warning" href="{escaped_href}">{escaped_label}</a>'
    return f'<span class="export-warning">{escaped_label}</span>'


def _render_exports_panel(exports: Sequence[ReviewExportLink]) -> str:
    if not exports:
        rows = '<p class="muted">No export packages were created for this run.</p>'
    else:
        rows = "".join(
            (
                '<div class="export-row">'
                f'<strong>{html.escape(export.profile, quote=True)}</strong>'
                '<div class="export-actions">'
                f'{_export_badge(label="GLB", path=export.glb_path, profile=export.profile)}'
                f'{_export_badge(label="STL", path=export.stl_path, profile=export.profile)}'
                f'{_stl_warning_badge(export)}'
                "</div>"
                "</div>"
            )
            for export in exports
        )
    return (
        '<section class="panel export-panel">'
        "<h2>Exports</h2>"
        f"{rows}"
        '<p class="export-note">STL exports are geometry-only and may need repair before 3D printing.</p>'
        "</section>"
    )
```

Inside `build_review_html()`, compute:

```python
    exports_panel = _render_exports_panel(exports)
```

Add CSS inside the `<style>` block:

```css
    a { color: inherit; }
    .muted { color: var(--muted); }
    .export-panel { display: grid; gap: 10px; }
    .export-row {
      display: grid;
      grid-template-columns: 76px minmax(0, 1fr);
      align-items: center;
      gap: 8px;
      border-top: 1px solid #e7ebf0;
      padding-top: 10px;
    }
    .export-row:first-of-type { border-top: 0; padding-top: 0; }
    .export-actions {
      display: flex;
      align-items: center;
      flex-wrap: wrap;
      gap: 6px;
    }
    .export-badge {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 30px;
      min-width: 42px;
      padding: 5px 8px;
      border: 1px solid var(--accent);
      border-radius: 6px;
      background: var(--accent);
      color: #fff;
      font-size: 0.78rem;
      font-weight: 700;
      text-decoration: none;
    }
    .export-badge.unavailable {
      border-color: #c5ceda;
      background: #eef2f6;
      color: var(--muted);
    }
    .export-warning {
      color: #9a3412;
      font-size: 0.78rem;
      font-weight: 700;
      text-decoration: none;
    }
    .export-note {
      margin: 0;
      color: var(--muted);
      font-size: 0.82rem;
      line-height: 1.35;
    }
```

Render the panel below the Review panel in the left rail:

```html
      <section class="panel">
        <h2>Review</h2>
        <button class="primary" type="button">Approve</button>
        <button type="button">Needs changes</button>
        <button type="button">Reject</button>
      </section>
      {exports_panel}
```

Update `write_review_html()` to accept and pass exports:

```python
def write_review_html(
    run_dir: Path,
    *,
    asset_id: str,
    concept_image: str,
    glb_path: str,
    thumbnail: str,
    qa_passed: bool,
    warnings: list[str],
    exports: Sequence[ReviewExportLink] = (),
) -> Path:
```

Pass `exports=exports` into `build_review_html()`.

- [ ] **Step 4: Run render tests and verify they pass**

Run:

```bash
.venv/bin/pytest tests/test_review.py::test_build_review_html_renders_export_links tests/test_review.py::test_build_review_html_marks_missing_export_formats_unavailable tests/test_review.py::test_build_review_html_renders_export_empty_state tests/test_review.py::test_build_review_html_escapes_export_content -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 1**

Run:

```bash
git add src/asset_factory/review.py tests/test_review.py
git commit -m "Add export links to review HTML"
```

## Task 2: Collect Export Link Data From Package Directories

**Files:**
- Modify: `tests/test_review.py`
- Modify: `src/asset_factory/review.py`

- [ ] **Step 1: Write failing collection tests**

Add imports at the top of `tests/test_review.py`:

```python
import json
```

Add these tests near the render tests:

```python
def test_collect_review_exports_finds_package_files_and_warning_counts(tmp_path: Path):
    from asset_factory.models import ExportProfile
    from asset_factory.review import ReviewExportLink, collect_review_exports

    export_dir = tmp_path / "exports" / "web"
    export_dir.mkdir(parents=True)
    (export_dir / "asset.glb").write_bytes(b"glb")
    (export_dir / "asset.stl").write_bytes(b"stl")
    (export_dir / "stl_report.json").write_text(
        json.dumps({"warnings": ["not watertight", "many bodies"]}),
        encoding="utf-8",
    )

    exports = collect_review_exports(tmp_path, {ExportProfile.WEB: export_dir})

    assert exports == [
        ReviewExportLink(
            profile="Web",
            glb_path="exports/web/asset.glb",
            stl_path="exports/web/asset.stl",
            stl_report_path="exports/web/stl_report.json",
            stl_warning_count=2,
        )
    ]


def test_collect_review_exports_keeps_stl_link_when_report_is_unreadable(tmp_path: Path):
    from asset_factory.models import ExportProfile
    from asset_factory.review import ReviewExportLink, collect_review_exports

    export_dir = tmp_path / "exports" / "unity"
    export_dir.mkdir(parents=True)
    (export_dir / "asset.stl").write_bytes(b"stl")
    (export_dir / "stl_report.json").write_text("{not-json", encoding="utf-8")

    exports = collect_review_exports(tmp_path, {ExportProfile.UNITY: export_dir})

    assert exports == [
        ReviewExportLink(
            profile="Unity",
            glb_path=None,
            stl_path="exports/unity/asset.stl",
            stl_report_path="exports/unity/stl_report.json",
            stl_warning_count=1,
        )
    ]


def test_collect_review_exports_does_not_link_outside_run_dir(tmp_path: Path):
    from asset_factory.models import ExportProfile
    from asset_factory.review import ReviewExportLink, collect_review_exports

    outside_dir = tmp_path.parent / "outside-export"
    outside_dir.mkdir(exist_ok=True)
    (outside_dir / "asset.glb").write_bytes(b"glb")

    exports = collect_review_exports(tmp_path, {ExportProfile.UNREAL: outside_dir})

    assert exports == [ReviewExportLink(profile="Unreal")]
```

- [ ] **Step 2: Run collection tests and verify they fail**

Run:

```bash
.venv/bin/pytest tests/test_review.py::test_collect_review_exports_finds_package_files_and_warning_counts tests/test_review.py::test_collect_review_exports_keeps_stl_link_when_report_is_unreadable tests/test_review.py::test_collect_review_exports_does_not_link_outside_run_dir -q
```

Expected: FAIL because `collect_review_exports()` does not exist.

- [ ] **Step 3: Implement export collection**

In `src/asset_factory/review.py`, add imports:

```python
from collections.abc import Mapping
```

Extend the existing `json` and `Path` imports already in the file.

Add these helpers below `ReviewExportLink`:

```python
def collect_review_exports(
    run_dir: Path,
    exports: Mapping[object, str | Path],
) -> list[ReviewExportLink]:
    collected: list[ReviewExportLink] = []
    for profile, export_path in sorted(exports.items(), key=lambda item: _profile_value(item[0])):
        export_dir = _resolve_export_dir(run_dir, export_path)
        glb_path = _relative_existing_file(run_dir, export_dir / "asset.glb")
        stl_path = _relative_existing_file(run_dir, export_dir / "asset.stl")
        stl_report_path = _relative_existing_file(run_dir, export_dir / "stl_report.json")
        collected.append(
            ReviewExportLink(
                profile=_profile_label(profile),
                glb_path=glb_path,
                stl_path=stl_path,
                stl_report_path=stl_report_path,
                stl_warning_count=_stl_warning_count(export_dir / "stl_report.json")
                if stl_path
                else 0,
            )
        )
    return collected


def _profile_value(profile: object) -> str:
    value = getattr(profile, "value", profile)
    return str(value)


def _profile_label(profile: object) -> str:
    return _profile_value(profile).replace("_", " ").title()


def _resolve_export_dir(run_dir: Path, export_path: str | Path) -> Path:
    path = Path(export_path)
    if path.is_absolute():
        return path
    if path.parts[:1] == ("exports",):
        return run_dir / path
    return path


def _relative_existing_file(run_dir: Path, file_path: Path) -> str | None:
    if not file_path.is_file():
        return None
    try:
        relative_path = file_path.resolve().relative_to(run_dir.resolve())
    except ValueError:
        return None
    return relative_path.as_posix()


def _stl_warning_count(report_path: Path) -> int:
    if not report_path.is_file():
        return 1
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 1
    warnings = report.get("warnings")
    if not isinstance(warnings, list):
        return 1
    return len(warnings)
```

- [ ] **Step 4: Run collection tests and verify they pass**

Run:

```bash
.venv/bin/pytest tests/test_review.py::test_collect_review_exports_finds_package_files_and_warning_counts tests/test_review.py::test_collect_review_exports_keeps_stl_link_when_report_is_unreadable tests/test_review.py::test_collect_review_exports_does_not_link_outside_run_dir -q
```

Expected: PASS.

- [ ] **Step 5: Run all review tests**

Run:

```bash
.venv/bin/pytest tests/test_review.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit Task 2**

Run:

```bash
git add src/asset_factory/review.py tests/test_review.py
git commit -m "Collect review export links from packages"
```

## Task 3: Wire Export Links Into Pipeline And CLI

**Files:**
- Modify: `tests/test_pipeline.py`
- Modify: `tests/test_cli.py`
- Modify: `src/asset_factory/pipeline.py`
- Modify: `src/asset_factory/cli.py`

- [ ] **Step 1: Write failing pipeline test assertions**

In `tests/test_pipeline.py`, inside `test_generate_asset_creates_complete_run()` after the existing export file assertions, add:

```python
    review_html = (run_dir / "reports" / "review.html").read_text(encoding="utf-8")
    assert 'href="../exports/web/asset.glb"' in review_html
    assert 'href="../exports/web/asset.stl"' in review_html
    assert 'href="../exports/unity/asset.glb"' in review_html
    assert 'href="../exports/unity/asset.stl"' in review_html
    assert "STL exports are geometry-only and may need repair before 3D printing." in review_html
```

- [ ] **Step 2: Write failing CLI refresh test**

In `tests/test_cli.py`, add this test after `test_export_command_can_create_stl_only_package()`:

```python
def test_export_command_refreshes_review_html_with_current_formats(tmp_path: Path):
    runner, run_dir = generate_run(tmp_path)

    export_result = runner.invoke(
        app,
        ["export", str(run_dir), "--profile", "unity", "--format", "stl"],
    )

    assert export_result.exit_code == 0, export_result.output
    html = (run_dir / "reports" / "review.html").read_text(encoding="utf-8")
    assert "Web" in html
    assert 'href="../exports/web/asset.glb"' in html
    assert 'aria-label="STL unavailable for Web"' in html
    assert "Unity" in html
    assert 'aria-label="GLB unavailable for Unity"' in html
    assert 'href="../exports/unity/asset.stl"' in html
```

- [ ] **Step 3: Run new wiring tests and verify they fail**

Run:

```bash
.venv/bin/pytest tests/test_pipeline.py::test_generate_asset_creates_complete_run tests/test_cli.py::test_export_command_refreshes_review_html_with_current_formats -q
```

Expected: FAIL because pipeline review HTML is written before exports and the export command does not refresh review HTML.

- [ ] **Step 4: Update pipeline review generation order**

In `src/asset_factory/pipeline.py`, replace the early `write_review_html()` call and the two `_apply_outputs()` calls with this sequence after `qa_report.write_text(...)`:

```python
    exports = (
        export_profiles(layout.run_dir, spec.exports, formats=spec.export_formats)
        if qa_summary.passed
        else {}
    )

    from asset_factory.review import collect_review_exports, write_review_html

    review_html = write_review_html(
        layout.run_dir,
        asset_id=spec.id,
        concept_image="image/concept.png",
        glb_path="optimize/asset.glb",
        thumbnail="previews/thumbnail.png",
        qa_passed=qa_summary.passed,
        warnings=qa_summary.warnings,
        exports=collect_review_exports(layout.run_dir, exports),
    )

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
    _write_export_manifests(exports, manifest, spec.export_formats)
    return PipelineResult(run_dir=layout.run_dir, layout=layout, manifest=manifest)
```

The resulting function should write the final review HTML once, after export packages exist.

- [ ] **Step 5: Update CLI review writing**

In `src/asset_factory/cli.py`, update `_write_review_html()`:

```python
def _write_review_html(run_dir: Path, manifest: AssetManifest) -> Path:
    from asset_factory.review import collect_review_exports, write_review_html

    warnings = [*manifest.qa.blocking_failures, *manifest.qa.warnings]
    return write_review_html(
        run_dir,
        asset_id=manifest.asset.id,
        concept_image="image/concept.png",
        glb_path="optimize/asset.glb",
        thumbnail="previews/thumbnail.png",
        qa_passed=manifest.qa.passed,
        warnings=warnings,
        exports=collect_review_exports(run_dir, manifest.files.exports),
    )
```

In the `export()` command, replace the existing `write_manifest(manifest_path, manifest)` before `_sync_export_packages(...)` with final persistence after syncing packages:

```python
    _sync_export_packages(
        manifest,
        run_dir / "reports" / "qa.json",
        run_dir / "exports",
        export_dirs=export_dirs,
    )
    review_html = _write_review_html(run_dir, manifest)
    manifest.files.review_html = str(review_html)
    write_manifest(manifest_path, manifest)
```

Keep the final `typer.echo(...)` loop unchanged.

- [ ] **Step 6: Run new wiring tests and verify they pass**

Run:

```bash
.venv/bin/pytest tests/test_pipeline.py::test_generate_asset_creates_complete_run tests/test_cli.py::test_export_command_refreshes_review_html_with_current_formats -q
```

Expected: PASS.

- [ ] **Step 7: Run CLI export regression tests**

Run:

```bash
.venv/bin/pytest tests/test_cli.py::test_export_updates_existing_export_manifests tests/test_cli.py::test_export_command_can_create_stl_only_package tests/test_cli.py::test_export_command_can_create_glb_and_stl_package tests/test_cli.py::test_failed_stl_export_preserves_existing_advertised_package -q
```

Expected: PASS.

- [ ] **Step 8: Commit Task 3**

Run:

```bash
git add src/asset_factory/pipeline.py src/asset_factory/cli.py tests/test_pipeline.py tests/test_cli.py
git commit -m "Wire export links into generated review pages"
```

## Task 4: Full Verification

**Files:**
- No code changes expected.

- [ ] **Step 1: Run formatter/linter**

Run:

```bash
.venv/bin/ruff check .
```

Expected: PASS with no lint errors.

- [ ] **Step 2: Run the full test suite**

Run:

```bash
.venv/bin/pytest -q
```

Expected: PASS.

- [ ] **Step 3: Check for whitespace errors**

Run:

```bash
git diff --check
```

Expected: no output and exit code 0.

- [ ] **Step 4: Inspect final diff**

Run:

```bash
git diff --stat origin/main...HEAD
git diff --name-only origin/main...HEAD
```

Expected: changed files are limited to:

```text
docs/superpowers/specs/2026-05-22-review-export-links-design.md
docs/superpowers/plans/2026-05-22-review-export-links-implementation.md
src/asset_factory/review.py
src/asset_factory/pipeline.py
src/asset_factory/cli.py
tests/test_review.py
tests/test_pipeline.py
tests/test_cli.py
```

- [ ] **Step 5: Commit verification-only fixes if needed**

If Step 1, 2, or 3 required code changes, run:

```bash
git add src/asset_factory/review.py src/asset_factory/pipeline.py src/asset_factory/cli.py tests/test_review.py tests/test_pipeline.py tests/test_cli.py
git commit -m "Polish review export link implementation"
```

If no files changed after verification, do not create an empty commit.
