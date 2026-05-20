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

    gltf = GLTF2.load(path)
    materials = gltf.materials or []
    for mesh in gltf.meshes or []:
        for primitive in mesh.primitives or []:
            material_index = primitive.material
            if material_index is None or material_index >= len(materials):
                continue

            has_material = True
            pbr = materials[material_index].pbrMetallicRoughness
            if pbr is not None and (
                pbr.baseColorFactor is not None or pbr.baseColorTexture is not None
            ):
                has_base_color = True

    return GlbMetrics(
        triangles=triangles,
        file_size_bytes=path.stat().st_size,
        has_geometry=triangles > 0,
        has_material=has_material,
        has_base_color=has_base_color,
    )
