from pathlib import Path

import pytest
from pydantic import ValidationError

from asset_factory.models import ExportProfile, ScienceSubject, StyleMode
from asset_factory.specs import load_asset_spec


def test_loads_valid_asset_spec(tmp_path: Path):
    spec_path = tmp_path / "asset.yaml"
    spec_path.write_text(
        """
id: chloroplast_001
subject: biology
object: chloroplast
grade_band: "6-8"
style: conceptual
learning_goal: Identify the outer membrane, stroma, thylakoids, and grana.
exports: ["web", "unity", "unreal"]
qa:
  max_triangles: 150000
  max_glb_mb: 25
""".strip(),
        encoding="utf-8",
    )

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
    spec_path.write_text(
        """
id: no_exports
subject: physics
object: lever
grade_band: "3-5"
style: conceptual
learning_goal: Identify the fulcrum and load.
exports: []
qa:
  max_triangles: 1000
  max_glb_mb: 10
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError, match="at least one export"):
        load_asset_spec(spec_path)
