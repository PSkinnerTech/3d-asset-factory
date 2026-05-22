# Export Formats Design

## Summary

Add export format selection to 3D Asset Factory so each destination profile can package GLB, STL, or both. GLB remains the canonical textured runtime asset. STL is a best-effort print/CAD derivative generated from the optimized GLB, with explicit warnings because STL does not preserve material, color, or texture data.

## Goals

- Let developers request `.glb`, `.stl`, or both in generated export packages.
- Keep the existing `exports: ["web", "unity", "unreal"]` profile model intact.
- Preserve backwards compatibility for existing specs by defaulting export formats to GLB.
- Treat STL as geometry-only and intended for 3D printing/CAD workflows.
- Generate an STL report with print-readiness checks and warnings.
- Avoid blocking exports for non-watertight or non-manifold TRELLIS geometry unless STL conversion itself fails.

## Non-Goals

- Do not make STL a new export profile.
- Do not replace GLB as the canonical optimized asset.
- Do not guarantee print-ready geometry in v1.
- Do not add automatic mesh repair, hollowing, scale-unit normalization, supports, slicing, or printer-specific outputs.
- Do not add OBJ, FBX, USDZ, or other formats in this iteration.

## Current State

The current pipeline has destination profiles:

```text
web | unity | unreal
```

Each export package currently receives:

```text
asset.glb
thumbnail.png
turntable.webm
qa.json
manifest.json
IMPORT_NOTES.md
```

This works for runtime use because GLB preserves materials and colors. It does not address CAD or 3D-printing users who often need STL.

## Design

Keep destination and file format separate:

```text
profile: web | unity | unreal
format: glb | stl
```

`exports` continues to mean destination profile. Add a separate optional `export_formats` field:

```yaml
exports: ["web", "unity", "unreal"]
export_formats: ["glb", "stl"]
```

If `export_formats` is omitted, the system behaves exactly as it does today and exports only GLB:

```yaml
exports: ["web", "unity", "unreal"]
```

The CLI also accepts one or more formats for ad hoc export:

```bash
asset-factory export runs/... --profile web --format glb
asset-factory export runs/... --profile web --format stl
asset-factory export runs/... --profile web --format glb --format stl
```

If no `--format` is supplied, the CLI defaults to GLB for compatibility.

## Package Layout

When both formats are requested:

```text
exports/web/
  asset.glb
  asset.stl
  thumbnail.png
  turntable.webm
  qa.json
  stl_report.json
  manifest.json
  IMPORT_NOTES.md
```

When only STL is requested:

```text
exports/web/
  asset.stl
  thumbnail.png
  turntable.webm
  qa.json
  stl_report.json
  manifest.json
  IMPORT_NOTES.md
```

The STL-only package is valid, but import notes must clearly state that STL is a geometry-only derivative and GLB should be used for textured learning-app rendering.

## Data Model

Add:

```python
class ExportFormat(StrEnum):
    GLB = "glb"
    STL = "stl"
```

Add to `AssetSpec`:

```python
export_formats: list[ExportFormat] = Field(default_factory=lambda: [ExportFormat.GLB])
```

Add to `FileManifest`:

```python
stl: str | None = None
stl_report: str | None = None
```

Existing `optimized_glb` remains the canonical runtime GLB path. In a package-local manifest, `optimized_glb` is `"asset.glb"` only when the package includes GLB; otherwise it is `None`. `stl` is `"asset.stl"` only when the package includes STL.

## STL Report

Each STL export writes `stl_report.json`:

```json
{
  "exported": true,
  "source_glb": "optimize/asset.glb",
  "output_stl": "exports/web/asset.stl",
  "triangle_count": 150000,
  "body_count": 1,
  "is_watertight": false,
  "is_winding_consistent": true,
  "is_volume": false,
  "warnings": [
    "STL is geometry-only; materials, colors, and textures are not preserved.",
    "Mesh is not watertight; 3D printing may require repair."
  ]
}
```

Warnings are expected for many TRELLIS outputs. They do not fail the export unless conversion fails or no STL is written.

## STL Conversion

Use `trimesh` to convert `optimize/asset.glb` to STL:

1. Load the optimized GLB.
2. Collect geometry from a scene or mesh.
3. Combine visible geometry into one exportable mesh when needed.
4. Export binary STL as `asset.stl`.
5. Inspect the exported mesh and write `stl_report.json`.

The conversion must not mutate `optimize/asset.glb`. GLB remains the source of truth for textured previews and runtime packages.

## Error Handling

- Missing optimized GLB: fail the export command.
- Unsupported format value: fail argument/spec validation.
- STL conversion exception: fail the export command and do not advertise the incomplete package in manifests.
- STL written but mesh is not watertight, not a valid volume, has inconsistent winding, or has multiple bodies: export succeeds with warnings in `stl_report.json`.
- STL requested with no geometry: fail the STL conversion because no useful CAD/print derivative exists.

## Import Notes

`IMPORT_NOTES.md` should include profile-specific guidance plus format-specific guidance:

- GLB: textured runtime asset for web, Unity, Unreal, and learning apps.
- STL: geometry-only derivative for CAD and 3D-printing workflows.
- STL does not preserve TRELLIS textures, materials, vertex colors, PBR values, or opacity.
- Review `stl_report.json` before printing.
- If the mesh is not watertight or not a valid volume, repair it in CAD/mesh tooling before printing.

## Testing

Unit tests:

- Specs accept omitted `export_formats` and default to GLB.
- Specs accept `export_formats: ["glb", "stl"]`.
- Specs reject unsupported formats and empty format lists.
- Export package with GLB only matches current behavior.
- Export package with STL only writes `asset.stl`, `stl_report.json`, package manifest, notes, previews, and QA report.
- Export package with both formats writes both `asset.glb` and `asset.stl`.
- STL report includes geometry-only warning and print-readiness metrics.
- Non-watertight mesh exports successfully with warnings.
- Missing optimized GLB fails cleanly.

CLI tests:

- `asset-factory export RUN --profile web --format stl` creates an STL package.
- Re-running export does not advertise incomplete stale profile directories.
- QA pass resyncs only complete export packages.
- Failed QA still blocks export as it does today.

Integration check:

- Use the existing chloroplast run to export both GLB and STL.
- Confirm `asset.stl` exists and has non-zero size.
- Confirm package manifest references `asset.glb`, `asset.stl`, and `stl_report.json` when both formats are requested.

## Open Decisions

No open decisions remain for v1. STL is a best-effort CAD/3D-printing derivative with warnings, not a blocking print-readiness gate.
