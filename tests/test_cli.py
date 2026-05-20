import json
from pathlib import Path

from typer.testing import CliRunner

from asset_factory.cli import app


def write_spec(path: Path) -> Path:
    path.write_text(
        """
id: cli_pulley
subject: physics
object: pulley
grade_band: "3-5"
style: conceptual
learning_goal: Identify how a pulley changes the direction of force.
exports:
  - web
qa:
  max_triangles: 150000
  max_glb_mb: 25
  max_texture_px: 4096
""".lstrip(),
        encoding="utf-8",
    )
    return path


def generate_run(tmp_path: Path) -> tuple[CliRunner, Path]:
    spec_path = write_spec(tmp_path / "asset.yaml")
    runner = CliRunner()

    generate_result = runner.invoke(
        app,
        ["generate", str(spec_path), "--root-dir", str(tmp_path), "--runner", "mock"],
    )
    assert generate_result.exit_code == 0, generate_result.output
    run_dir = Path(generate_result.output.strip().split("Generated run: ", maxsplit=1)[1])
    return runner, run_dir


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def assert_package_local_manifest(manifest: dict, profile: str) -> None:
    assert manifest["files"]["optimized_glb"] == "asset.glb"
    assert manifest["files"]["thumbnail"] == "thumbnail.png"
    assert manifest["files"]["turntable"] == "turntable.webm"
    assert manifest["files"]["qa_report"] == "qa.json"
    assert manifest["files"]["raw_glb"] is None
    assert manifest["files"]["concept_image"] is None
    assert manifest["files"]["review_html"] is None
    assert manifest["files"]["exports"] == {profile: "."}


def set_copied_spec_max_triangles(run_dir: Path, max_triangles: int) -> None:
    copied_spec = run_dir / "input" / "asset.yaml"
    lines = copied_spec.read_text(encoding="utf-8").splitlines()
    updated = [
        f"  max_triangles: {max_triangles}" if line.strip().startswith("max_triangles:") else line
        for line in lines
    ]
    copied_spec.write_text("\n".join(updated) + "\n", encoding="utf-8")


def recover_failed_qa_run(tmp_path: Path) -> tuple[CliRunner, Path]:
    runner, run_dir = generate_run(tmp_path)
    set_copied_spec_max_triangles(run_dir, 1)

    failed_result = runner.invoke(app, ["qa", str(run_dir)])
    assert failed_result.exit_code == 0, failed_result.output
    assert "QA passed: False" in failed_result.output

    set_copied_spec_max_triangles(run_dir, 150000)
    passed_result = runner.invoke(app, ["qa", str(run_dir)])
    assert passed_result.exit_code == 0, passed_result.output
    assert "QA passed: True" in passed_result.output
    return runner, run_dir


def test_generate_with_mock_runner(tmp_path: Path):
    spec_path = write_spec(tmp_path / "asset.yaml")

    result = CliRunner().invoke(
        app,
        ["generate", str(spec_path), "--root-dir", str(tmp_path), "--runner", "mock"],
    )

    assert result.exit_code == 0, result.output
    assert "Generated run:" in result.output
    assert (tmp_path / "runs" / "cli_pulley").exists()


def test_qa_command_reports_existing_run(tmp_path: Path):
    runner, run_dir = generate_run(tmp_path)

    qa_result = runner.invoke(app, ["qa", str(run_dir)])

    assert qa_result.exit_code == 0, qa_result.output
    assert "QA passed: True" in qa_result.output


def test_export_updates_existing_export_manifests(tmp_path: Path):
    runner, run_dir = generate_run(tmp_path)

    export_result = runner.invoke(app, ["export", str(run_dir), "--profile", "unity"])

    assert export_result.exit_code == 0, export_result.output
    root_manifest = read_json(run_dir / "manifest.json")
    web_manifest = read_json(run_dir / "exports" / "web" / "manifest.json")
    unity_manifest = read_json(run_dir / "exports" / "unity" / "manifest.json")
    assert set(root_manifest["files"]["exports"]) == {"web", "unity"}
    assert root_manifest["files"]["optimized_glb"] == str(run_dir / "optimize" / "asset.glb")
    assert root_manifest["files"]["thumbnail"] == str(run_dir / "previews" / "thumbnail.png")
    assert root_manifest["files"]["turntable"] == str(run_dir / "previews" / "turntable.webm")
    assert root_manifest["files"]["qa_report"] == str(run_dir / "reports" / "qa.json")
    assert_package_local_manifest(web_manifest, "web")
    assert_package_local_manifest(unity_manifest, "unity")


