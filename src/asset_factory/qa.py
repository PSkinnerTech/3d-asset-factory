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
            "primitive_count": glb_metrics.primitive_count,
            "primitives_missing_material": glb_metrics.primitives_missing_material,
            "primitives_missing_base_color": glb_metrics.primitives_missing_base_color,
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
    if glb_metrics.has_geometry and glb_metrics.triangles < 50:
        warnings.append("Asset has very low triangle count; visual quality needs review")

    return QaSummary(
        passed=not failures,
        blocking_failures=failures,
        warnings=warnings,
        metrics=metrics,
    )
