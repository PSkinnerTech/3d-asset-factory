import json
import struct
from collections.abc import Callable
from pathlib import Path

import trimesh
from pygltflib import GLTF2

from asset_factory.models import AssetSpec, ExportProfile, QaThresholds, ScienceSubject, StyleMode
from asset_factory.qa import run_qa

_GLB_HEADER_LENGTH = 12
_GLB_CHUNK_HEADER_LENGTH = 8
_JSON_CHUNK_TYPE = 0x4E4F534A
_BIN_CHUNK_TYPE = 0x004E4942


def make_spec(max_triangles: int = 1000, max_glb_mb: int = 10) -> AssetSpec:
    return AssetSpec(
        id="qa_asset",
        subject=ScienceSubject.PHYSICS,
        object="cube",
        grade_band="3-5",
        style=StyleMode.CONCEPTUAL,
        learning_goal="Inspect a cube.",
        exports=[ExportProfile.WEB],
        qa=QaThresholds(max_triangles=max_triangles, max_glb_mb=max_glb_mb),
    )


def write_box(path: Path) -> None:
    mesh = trimesh.creation.box(extents=(1, 1, 1))
    material = trimesh.visual.material.PBRMaterial(baseColorFactor=[0.78, 0.47, 0.31, 1.0])
    mesh.visual = trimesh.visual.TextureVisuals(material=material)
    mesh.export(path)


def write_box_without_material(path: Path) -> None:
    mesh = trimesh.creation.box(extents=(1, 1, 1))
    mesh.visual = None
    mesh.export(path)


def write_vertex_colored_box(path: Path) -> None:
    mesh = trimesh.creation.box(extents=(1, 1, 1))
    mesh.visual = trimesh.visual.ColorVisuals(
        mesh=mesh,
        vertex_colors=[[199, 120, 79, 255]] * len(mesh.vertices),
    )
    mesh.export(path)


def write_vertex_colored_box_with_invalid_color_accessor(path: Path) -> None:
    write_vertex_colored_box(path)

    def mutate(glb_json: dict) -> None:
        primitive = glb_json["meshes"][0]["primitives"][0]
        primitive["attributes"]["COLOR_0"] = len(glb_json.get("accessors", []))

    mutate_glb_json(path, mutate)


def write_vertex_colored_box_with_empty_color_accessor(path: Path) -> None:
    write_vertex_colored_box(path)

    def mutate(glb_json: dict) -> None:
        primitive = glb_json["meshes"][0]["primitives"][0]
        color_accessor = glb_json["accessors"][primitive["attributes"]["COLOR_0"]]
        color_accessor["count"] = 0

    mutate_glb_json(path, mutate)


def write_vertex_colored_box_with_dataless_color_accessor(path: Path) -> None:
    write_vertex_colored_box(path)

    def mutate(glb_json: dict) -> None:
        primitive = glb_json["meshes"][0]["primitives"][0]
        color_accessor = glb_json["accessors"][primitive["attributes"]["COLOR_0"]]
        color_accessor["count"] = 1
        color_accessor.pop("bufferView", None)
        color_accessor.pop("sparse", None)

    mutate_glb_json(path, mutate)


def write_materialless_box_with_scalar_color_accessor(path: Path) -> None:
    write_box_without_material(path)

    def mutate(glb_json: dict) -> None:
        primitive = glb_json["meshes"][0]["primitives"][0]
        primitive["attributes"]["COLOR_0"] = primitive["indices"]

    mutate_glb_json(path, mutate)


def write_vertex_colored_box_with_mismatched_color_count(path: Path) -> None:
    write_vertex_colored_box(path)

    def mutate(glb_json: dict) -> None:
        primitive = glb_json["meshes"][0]["primitives"][0]
        position_accessor = glb_json["accessors"][primitive["attributes"]["POSITION"]]
        mismatched_color_accessor = dict(position_accessor)
        mismatched_color_accessor["count"] = position_accessor["count"] - 1
        primitive["attributes"]["COLOR_0"] = len(glb_json["accessors"])
        glb_json["accessors"].append(mismatched_color_accessor)

    mutate_glb_json(path, mutate)


