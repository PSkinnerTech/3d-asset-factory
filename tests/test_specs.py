from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from asset_factory.models import ExportProfile, ScienceSubject, StyleMode
from asset_factory.specs import load_asset_spec


def write_asset_spec(
    path: Path,
    *,
    asset_id: str = "chloroplast_001",
    subject: str = "biology",
    object_name: str = "chloroplast",
    grade_band: str = "6-8",
    style: str = "conceptual",
    learning_goal: str = "Identify the outer membrane, stroma, thylakoids, and grana.",
    exports: str = '["web", "unity", "unreal"]',
    max_triangles: int = 150000,
    max_glb_mb: int = 25,
) -> None:
    path.write_text(
        f"""
id: {asset_id!r}
subject: {subject}
object: {object_name!r}
grade_band: {grade_band!r}
style: {style}
learning_goal: {learning_goal!r}
exports: {exports}
qa:
  max_triangles: {max_triangles}
  max_glb_mb: {max_glb_mb}
""".strip(),
        encoding="utf-8",
    )


def test_loads_valid_asset_spec(tmp_path: Path):
    spec_path = tmp_path / "asset.yaml"
    write_asset_spec(spec_path, asset_id=" chloroplast_001 ")

    spec = load_asset_spec(spec_path)

    assert spec.id == "chloroplast_001"
    assert spec.subject is ScienceSubject.BIOLOGY
    assert spec.style is StyleMode.CONCEPTUAL
    assert spec.exports == [ExportProfile.WEB, ExportProfile.UNITY, ExportProfile.UNREAL]
    assert spec.qa.max_triangles == 150000
    assert spec.qa.max_glb_mb == 25


def test_rejects_invalid_style(tmp_path: Path):
    spec_path = tmp_path / "asset.yaml"
    spec_path.write_text(
        """
id: bad_style
subject: biology
object: cell
grade_band: "6-8"
style: cinematic
learning_goal: Identify a cell.
exports: ["web"]
qa:
  max_triangles: 1000
  max_glb_mb: 10
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError):
        load_asset_spec(spec_path)


def test_rejects_empty_exports(tmp_path: Path):
    spec_path = tmp_path / "asset.yaml"
    write_asset_spec(
        spec_path,
        asset_id="no_exports",
        subject="physics",
        object_name="lever",
        grade_band="3-5",
        learning_goal="Identify the fulcrum and load.",
        exports="[]",
        max_triangles=1000,
        max_glb_mb=10,
    )

    with pytest.raises(ValidationError, match="at least one export"):
        load_asset_spec(spec_path)


@pytest.mark.parametrize(
    ("field_name", "overrides"),
    [
        ("object", {"object_name": "   "}),
        ("grade_band", {"grade_band": "   "}),
        ("learning_goal", {"learning_goal": "   "}),
    ],
)
def test_rejects_whitespace_only_required_text_fields(
    tmp_path: Path,
    field_name: str,
    overrides: dict[str, str],
):
    spec_path = tmp_path / "asset.yaml"
    write_asset_spec(spec_path, **overrides)

    with pytest.raises(ValidationError) as error_info:
        load_asset_spec(spec_path)

    assert field_name in str(error_info.value)


def test_malformed_yaml_includes_path_context(tmp_path: Path):
    spec_path = tmp_path / "asset.yaml"
    spec_path.write_text("id: [unterminated", encoding="utf-8")

    with pytest.raises(ValueError) as error_info:
        load_asset_spec(spec_path)

    assert str(spec_path) in str(error_info.value)
    assert "YAML" in str(error_info.value)
    assert isinstance(error_info.value.__cause__, yaml.YAMLError)


def test_rejects_non_mapping_yaml_with_path_context(tmp_path: Path):
    spec_path = tmp_path / "asset.yaml"
    spec_path.write_text("- chloroplast\n- mitochondrion\n", encoding="utf-8")

    with pytest.raises(ValueError) as error_info:
        load_asset_spec(spec_path)

    message = str(error_info.value)
    assert str(spec_path) in message
    assert "YAML mapping" in message