def test_export_does_not_advertise_incomplete_profile_dirs(tmp_path: Path):
    runner, run_dir = generate_run(tmp_path)
    partial_export_dir = run_dir / "exports" / "unreal"
    partial_export_dir.mkdir()

    export_result = runner.invoke(app, ["export", str(run_dir), "--profile", "unity"])

    assert export_result.exit_code == 0, export_result.output
    root_manifest = read_json(run_dir / "manifest.json")
    assert set(root_manifest["files"]["exports"]) == {"web", "unity"}
    assert "unreal" not in root_manifest["files"]["exports"]
    assert not (partial_export_dir / "asset.glb").exists()


def test_export_does_not_complete_or_later_advertise_near_complete_profile_dirs(tmp_path: Path):
    runner, run_dir = generate_run(tmp_path)
    partial_export_dir = run_dir / "exports" / "unreal"
    partial_export_dir.mkdir()
    for package_file in ("asset.glb", "thumbnail.png", "turntable.webm", "IMPORT_NOTES.md"):
        (partial_export_dir / package_file).write_text("stale partial export\n", encoding="utf-8")
    root_manifest_path = run_dir / "manifest.json"
    root_manifest = read_json(root_manifest_path)
    root_manifest["files"]["exports"]["unreal"] = str(partial_export_dir)
    root_manifest_path.write_text(
        json.dumps(root_manifest, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    first_export_result = runner.invoke(app, ["export", str(run_dir), "--profile", "unity"])
    second_export_result = runner.invoke(app, ["export", str(run_dir), "--profile", "unity"])

    assert first_export_result.exit_code == 0, first_export_result.output
    assert second_export_result.exit_code == 0, second_export_result.output
    root_manifest = read_json(run_dir / "manifest.json")
    assert set(root_manifest["files"]["exports"]) == {"web", "unity"}
    assert "unreal" not in root_manifest["files"]["exports"]
    assert not (partial_export_dir / "manifest.json").exists()
    assert not (partial_export_dir / "qa.json").exists()


def test_qa_failure_clears_advertised_exports(tmp_path: Path):
    runner, run_dir = generate_run(tmp_path)
    review_html_path = run_dir / "reports" / "review.html"
    assert "QA Passed" in review_html_path.read_text(encoding="utf-8")
    set_copied_spec_max_triangles(run_dir, 1)

    qa_result = runner.invoke(app, ["qa", str(run_dir)])

    assert qa_result.exit_code == 0, qa_result.output
    assert "QA passed: False" in qa_result.output
    root_manifest = read_json(run_dir / "manifest.json")
    qa_report = read_json(run_dir / "reports" / "qa.json")
    review_html = review_html_path.read_text(encoding="utf-8")
    assert root_manifest["qa"]["passed"] is False
    assert root_manifest["files"]["exports"] == {}
    assert qa_report["passed"] is False
    assert "QA Needs review" in review_html
    assert "Triangle count" in review_html
    assert not (run_dir / "exports" / "web").exists()


def test_qa_pass_resyncs_existing_export_package_with_local_manifest(tmp_path: Path):
    runner, run_dir = generate_run(tmp_path)
    web_manifest_path = run_dir / "exports" / "web" / "manifest.json"
    web_manifest_path.write_text(
        (run_dir / "manifest.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    qa_result = runner.invoke(app, ["qa", str(run_dir)])

    assert qa_result.exit_code == 0, qa_result.output
    assert "QA passed: True" in qa_result.output
    root_manifest = read_json(run_dir / "manifest.json")
    root_qa_report = read_json(run_dir / "reports" / "qa.json")
    web_manifest = read_json(run_dir / "exports" / "web" / "manifest.json")
    web_qa_report = read_json(run_dir / "exports" / "web" / "qa.json")

    assert root_manifest["qa"]["passed"] is True
    assert root_manifest["files"]["exports"] == {
        "web": str(run_dir / "exports" / "web"),
    }
    assert root_qa_report["passed"] is True
    assert web_manifest["qa"]["passed"] is True
    assert_package_local_manifest(web_manifest, "web")
    assert web_qa_report["passed"] is True


def test_nested_manifest_export_path_is_not_synced_or_advertised(tmp_path: Path):
    runner, run_dir = generate_run(tmp_path)
    nested_dir = run_dir / "exports" / "stale" / "unity"
    nested_dir.mkdir(parents=True)
    for package_file in (
        "asset.glb",
        "thumbnail.png",
        "turntable.webm",
        "qa.json",
        "IMPORT_NOTES.md",
    ):
        (nested_dir / package_file).write_text("stale nested export\n", encoding="utf-8")
    marker_manifest = {"marker": "do not overwrite"}
    (nested_dir / "manifest.json").write_text(
        json.dumps(marker_manifest, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    root_manifest_path = run_dir / "manifest.json"
    root_manifest = read_json(root_manifest_path)
    root_manifest["files"]["exports"]["unity"] = str(nested_dir)
    root_manifest_path.write_text(
        json.dumps(root_manifest, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    qa_result = runner.invoke(app, ["qa", str(run_dir)])

    assert qa_result.exit_code == 0, qa_result.output
    assert "QA passed: True" in qa_result.output
    root_manifest = read_json(run_dir / "manifest.json")
    assert root_manifest["files"]["exports"] == {
        "web": str(run_dir / "exports" / "web"),
    }
    assert read_json(nested_dir / "manifest.json") == marker_manifest


def test_qa_does_not_sync_export_paths_outside_exports_root(tmp_path: Path):
    runner, run_dir = generate_run(tmp_path)
    external_dir = tmp_path / "external-export"
    external_dir.mkdir()
    root_manifest_path = run_dir / "manifest.json"
    root_manifest = read_json(root_manifest_path)
    root_manifest["files"]["exports"]["web"] = str(external_dir)
    root_manifest_path.write_text(
        json.dumps(root_manifest, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    qa_result = runner.invoke(app, ["qa", str(run_dir)])

    assert qa_result.exit_code == 0, qa_result.output
    assert "QA passed: True" in qa_result.output
    assert not (external_dir / "manifest.json").exists()
    assert not (external_dir / "qa.json").exists()


def test_export_after_qa_recovery_syncs_old_and_new_export_packages(tmp_path: Path):
    runner, run_dir = recover_failed_qa_run(tmp_path)

    export_result = runner.invoke(app, ["export", str(run_dir), "--profile", "unity"])

    assert export_result.exit_code == 0, export_result.output
    root_manifest = read_json(run_dir / "manifest.json")
    unity_manifest = read_json(run_dir / "exports" / "unity" / "manifest.json")
    assert root_manifest["files"]["exports"] == {
        "unity": str(run_dir / "exports" / "unity"),
    }
    assert not (run_dir / "exports" / "web").exists()
    assert_package_local_manifest(unity_manifest, "unity")


def test_export_refuses_failed_qa_run(tmp_path: Path):
    runner, run_dir = generate_run(tmp_path)
    set_copied_spec_max_triangles(run_dir, 1)

    qa_result = runner.invoke(app, ["qa", str(run_dir)])
    assert qa_result.exit_code == 0, qa_result.output
    assert "QA passed: False" in qa_result.output

    export_result = runner.invoke(app, ["export", str(run_dir), "--profile", "unity"])

    root_manifest = read_json(run_dir / "manifest.json")
    assert export_result.exit_code != 0
    assert "Cannot export" in export_result.output
    assert "QA" in export_result.output
    assert root_manifest["files"]["exports"] == {}
    assert not (run_dir / "exports" / "unity").exists()