def write_vertex_colored_box_with_color_accessor_metadata(
    path: Path, component_type: int, normalized: object = None, extra_color_bytes: int = 0
) -> None:
    write_vertex_colored_box(path)

    def mutate(glb_json: dict) -> None:
        primitive = glb_json["meshes"][0]["primitives"][0]
        color_accessor = glb_json["accessors"][primitive["attributes"]["COLOR_0"]]
        color_accessor["componentType"] = component_type
        if extra_color_bytes:
            glb_json["bufferViews"][color_accessor["bufferView"]]["byteLength"] += extra_color_bytes
            glb_json["buffers"][0]["byteLength"] += extra_color_bytes
        if normalized is None:
            color_accessor.pop("normalized", None)
        else:
            color_accessor["normalized"] = normalized

    mutate_glb_json(path, mutate, extra_bin_bytes=extra_color_bytes)


def write_mixed_material_scene(path: Path) -> None:
    materialized = trimesh.creation.box(extents=(1, 1, 1))
    material = trimesh.visual.material.PBRMaterial(baseColorFactor=[0.78, 0.47, 0.31, 1.0])
    materialized.visual = trimesh.visual.TextureVisuals(material=material)

    materialless = trimesh.creation.box(extents=(1, 1, 1))
    materialless.apply_translation((2, 0, 0))
    materialless.visual = None

    scene = trimesh.Scene()
    scene.add_geometry(materialized, node_name="with_material")
    scene.add_geometry(materialless, node_name="without_material")
    scene.export(path)


def write_box_with_negative_material_index(path: Path) -> None:
    write_box(path)
    gltf = GLTF2.load(path)
    gltf.meshes[0].primitives[0].material = -1
    gltf.save(path)


def write_box_without_explicit_base_color(path: Path) -> None:
    write_box(path)
    gltf = GLTF2.load(path)
    pbr = gltf.materials[0].pbrMetallicRoughness
    pbr.baseColorFactor = None
    pbr.baseColorTexture = None
    gltf.save(path)


def mutate_glb_json(path: Path, mutate: Callable[[dict], None], extra_bin_bytes: int = 0) -> None:
    data = path.read_bytes()
    magic, version, _length = struct.unpack_from("<4sII", data, 0)
    chunks = []
    offset = _GLB_HEADER_LENGTH
    while offset + _GLB_CHUNK_HEADER_LENGTH <= len(data):
        chunk_length, chunk_type = struct.unpack_from("<II", data, offset)
        offset += _GLB_CHUNK_HEADER_LENGTH
        chunk_data = data[offset : offset + chunk_length]
        offset += chunk_length

        if chunk_type == _JSON_CHUNK_TYPE:
            glb_json = json.loads(chunk_data.rstrip(b" \t\r\n\x00").decode("utf-8"))
            mutate(glb_json)
            chunk_data = json.dumps(glb_json, separators=(",", ":")).encode("utf-8")
            chunk_data += b" " * (-len(chunk_data) % 4)
            chunk_length = len(chunk_data)

        if chunk_type == _BIN_CHUNK_TYPE and extra_bin_bytes:
            chunk_data += b"\x00" * extra_bin_bytes
            chunk_data += b"\x00" * (-len(chunk_data) % 4)
            chunk_length = len(chunk_data)

        chunks.append(struct.pack("<II", chunk_length, chunk_type) + chunk_data)

    body = b"".join(chunks)
    path.write_bytes(struct.pack("<4sII", magic, version, _GLB_HEADER_LENGTH + len(body)) + body)


def write_box_with_base_color_factor(path: Path, factor: object) -> None:
    write_box(path)

    def mutate(glb_json: dict) -> None:
        pbr = glb_json["materials"][0].setdefault("pbrMetallicRoughness", {})
        pbr["baseColorFactor"] = factor
        pbr.pop("baseColorTexture", None)

    mutate_glb_json(path, mutate)


def write_box_with_invalid_base_color_texture_index(path: Path) -> None:
    write_box(path)

    def mutate(glb_json: dict) -> None:
        pbr = glb_json["materials"][0].setdefault("pbrMetallicRoughness", {})
        pbr.pop("baseColorFactor", None)
        pbr["baseColorTexture"] = {"index": 999}

    mutate_glb_json(path, mutate)


