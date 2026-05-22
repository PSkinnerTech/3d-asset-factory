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
    body_count = _count_connected_bodies(mesh)
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


def _count_connected_bodies(mesh: Trimesh) -> int:
    face_count = len(mesh.faces)
    if face_count == 0:
        return 1

    parents = list(range(face_count))

    def find(face: int) -> int:
        while parents[face] != face:
            parents[face] = parents[parents[face]]
            face = parents[face]
        return face

    def union(left: int, right: int) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parents[right_root] = left_root

    for left, right in mesh.face_adjacency:
        union(int(left), int(right))

    return len({find(face) for face in range(face_count)})
