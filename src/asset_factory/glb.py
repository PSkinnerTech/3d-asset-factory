from __future__ import annotations

import json
import struct
from dataclasses import dataclass
from numbers import Real
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

import trimesh
from pygltflib import GLTF2

_GLB_HEADER_LENGTH = 12
_GLB_CHUNK_HEADER_LENGTH = 8
_JSON_CHUNK_TYPE = 0x4E4F534A
_COLOR_ACCESSOR_TYPES = {"VEC3", "VEC4"}
_COLOR_FLOAT_COMPONENT_TYPE = 5126
_COLOR_NORMALIZED_INTEGER_COMPONENT_TYPES = {5121, 5123}


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
        and all(
            isinstance(value, Real) and not isinstance(value, bool) and 0.0 <= value <= 1.0
            for value in factor
        )
    )


def _has_usable_image_uri(uri: Any, glb_parent: Path) -> bool:
    if not isinstance(uri, str):
        return False

    uri = uri.strip()
    if not uri:
        return False

    if uri.lower().startswith("data:"):
        _header, separator, payload = uri.partition(",")
        return bool(separator and payload.strip())

    parsed = urlparse(uri)
    if parsed.scheme and parsed.scheme != "file":
        return False

    uri_path = unquote(parsed.path if parsed.scheme == "file" else uri)
    image_path = Path(uri_path)
    if not image_path.is_absolute():
        image_path = glb_parent / image_path

    return image_path.is_file()


def _has_positive_byte_length(buffer_view: Any) -> bool:
    if not isinstance(buffer_view, dict):
        return False

    byte_length = buffer_view.get("byteLength")
    return isinstance(byte_length, int) and not isinstance(byte_length, bool) and byte_length > 0


def _positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _has_usable_image_data(image: Any, glb_json: dict[str, Any], glb_parent: Path) -> bool:
    if not isinstance(image, dict):
        return False

    if _has_usable_image_uri(image.get("uri"), glb_parent):
        return True

    mime_type = image.get("mimeType")
    buffer_views = glb_json.get("bufferViews")
    buffer_view_index = image.get("bufferView")
    return (
        isinstance(mime_type, str)
        and bool(mime_type.strip())
        and _is_valid_index(buffer_view_index, buffer_views)
        and _has_positive_byte_length(buffer_views[buffer_view_index])
    )


def _has_valid_base_color_texture(
    pbr: dict[str, Any], glb_json: dict[str, Any], glb_parent: Path
) -> bool:
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
    source_index = texture.get("source")
    return _is_valid_index(source_index, images) and _has_usable_image_data(
        images[source_index], glb_json, glb_parent
    )


def _has_explicit_base_color(material: Any, glb_json: dict[str, Any], glb_parent: Path) -> bool:
    if not isinstance(material, dict):
        return False

    pbr = material.get("pbrMetallicRoughness")
    if not isinstance(pbr, dict):
        return False

    has_base_color_factor = "baseColorFactor" in pbr
    has_base_color_texture = "baseColorTexture" in pbr
    if not has_base_color_factor and not has_base_color_texture:
        return False

    if has_base_color_factor and not _has_valid_base_color_factor(pbr):
        return False
    if has_base_color_texture and not _has_valid_base_color_texture(pbr, glb_json, glb_parent):
        return False

    return True


def _has_vertex_color_attribute(attributes: Any, glb_json: dict[str, Any]) -> bool:
    accessors = glb_json.get("accessors")
    color_accessor_index = getattr(attributes, "COLOR_0", None)
    if not _is_valid_index(color_accessor_index, accessors):
        return False

    color_accessor = accessors[color_accessor_index]
    if not isinstance(color_accessor, dict):
        return False

    count = color_accessor.get("count")
    if not _positive_int(count):
        return False

    if color_accessor.get("type") not in _COLOR_ACCESSOR_TYPES:
        return False

    component_type = color_accessor.get("componentType")
    if component_type == _COLOR_FLOAT_COMPONENT_TYPE:
        pass
    elif component_type in _COLOR_NORMALIZED_INTEGER_COMPONENT_TYPES:
        if color_accessor.get("normalized") is not True:
            return False
    else:
        return False

    buffer_views = glb_json.get("bufferViews")
    buffer_view_index = color_accessor.get("bufferView")
    if not (
        _is_valid_index(buffer_view_index, buffer_views)
        and _has_positive_byte_length(buffer_views[buffer_view_index])
    ):
        return False

    position_accessor_index = getattr(attributes, "POSITION", None)
    if _is_valid_index(position_accessor_index, accessors):
        position_accessor = accessors[position_accessor_index]
        if isinstance(position_accessor, dict):
            position_count = position_accessor.get("count")
            if _positive_int(position_count) and count != position_count:
                return False

    return True


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
            if material_index is None and _has_vertex_color_attribute(attributes, glb_json):
                continue

            if not _is_valid_index(material_index, materials):
                primitives_missing_material += 1
                primitives_missing_base_color += 1
                continue

            if not _has_explicit_base_color(materials[material_index], glb_json, path.parent):
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