def write_box_with_valid_factor_and_invalid_base_color_texture_index(path: Path) -> None:
    write_box(path)

    def mutate(glb_json: dict) -> None:
        pbr = glb_json["materials"][0].setdefault("pbrMetallicRoughness", {})
        pbr["baseColorFactor"] = [0.78, 0.47, 0.31, 1.0]
        pbr["baseColorTexture"] = {"index": 999}

    mutate_glb_json(path, mutate)


def write_box_with_valid_texture_and_base_color_factor(path: Path, factor: object) -> None:
    write_box(path)
    (path.parent / "texture.png").write_bytes(b"png")

    def mutate(glb_json: dict) -> None:
        pbr = glb_json["materials"][0].setdefault("pbrMetallicRoughness", {})
        pbr["baseColorFactor"] = factor
        pbr["baseColorTexture"] = {"index": 0}
        glb_json["textures"] = [{"source": 0}]
        glb_json["images"] = [{"uri": "texture.png"}]

    mutate_glb_json(path, mutate)


def write_box_with_base_color_texture_uri(path: Path, uri: str) -> None:
    write_box(path)

    def mutate(glb_json: dict) -> None:
        pbr = glb_json["materials"][0].setdefault("pbrMetallicRoughness", {})
        pbr.pop("baseColorFactor", None)
        pbr["baseColorTexture"] = {"index": 0}
        glb_json["textures"] = [{"source": 0}]
        glb_json["images"] = [{"uri": uri}]

    mutate_glb_json(path, mutate)


def write_box_with_empty_base_color_texture_image(path: Path) -> None:
    write_box(path)

    def mutate(glb_json: dict) -> None:
        pbr = glb_json["materials"][0].setdefault("pbrMetallicRoughness", {})
        pbr.pop("baseColorFactor", None)
        pbr["baseColorTexture"] = {"index": 0}
        glb_json["textures"] = [{"source": 0}]
        glb_json["images"] = [{}]

    mutate_glb_json(path, mutate)


def write_box_with_base_color_texture_data_uri(path: Path, uri: str) -> None:
    write_box(path)

    def mutate(glb_json: dict) -> None:
        pbr = glb_json["materials"][0].setdefault("pbrMetallicRoughness", {})
        pbr.pop("baseColorFactor", None)
        pbr["baseColorTexture"] = {"index": 0}
        glb_json["textures"] = [{"source": 0}]
        glb_json["images"] = [{"uri": uri}]

    mutate_glb_json(path, mutate)


def write_box_with_zero_byte_base_color_texture_buffer_view(path: Path) -> None:
    write_box(path)

    def mutate(glb_json: dict) -> None:
        pbr = glb_json["materials"][0].setdefault("pbrMetallicRoughness", {})
        pbr.pop("baseColorFactor", None)
        pbr["baseColorTexture"] = {"index": 0}
        glb_json["textures"] = [{"source": 0}]
        buffer_views = glb_json.setdefault("bufferViews", [])
        image_buffer_view_index = len(buffer_views)
        buffer_views.append({"buffer": 0, "byteOffset": 0, "byteLength": 0})
        glb_json["images"] = [{"bufferView": image_buffer_view_index, "mimeType": "image/png"}]

    mutate_glb_json(path, mutate)


def write_box_with_bool_material_index(path: Path) -> None:
    write_box(path)

    def mutate(glb_json: dict) -> None:
        glb_json["meshes"][0]["primitives"][0]["material"] = False

    mutate_glb_json(path, mutate)


def write_large_materialized_mesh(path: Path) -> None:
    mesh = trimesh.creation.icosphere(subdivisions=6, radius=1)
    material = trimesh.visual.material.PBRMaterial(baseColorFactor=[0.78, 0.47, 0.31, 1.0])
    mesh.visual = trimesh.visual.TextureVisuals(material=material)
    mesh.export(path)


