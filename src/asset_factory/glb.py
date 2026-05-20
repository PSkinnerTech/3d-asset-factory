from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import trimesh
from pygltflib import GLTF2


@dataclass(frozen=True)
class GlbMetrics:
    triangles: int
    file_size_bytes: int
    has_geometry: bool
    has_material: bool
    has_base_color: bool
    primitive_count: int
    primitives_missing_material: int
    primitives_missing_base_color: int


def inspect_glb(path: Path) -> GlbMetrics:
    loaded = trimesh.load(path, force="scene")
    geometries = list(getattr(loaded, "geometry", {}).values())
    if not geometries and hasattr(loaded, "faces"):
        geometries = [loaded]

    triangles = 0
    for geometry in geometries:
        faces = getattr(geometry, "faces", [])
        triangles += len(faces)

    gltf = GLTF2.load(path)
    materials = gltf.materials or []
    primitive_count = 0
    primitives_missing_material = 0
    primitives_missing_base_color = 0
    for mesh in gltf.meshes or []:
        for primitive in mesh.primitives or []:
            attributes = primitive.attributes
            if attributes is None or getattr(attributes, "POSITION", None) is None:
                continue

            primitive_count += 1
            material_index = primitive.material
            if (
                material_index is None
                or material_index < 0
                or material_index >= len(materials)
            ):
                primitives_missing_material += 1
                primitives_missing_base_color += 1
                continue

            pbr = materials[material_index].pbrMetallicRoughness
            if pbr is None or (
                pbr.baseColorFactor is None and pbr.baseColorTexture is None
            ):
                primitives_missing_base_color += 1

    has_material = primitive_count > 0 and primitives_missing_material == 0
    has_base_color = primitive_count > 0 and primitives_missing_base_color == 0

    return GlbMetrics(
        triangles=triangles,
        file_size_bytes=path.stat().st_size,
        has_geometry=triangles > 0,
        has_material=has_material,
        has_base_color=has_base_color,
        primitive_count=primitive_count,
        primitives_missing_material=primitives_missing_material,
        primitives_missing_base_color=primitives_missing_base_color,
    )
