import sys
from pathlib import Path

from asset_factory.runners.base import RunnerRequest
from asset_factory.runners.trellis import TrellisCommandRunner


def test_trellis_runner_requires_env(monkeypatch):
    monkeypatch.delenv("TRELLIS2_COMMAND", raising=False)

    try:
        TrellisCommandRunner.from_env()
    except RuntimeError as exc:
        assert "TRELLIS2_COMMAND" in str(exc)
    else:
        raise AssertionError("TrellisCommandRunner.from_env should require TRELLIS2_COMMAND")


def test_trellis_runner_executes_command_template(tmp_path: Path, monkeypatch):
    script = tmp_path / "fake_trellis.py"
    script.write_text(
        """
from pathlib import Path
import sys
out = Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
(out / "raw.glb").write_bytes(b"glTF-fake")
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setenv("TRELLIS2_COMMAND", f"{sys.executable} {script} {{image}} {{output}}")
    image = tmp_path / "concept.png"
    image.write_bytes(b"png")

    runner = TrellisCommandRunner.from_env()
    result = runner.run(RunnerRequest(concept_image=image, output_dir=tmp_path / "trellis"))

    assert result.raw_glb_path.read_bytes() == b"glTF-fake"
    assert result.report_path.exists()
    assert result.runner_type == "trellis"
    assert result.success is True