def test_qa_passes_valid_glb(tmp_path: Path):
    glb_path = tmp_path / "asset.glb"
    glb_path.parent.mkdir(parents=True, exist_ok=True)
    write_box(glb_path)

    report = run_qa(make_spec(), glb_path)

    assert report.passed is True
    assert report.blocking_failures == []
    assert report.metrics["triangles"] == 12
    assert report.metrics["primitive_count"] == 1
    assert report.metrics["primitives_missing_material"] == 0
    assert report.metrics["primitives_missing_base_color"] == 0
    assert report.metrics["file_size_bytes"] > 0


def test_qa_passes_vertex_colored_glb(tmp_path: Path):
    glb_path = tmp_path / "asset.glb"
    write_vertex_colored_box(glb_path)

    report = run_qa(make_spec(), glb_path)

    assert report.passed is True
    assert report.blocking_failures == []
    assert report.metrics["triangles"] == 12
    assert report.metrics["primitive_count"] == 1
    assert report.metrics["primitives_missing_material"] == 0
    assert report.metrics["primitives_missing_base_color"] == 0


def test_qa_blocks_invalid_vertex_color_accessor(tmp_path: Path):
    glb_path = tmp_path / "asset.glb"
    write_vertex_colored_box_with_invalid_color_accessor(glb_path)

    report = run_qa(make_spec(), glb_path)

    assert report.passed is False
    assert "Required material data is missing" in report.blocking_failures
    assert "Required base color data is missing" in report.blocking_failures
    assert report.metrics["primitive_count"] == 1
    assert report.metrics["primitives_missing_material"] == 1
    assert report.metrics["primitives_missing_base_color"] == 1


def test_qa_blocks_empty_vertex_color_accessor(tmp_path: Path):
    glb_path = tmp_path / "asset.glb"
    write_vertex_colored_box_with_empty_color_accessor(glb_path)

    report = run_qa(make_spec(), glb_path)

    assert report.passed is False
    assert "Required material data is missing" in report.blocking_failures
    assert "Required base color data is missing" in report.blocking_failures
    assert report.metrics["primitive_count"] == 1
    assert report.metrics["primitives_missing_material"] == 1
    assert report.metrics["primitives_missing_base_color"] == 1


def test_qa_blocks_dataless_vertex_color_accessor(tmp_path: Path):
    glb_path = tmp_path / "asset.glb"
    write_vertex_colored_box_with_dataless_color_accessor(glb_path)

    report = run_qa(make_spec(), glb_path)

    assert report.passed is False
    assert "Required material data is missing" in report.blocking_failures
    assert "Required base color data is missing" in report.blocking_failures
    assert report.metrics["primitive_count"] == 1
    assert report.metrics["primitives_missing_material"] == 1
    assert report.metrics["primitives_missing_base_color"] == 1


def test_qa_blocks_scalar_index_accessor_as_vertex_color(tmp_path: Path):
    glb_path = tmp_path / "asset.glb"
    write_materialless_box_with_scalar_color_accessor(glb_path)

    report = run_qa(make_spec(), glb_path)

    assert report.passed is False
    assert "Required material data is missing" in report.blocking_failures
    assert "Required base color data is missing" in report.blocking_failures
    assert report.metrics["primitive_count"] == 1
    assert report.metrics["primitives_missing_material"] == 1
    assert report.metrics["primitives_missing_base_color"] == 1


def test_qa_blocks_mismatched_vertex_color_count(tmp_path: Path):
    glb_path = tmp_path / "asset.glb"
    write_vertex_colored_box_with_mismatched_color_count(glb_path)

    report = run_qa(make_spec(), glb_path)

    assert report.passed is False
    assert "Required material data is missing" in report.blocking_failures
    assert "Required base color data is missing" in report.blocking_failures
    assert report.metrics["primitive_count"] == 1
    assert report.metrics["primitives_missing_material"] == 1
    assert report.metrics["primitives_missing_base_color"] == 1


