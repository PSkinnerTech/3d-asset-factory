# Review Export Links Design

## Decision

Use Option A: add a simple **Exports** panel to the left rail of the generated review HTML.

The review page remains a static QA report. It exposes export files that already exist in the run directory; it does not generate new exports or provide an interactive export workflow.

## Goals

- Make available export formats discoverable from the review page.
- Support the current profiles: `web`, `unity`, and `unreal`.
- Show available `GLB` and `STL` files as direct browser links.
- Make missing export files visible without hiding the whole profile.
- Keep the page compatible with static file serving from a run directory.

## Non-Goals

- No export drawer, wizard, queue, or custom format selector in this version.
- No on-demand conversion from the browser UI.
- No zip package creation from the review page.
- No attempt to make STL printability look equivalent to GLB visual QA.

## User Experience

The left rail gains an **Exports** panel below the existing review controls.

Each export profile renders as a row:

```text
Web      GLB  STL
Unity    GLB  STL
Unreal   GLB  STL
```

When a file exists, `GLB` or `STL` is a direct link to that file. When it does not exist, the format appears as a muted unavailable badge.

The panel includes a compact STL note:

```text
STL exports are geometry-only and may need repair before 3D printing.
```

If an STL report exists and contains warnings, the row should show a small warning indicator for that STL link. The full warning detail stays in `stl_report.json` for this version.

## Data Flow

`asset_factory.cli._write_review_html()` should inspect `manifest.files.exports` and each export package directory. For every profile, it should determine whether these files exist:

- `asset.glb`
- `asset.stl`
- `stl_report.json`

The CLI passes normalized export-link data into `asset_factory.review.write_review_html()`, which passes it through to `build_review_html()`.

`build_review_html()` renders only static links and labels. It should not read the filesystem directly.

## Failure And Empty States

If QA fails and no export packages exist, the Exports panel should still render with an empty-state message:

```text
No export packages were created for this run.
```

If a profile exists but only one format exists, render the available format as a link and the missing format as unavailable.

If `stl_report.json` is malformed or unreadable, the link should still render and show a generic STL warning indicator.

## Testing

Add review HTML tests for:

- Rendering direct `GLB` and `STL` links for available profiles.
- Rendering muted unavailable states for missing formats.
- Rendering the empty state when no export packages exist.
- Escaping profile labels and paths in visible HTML and link attributes.

Add CLI or pipeline coverage that proves generated review HTML includes export links after a successful run with `GLB` and `STL` exports.

## Future Path

This design keeps enough structure to evolve toward Option B later: a detailed export package panel with file sizes, triangle counts, STL warning counts, and per-package health. Option C, an export drawer or wizard, should wait until the project has a persistent app surface rather than generated static HTML.
