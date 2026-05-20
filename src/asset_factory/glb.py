from __future__ import annotations

import json
import struct
from dataclasses import dataclass
from numbers import Real
from pathlib import Path
from typing import Any

import trimesh
from pygltflib import GLTF2

_GLB_HEADER_LENGTH = 12
_GLB_CHUNK_HEADER_LENGTH = 8
_JSON_CHUNK_TYPE = 0x4E4F534A


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


def _load_glb_json(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    if len(data) < _GLB_HEADER_LENGTH:
        raise ValueError("GLB header is incomplete")

    magic, _version, _length = struct.unpack_from("<4sII", data, 0)
    if magic != b"glTF":
        raise ValueError("not binary GLTF!")

    offset = _GLB_HEADER_LENGTH
    while offset + _GLB_CHUNK_HEADER_LENGTH <= len(data):
        chunk_length, chunk_type = struct.unpack_from("<II", data, offset)
        offset += _GLB_CHUNK_HEADER_LENGTH
        chunk_end = offset + chunk_length
        if chunk_end > len(data):
            raise ValueError("GLB chunk length exceeds file length")

        chunk_data = data[offset:chunk_end]
        offset = chunk_end
        if chunk_type == _JSON_CHUNK_TYPE:
            json_text = chunk_data.rstrip(b" \t\r\n\x00").decode("utf-8")
            return json.loads(json_text)

    raise ValueError("GLB JSON chunk is missing")


def _is_valid_index(value: Any, items: Any) -> bool:
    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and value >= 0
        and isinstance(items, list)
        and value < len(items)
    )


def _has_valid_base_color_factor(pbr: dict[str, Any]) -> bool:
    factor = pbr.get("baseColorFactor")
    return (
        isinstance(factor, list)
        and len(factor) == 4
        and all(isinstance(value, Real) and not isinstance(value, bool) for value in factor)
    )


def _has_valid_base_color_texture(pbr: dict[str, Any], glb_json: dict[str, Any]) -> bool:
    texture_info = pbr.get("baseColorTexture")
    if not isinstance(texture_info, dict):
        return False

    textures = glb_json.get("textures")
    texture_index = texture_info.get("index")
    if not _is_valid_index(texture_index, textures):
        return False

    texture = textures[texture_index]
    if not isinstance(texture, dict):
        return False

    images = glb_json.get("images")
    return _is_valid_index(texture.get("source"), images)


def _has_explicit_base_color(material: Any, glb_json: dict[str, Any]) -> bool:
    if not isinstance(material, dict):
        return False

    pbr = material.get("pbrMetallicRoughness")
    if not isinstance(pbr, dict):
        return False

    return _has_valid_base_color_factor(pbr) or _has_valid_base_color_texture(pbr, glb_json)


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
    glb_json = _load_glb_json(path)
    materials = glb_json.get("materials") or []
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

            if not _has_explicit_base_color(materials[material_index], glb_json):
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