def test_qa_blocks_unnormalized_unsigned_byte_vertex_color_accessor(tmp_path: Path):
    glb_path = tmp_path / "asset.glb"
    write_vertex_colored_box_with_color_accessor_metadata(glb_path, component_type=5121)

    report = run_qa(make_spec(), glb_path)

    assert report.passed is False
    assert "Required material data is missing" in report.blocking_failures
    assert "Required base color data is missing" in report.blocking_failures
    assert report.metrics["primitive_count"] == 1
    assert report.metrics["primitives_missing_material"] == 1
    assert report.metrics["primitives_missing_base_color"] == 1


def test_qa_blocks_signed_byte_vertex_color_accessor(tmp_path: Path):
    glb_path = tmp_path / "asset.glb"
    write_vertex_colored_box_with_color_accessor_metadata(
        glb_path, component_type=5120, normalized=True
    )

    report = run_qa(make_spec(), glb_path)

    assert report.passed is False
    assert "Required material data is missing" in report.blocking_failures
    assert "Required base color data is missing" in report.blocking_failures
    assert report.metrics["primitive_count"] == 1
    assert report.metrics["primitives_missing_material"] == 1
    assert report.metrics["primitives_missing_base_color"] == 1


def test_qa_blocks_signed_short_vertex_color_accessor(tmp_path: Path):
    glb_path = tmp_path / "asset.glb"
    write_vertex_colored_box_with_color_accessor_metadata(
        glb_path, component_type=5122, normalized=True, extra_color_bytes=32
    )

    report = run_qa(make_spec(), glb_path)

    assert report.passed is False
    assert "Required material data is missing" in report.blocking_failures
    assert "Required base color data is missing" in report.blocking_failures
    assert report.metrics["primitive_count"] == 1
    assert report.metrics["primitives_missing_material"] == 1
    assert report.metrics["primitives_missing_base_color"] == 1


def test_qa_blocks_missing_glb(tmp_path: Path):
    report = run_qa(make_spec(), tmp_path / "missing.glb")

    assert report.passed is False
    assert "GLB file is missing" in report.blocking_failures


def test_qa_blocks_triangle_budget(tmp_path: Path):
    glb_path = tmp_path / "asset.glb"
    write_box(glb_path)

    report = run_qa(make_spec(max_triangles=1), glb_path)

    assert report.passed is False
    assert "Triangle count 12 exceeds max_triangles 1" in report.blocking_failures


def test_qa_blocks_missing_material_and_base_color(tmp_path: Path):
    glb_path = tmp_path / "asset.glb"
    write_box_without_material(glb_path)

    report = run_qa(make_spec(), glb_path)

    assert report.passed is False
    assert "Required material data is missing" in report.blocking_failures
    assert "Required base color data is missing" in report.blocking_failures
    assert report.metrics["triangles"] == 12
    assert report.metrics["primitive_count"] == 1
    assert report.metrics["primitives_missing_material"] == 1
    assert report.metrics["primitives_missing_base_color"] == 1
    assert report.metrics["file_size_bytes"] > 0


def test_qa_blocks_mixed_material_coverage(tmp_path: Path):
    glb_path = tmp_path / "asset.glb"
    write_mixed_material_scene(glb_path)

    report = run_qa(make_spec(), glb_path)

    assert report.passed is False
    assert "Required material data is missing" in report.blocking_failures
    assert "Required base color data is missing" in report.blocking_failures
    assert report.metrics["triangles"] == 24
    assert report.metrics["primitive_count"] == 2
    assert report.metrics["primitives_missing_material"] == 1
    assert report.metrics["primitives_missing_base_color"] == 1


def test_qa_blocks_negative_material_index(tmp_path: Path):
    glb_path = tmp_path / "asset.glb"
    write_box_with_negative_material_index(glb_path)

    report = run_qa(make_spec(), glb_path)

    assert report.passed is False
    assert "Required material data is missing" in report.blocking_failures
    assert "Required base color data is missing" in report.blocking_failures
    assert report.metrics["primitive_count"] == 1
    assert report.metrics["primitives_missing_material"] == 1
    assert report.metrics["primitives_missing_base_color"] == 1


