import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from asset_factory.manifest import create_initial_manifest, read_manifest, write_manifest
from asset_factory.models import AssetSpec, ExportProfile, QaThresholds, ScienceSubject, StyleMode
from asset_factory.runs import create_run_layout


def make_spec() -> AssetSpec:
    return AssetSpec(
        id="lever_001",
        subject=ScienceSubject.PHYSICS,
        object="lever",
        grade_band="3-5",
        style=StyleMode.CONCEPTUAL,
        learning_goal="Identify the fulcrum, effort, and load.",
        exports=[ExportProfile.WEB, ExportProfile.UNITY],
        qa=QaThresholds(max_triangles=100000, max_glb_mb=20),
        source_path=Path("assets/seeds/lever_conceptual.yaml"),
    )


def test_create_run_layout_writes_expected_directories(tmp_path: Path):
    layout = create_run_layout(make_spec(), tmp_path, timestamp="20260520T120000Z")

    assert layout.run_dir == tmp_path / "runs" / "lever_001" / "20260520T120000Z"
    assert (
        layout.manifest_path
        == tmp_path / "runs" / "lever_001" / "20260520T120000Z" / "manifest.json"
    )
    assert layout.input_dir.is_dir()
    assert layout.image_dir.is_dir()
    assert layout.trellis_dir.is_dir()
    assert layout.optimize_dir.is_dir()
    assert layout.previews_dir.is_dir()
    assert layout.exports_dir.is_dir()
    assert layout.reports_dir.is_dir()


def test_create_run_layout_rejects_existing_run_directory(tmp_path: Path):
    run_dir = tmp_path / "runs" / "lever_001" / "20260520T120000Z"
    run_dir.mkdir(parents=True)

    with pytest.raises(FileExistsError):
        create_run_layout(make_spec(), tmp_path, timestamp="20260520T120000Z")


def test_create_run_layout_copies_source_spec_to_input(tmp_path: Path):
    source_path = tmp_path / "lever_conceptual.yaml"
    source_path.write_text("id: lever_001\n", encoding="utf-8")
    spec = make_spec().model_copy(update={"source_path": source_path})

    layout = create_run_layout(spec, tmp_path, timestamp="20260520T120000Z")

    assert (layout.input_dir / "asset.yaml").read_text(encoding="utf-8") == "id: lever_001\n"


def test_manifest_round_trip(tmp_path: Path):
    spec = make_spec()
    layout = create_run_layout(spec, tmp_path, timestamp="20260520T120000Z")
    manifest = create_initial_manifest(spec, layout, datetime(2026, 5, 20, 12, tzinfo=UTC))

    write_manifest(layout.manifest_path, manifest)
    loaded = read_manifest(layout.manifest_path)

    assert loaded.asset.id == "lever_001"
    assert loaded.education.learning_goal == "Identify the fulcrum, effort, and load."
    assert loaded.review.state == "generated"
    assert loaded.files.manifest == "manifest.json"
    manifest_json = json.loads(layout.manifest_path.read_text(encoding="utf-8"))
    assert manifest_json["asset"]["id"] == "lever_001"


def test_read_manifest_rejects_unknown_nested_fields(tmp_path: Path):
    spec = make_spec()
    layout = create_run_layout(spec, tmp_path, timestamp="20260520T120000Z")
    manifest = create_initial_manifest(spec, layout, datetime(2026, 5, 20, 12, tzinfo=UTC))
    write_manifest(layout.manifest_path, manifest)
    manifest_json = json.loads(layout.manifest_path.read_text(encoding="utf-8"))
    manifest_json["asset"]["unexpected"] = "ignored before strict validation"
    layout.manifest_path.write_text(json.dumps(manifest_json), encoding="utf-8")

    with pytest.raises(ValidationError):
        read_manifest(layout.manifest_path)
