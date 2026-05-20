"""Tests for the local Modal bridge at ``scripts/modal_trellis_runner.py``.

The script lives outside the package so we load it via ``importlib.util`` and
exercise its pure helpers without touching the Modal network.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "modal_trellis_runner.py"


def _load_runner_module():
    spec = importlib.util.spec_from_file_location("modal_trellis_runner", _SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["modal_trellis_runner"] = module
    spec.loader.exec_module(module)
    return module


runner = _load_runner_module()


@pytest.fixture
def concept_image(tmp_path: Path) -> Path:
    image = tmp_path / "concept.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\nfake-concept")
    return image


@pytest.fixture
def fake_glb_bytes() -> bytes:
    # glTF magic header (4 bytes) + version (4) + length (4) + filler.
    return b"glTF" + b"\x02\x00\x00\x00" + b"\x40\x00\x00\x00" + b"\x00" * 52


def test_parse_args_uses_defaults(concept_image, tmp_path: Path, monkeypatch):
    monkeypatch.delenv("MODAL_TRELLIS_APP", raising=False)
    monkeypatch.delenv("MODAL_TRELLIS_FUNCTION", raising=False)

    args = runner.parse_args([str(concept_image), str(tmp_path / "out")])

    assert args.image_path == concept_image
    assert args.output_dir == tmp_path / "out"
    assert args.resolution == runner.DEFAULT_RESOLUTION
    assert args.app_name == runner.DEFAULT_APP_NAME
    assert args.function_name == runner.DEFAULT_FUNCTION_NAME
    assert args.raw_glb_path == tmp_path / "out" / "raw.glb"


def test_parse_args_accepts_resolution(concept_image, tmp_path: Path):
    args = runner.parse_args([str(concept_image), str(tmp_path / "out"), "2048"])
    assert args.resolution == 2048


def test_parse_args_honours_env_overrides(concept_image, tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MODAL_TRELLIS_APP", "my-app")
    monkeypatch.setenv("MODAL_TRELLIS_FUNCTION", "my-fn")

    args = runner.parse_args([str(concept_image), str(tmp_path / "out")])

    assert args.app_name == "my-app"
    assert args.function_name == "my-fn"


def test_parse_args_rejects_non_positive_resolution(concept_image, tmp_path: Path):
    with pytest.raises(SystemExit):
        runner.parse_args([str(concept_image), str(tmp_path / "out"), "0"])


def test_parse_args_requires_image_and_output(capsys):
    with pytest.raises(SystemExit):
        runner.parse_args([])
    err = capsys.readouterr().err
    assert "image_path" in err or "usage" in err.lower()


def test_validate_inputs_missing_image(tmp_path: Path):
    args = runner.RunnerArgs(
        image_path=tmp_path / "missing.png",
        output_dir=tmp_path / "out",
        resolution=1024,
        app_name="a",
        function_name="f",
    )
    with pytest.raises(runner.RunnerError, match="concept image not found"):
        runner.validate_inputs(args)


def test_validate_inputs_rejects_empty_image(tmp_path: Path):
    image = tmp_path / "empty.png"
    image.write_bytes(b"")
    args = runner.RunnerArgs(
        image_path=image,
        output_dir=tmp_path / "out",
        resolution=1024,
        app_name="a",
        function_name="f",
    )
    with pytest.raises(runner.RunnerError, match="empty"):
        runner.validate_inputs(args)


def test_validate_inputs_rejects_directory_as_image(tmp_path: Path):
    image_dir = tmp_path / "image_dir"
    image_dir.mkdir()
    args = runner.RunnerArgs(
        image_path=image_dir,
        output_dir=tmp_path / "out",
        resolution=1024,
        app_name="a",
        function_name="f",
    )
    with pytest.raises(runner.RunnerError, match="not a regular file"):
        runner.validate_inputs(args)


def test_validate_glb_bytes_accepts_valid_glb(fake_glb_bytes):
    out = runner.validate_glb_bytes(fake_glb_bytes)
    assert out == fake_glb_bytes


def test_validate_glb_bytes_rejects_non_bytes():
    with pytest.raises(runner.RunnerError, match="expected bytes-like"):
        runner.validate_glb_bytes("not bytes")  # type: ignore[arg-type]


def test_validate_glb_bytes_rejects_short_payload():
    with pytest.raises(runner.RunnerError, match="not a valid GLB"):
        runner.validate_glb_bytes(b"glTF")


def test_validate_glb_bytes_rejects_bad_magic():
    payload = b"NOPE" + b"\x00" * 60
    with pytest.raises(runner.RunnerError, match="missing glTF magic"):
        runner.validate_glb_bytes(payload)


def test_run_writes_raw_glb(concept_image, tmp_path: Path, fake_glb_bytes):
    output_dir = tmp_path / "out"
    args = runner.RunnerArgs(
        image_path=concept_image,
        output_dir=output_dir,
        resolution=1024,
        app_name="a",
        function_name="f",
    )

    captured: dict = {}

    def fake_invoker(call_args, image_bytes):
        captured["args"] = call_args
        captured["image_bytes"] = image_bytes
        return fake_glb_bytes

    result = runner.run(args, invoker=fake_invoker)

    assert result == output_dir / "raw.glb"
    assert result.read_bytes() == fake_glb_bytes
    assert captured["args"] is args
    assert captured["image_bytes"] == concept_image.read_bytes()


def test_run_propagates_invoker_errors(concept_image, tmp_path: Path):
    args = runner.RunnerArgs(
        image_path=concept_image,
        output_dir=tmp_path / "out",
        resolution=1024,
        app_name="a",
        function_name="f",
    )

    def boom(_args, _bytes):
        raise runner.RunnerError("modal blew up")

    with pytest.raises(runner.RunnerError, match="modal blew up"):
        runner.run(args, invoker=boom)


def test_main_returns_zero_on_success(
    concept_image, tmp_path: Path, fake_glb_bytes, monkeypatch, capsys
):
    output_dir = tmp_path / "out"

    def fake_run(args, invoker=None):
        args.output_dir.mkdir(parents=True, exist_ok=True)
        (args.output_dir / "raw.glb").write_bytes(fake_glb_bytes)
        return args.raw_glb_path

    monkeypatch.setattr(runner, "run", fake_run)

    rc = runner.main([str(concept_image), str(output_dir), "1024"])

    assert rc == 0
    assert (output_dir / "raw.glb").read_bytes() == fake_glb_bytes
    out = capsys.readouterr().out
    assert "raw.glb" in out


def test_main_returns_one_on_runner_error(
    concept_image, tmp_path: Path, monkeypatch, capsys
):
    def fake_run(args, invoker=None):
        raise runner.RunnerError("boom from modal")

    monkeypatch.setattr(runner, "run", fake_run)

    rc = runner.main([str(concept_image), str(tmp_path / "out")])

    assert rc == 1
    err = capsys.readouterr().err
    assert "boom from modal" in err
    assert "modal_trellis_runner" in err


def test_main_returns_two_on_argparse_error(capsys):
    rc = runner.main([])
    assert rc == 2


def test_invoke_modal_reports_missing_dependency(concept_image, tmp_path: Path, monkeypatch):
    """If ``modal`` is not importable, we surface a helpful RunnerError."""
    monkeypatch.setitem(sys.modules, "modal", None)
    args = runner.RunnerArgs(
        image_path=concept_image,
        output_dir=tmp_path / "out",
        resolution=1024,
        app_name="a",
        function_name="f",
    )
    with pytest.raises(runner.RunnerError, match="'modal' package"):
        runner.invoke_modal(args, b"image-bytes")