def test_qa_blocks_material_without_explicit_base_color(tmp_path: Path):
    glb_path = tmp_path / "asset.glb"
    write_box_without_explicit_base_color(glb_path)

    report = run_qa(make_spec(), glb_path)

    assert report.passed is False
    assert "Required material data is missing" not in report.blocking_failures
    assert "Required base color data is missing" in report.blocking_failures
    assert report.metrics["primitive_count"] == 1
    assert report.metrics["primitives_missing_material"] == 0
    assert report.metrics["primitives_missing_base_color"] == 1


def test_qa_blocks_null_base_color_factor(tmp_path: Path):
    glb_path = tmp_path / "asset.glb"
    write_box_with_base_color_factor(glb_path, None)

    report = run_qa(make_spec(), glb_path)

    assert report.passed is False
    assert "Required material data is missing" not in report.blocking_failures
    assert "Required base color data is missing" in report.blocking_failures
    assert report.metrics["primitive_count"] == 1
    assert report.metrics["primitives_missing_material"] == 0
    assert report.metrics["primitives_missing_base_color"] == 1


def test_qa_blocks_wrong_length_base_color_factor(tmp_path: Path):
    glb_path = tmp_path / "asset.glb"
    write_box_with_base_color_factor(glb_path, [0.78, 0.47, 0.31])

    report = run_qa(make_spec(), glb_path)

    assert report.passed is False
    assert "Required material data is missing" not in report.blocking_failures
    assert "Required base color data is missing" in report.blocking_failures
    assert report.metrics["primitive_count"] == 1
    assert report.metrics["primitives_missing_material"] == 0
    assert report.metrics["primitives_missing_base_color"] == 1


def test_qa_blocks_out_of_range_base_color_factor(tmp_path: Path):
    glb_path = tmp_path / "asset.glb"
    write_box_with_base_color_factor(glb_path, [-1, 2, 0.5, 1])

    report = run_qa(make_spec(), glb_path)

    assert report.passed is False
    assert "Required material data is missing" not in report.blocking_failures
    assert "Required base color data is missing" in report.blocking_failures
    assert report.metrics["primitive_count"] == 1
    assert report.metrics["primitives_missing_material"] == 0
    assert report.metrics["primitives_missing_base_color"] == 1


def test_qa_blocks_invalid_base_color_texture_index(tmp_path: Path):
    glb_path = tmp_path / "asset.glb"
    write_box_with_invalid_base_color_texture_index(glb_path)

    report = run_qa(make_spec(), glb_path)

    assert report.passed is False
    assert "Required material data is missing" not in report.blocking_failures
    assert "Required base color data is missing" in report.blocking_failures
    assert report.metrics["primitive_count"] == 1
    assert report.metrics["primitives_missing_material"] == 0
    assert report.metrics["primitives_missing_base_color"] == 1


def test_qa_blocks_valid_factor_with_invalid_base_color_texture_index(tmp_path: Path):
    glb_path = tmp_path / "asset.glb"
    write_box_with_valid_factor_and_invalid_base_color_texture_index(glb_path)

    report = run_qa(make_spec(), glb_path)

    assert report.passed is False
    assert "Required material data is missing" not in report.blocking_failures
    assert "Required base color data is missing" in report.blocking_failures
    assert report.metrics["primitive_count"] == 1
    assert report.metrics["primitives_missing_material"] == 0
    assert report.metrics["primitives_missing_base_color"] == 1


def test_qa_blocks_valid_texture_with_out_of_range_base_color_factor(tmp_path: Path):
    glb_path = tmp_path / "asset.glb"
    write_box_with_valid_texture_and_base_color_factor(glb_path, [-1, 2, 0.5, 1])

    report = run_qa(make_spec(), glb_path)

    assert report.passed is False
    assert "Required material data is missing" not in report.blocking_failures
    assert "Required base color data is missing" in report.blocking_failures
    assert report.metrics["primitive_count"] == 1
    assert report.metrics["primitives_missing_material"] == 0
    assert report.metrics["primitives_missing_base_color"] == 1


