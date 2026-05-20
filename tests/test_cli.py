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
    spec_path = write_spec(tmp_path / "asset.yaml")
    runner = CliRunner()

    generate_result = runner.invoke(
        app,
        ["generate", str(spec_path), "--root-dir", str(tmp_path), "--runner", "mock"],
    )
    assert generate_result.exit_code == 0, generate_result.output
    run_dir = Path(generate_result.output.strip().split("Generated run: ", maxsplit=1)[1])

    qa_result = runner.invoke(app, ["qa", str(run_dir)])

    assert qa_result.exit_code == 0, qa_result.output
    assert "QA passed: True" in qa_result.output


def test_export_updates_existing_export_manifests(tmp_path: Path):
    spec_path = write_spec(tmp_path / "asset.yaml")
    runner = CliRunner()

    generate_result = runner.invoke(
        app,
        ["generate", str(spec_path), "--root-dir", str(tmp_path), "--runner", "mock"],
    )
    assert generate_result.exit_code == 0, generate_result.output
    run_dir = Path(generate_result.output.strip().split("Generated run: ", maxsplit=1)[1])

    export_result = runner.invoke(app, ["export", str(run_dir), "--profile", "unity"])

    assert export_result.exit_code == 0, export_result.output
    root_manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    web_manifest = json.loads(
        (run_dir / "exports" / "web" / "manifest.json").read_text(encoding="utf-8")
    )
    unity_manifest = json.loads(
        (run_dir / "exports" / "unity" / "manifest.json").read_text(encoding="utf-8")
    )
    assert set(root_manifest["files"]["exports"]) == {"web", "unity"}
    assert web_manifest == root_manifest
    assert unity_manifest == root_manifest


def test_qa_failure_clears_advertised_exports(tmp_path: Path):
    spec_path = write_spec(tmp_path / "asset.yaml")
    runner = CliRunner()

    generate_result = runner.invoke(
        app,
        ["generate", str(spec_path), "--root-dir", str(tmp_path), "--runner", "mock"],
    )
    assert generate_result.exit_code == 0, generate_result.output
    run_dir = Path(generate_result.output.strip().split("Generated run: ", maxsplit=1)[1])
    spec_path.unlink()
    copied_spec = run_dir / "input" / "asset.yaml"
    failing_spec = copied_spec.read_text(encoding="utf-8").replace(
        "max_triangles: 150000",
        "max_triangles: 1",
    )
    copied_spec.write_text(
        failing_spec,
        encoding="utf-8",
    )

    qa_result = runner.invoke(app, ["qa", str(run_dir)])

    assert qa_result.exit_code == 0, qa_result.output
    assert "QA passed: False" in qa_result.output
    root_manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    qa_report = json.loads((run_dir / "reports" / "qa.json").read_text(encoding="utf-8"))
    assert root_manifest["qa"]["passed"] is False
    assert root_manifest["files"]["exports"] == {}
    assert qa_report["passed"] is False