def test_qa_blocks_empty_base_color_texture_image(tmp_path: Path):
    glb_path = tmp_path / "asset.glb"
    write_box_with_empty_base_color_texture_image(glb_path)

    report = run_qa(make_spec(), glb_path)

    assert report.passed is False
    assert "Required material data is missing" not in report.blocking_failures
    assert "Required base color data is missing" in report.blocking_failures
    assert report.metrics["primitive_count"] == 1
    assert report.metrics["primitives_missing_material"] == 0
    assert report.metrics["primitives_missing_base_color"] == 1


def test_qa_blocks_missing_external_base_color_texture_uri(tmp_path: Path):
    glb_path = tmp_path / "asset.glb"
    write_box_with_base_color_texture_uri(glb_path, "missing-texture.png")

    report = run_qa(make_spec(), glb_path)

    assert report.passed is False
    assert "Required material data is missing" not in report.blocking_failures
    assert "Required base color data is missing" in report.blocking_failures
    assert report.metrics["primitive_count"] == 1
    assert report.metrics["primitives_missing_material"] == 0
    assert report.metrics["primitives_missing_base_color"] == 1


def test_qa_passes_external_base_color_texture_uri_with_sibling_file(tmp_path: Path):
    glb_path = tmp_path / "asset.glb"
    (tmp_path / "texture.png").write_bytes(b"png")
    write_box_with_base_color_texture_uri(glb_path, "texture.png")

    report = run_qa(make_spec(), glb_path)

    assert report.passed is True
    assert report.blocking_failures == []
    assert report.metrics["primitive_count"] == 1
    assert report.metrics["primitives_missing_material"] == 0
    assert report.metrics["primitives_missing_base_color"] == 0


def test_qa_blocks_empty_base_color_texture_data_uri(tmp_path: Path):
    glb_path = tmp_path / "asset.glb"
    write_box_with_base_color_texture_data_uri(glb_path, "data:image/png;base64,")

    report = run_qa(make_spec(), glb_path)

    assert report.passed is False
    assert "Required material data is missing" not in report.blocking_failures
    assert "Required base color data is missing" in report.blocking_failures
    assert report.metrics["primitive_count"] == 1
    assert report.metrics["primitives_missing_material"] == 0
    assert report.metrics["primitives_missing_base_color"] == 1


def test_qa_blocks_zero_byte_base_color_texture_buffer_view(tmp_path: Path):
    glb_path = tmp_path / "asset.glb"
    write_box_with_zero_byte_base_color_texture_buffer_view(glb_path)

    report = run_qa(make_spec(), glb_path)

    assert report.passed is False
    assert "Required material data is missing" not in report.blocking_failures
    assert "Required base color data is missing" in report.blocking_failures
    assert report.metrics["primitive_count"] == 1
    assert report.metrics["primitives_missing_material"] == 0
    assert report.metrics["primitives_missing_base_color"] == 1


def test_qa_blocks_bool_material_index(tmp_path: Path):
    glb_path = tmp_path / "asset.glb"
    write_box_with_bool_material_index(glb_path)

    report = run_qa(make_spec(), glb_path)

    assert report.passed is False
    assert "Required material data is missing" in report.blocking_failures
    assert "Required base color data is missing" in report.blocking_failures
    assert report.metrics["primitive_count"] == 1
    assert report.metrics["primitives_missing_material"] == 1
    assert report.metrics["primitives_missing_base_color"] == 1


def test_qa_blocks_malformed_glb_without_crashing(tmp_path: Path):
    glb_path = tmp_path / "broken.glb"
    glb_path.write_bytes(b"not a glb")

    report = run_qa(make_spec(), glb_path)

    assert report.passed is False
    assert len(report.blocking_failures) == 1
    assert report.blocking_failures[0].startswith("GLB cannot be parsed:")
    assert report.metrics == {}


def test_qa_blocks_file_size_budget(tmp_path: Path):
    glb_path = tmp_path / "asset.glb"
    write_large_materialized_mesh(glb_path)

    report = run_qa(make_spec(max_triangles=200_000, max_glb_mb=1), glb_path)

    assert report.passed is False
    assert any(
        failure.startswith("GLB size ") and failure.endswith(" bytes exceeds max_glb_mb 1")
        for failure in report.blocking_failures
    )
    assert report.metrics["file_size_bytes"] > 1024 * 1024
