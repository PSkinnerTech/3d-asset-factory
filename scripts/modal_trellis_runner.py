"""Bridge between TRELLIS2_COMMAND and a Modal-hosted TRELLIS.2 function.

This script is invoked as a subprocess by ``TrellisCommandRunner`` with the
arguments expanded from the ``TRELLIS2_COMMAND`` template. It:

1. Parses ``image_path``, ``output_dir``, and an optional ``resolution``.
2. Validates the inputs (image exists, output dir is creatable).
3. Reads the concept image bytes locally.
4. Calls the deployed Modal function ``trellis_generate`` with those bytes.
5. Writes the returned GLB bytes to ``{output_dir}/raw.glb``.
6. Exits 0 on success, non-zero with a clear stderr message otherwise.

It deliberately does not import Modal at module import time so the unit tests
can exercise the pure helpers without the dependency.

Usage:

    python scripts/modal_trellis_runner.py <image_path> <output_dir> [resolution]

Environment variables:

    MODAL_TRELLIS_APP       Modal app name (default: "trellis2-inference").
    MODAL_TRELLIS_FUNCTION  Modal function name (default: "trellis_generate").
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path

DEFAULT_APP_NAME = "trellis2-inference"
DEFAULT_FUNCTION_NAME = "trellis_generate"
DEFAULT_RESOLUTION = 1024
GLB_MAGIC = b"glTF"


class RunnerError(Exception):
    """Raised when the Modal runner cannot satisfy its output contract."""


@dataclass(frozen=True)
class RunnerArgs:
    image_path: Path
    output_dir: Path
    resolution: int
    app_name: str
    function_name: str

    @property
    def raw_glb_path(self) -> Path:
        return self.output_dir / "raw.glb"


def parse_args(argv: list[str]) -> RunnerArgs:
    parser = argparse.ArgumentParser(
        prog="modal_trellis_runner.py",
        description="Run TRELLIS.2 on Modal and write raw.glb locally.",
    )
    parser.add_argument("image_path", type=Path, help="Path to the concept image (PNG/JPEG).")
    parser.add_argument("output_dir", type=Path, help="Directory to write raw.glb into.")
    parser.add_argument(
        "resolution",
        nargs="?",
        type=int,
        default=DEFAULT_RESOLUTION,
        help=f"Optional resolution hint (default: {DEFAULT_RESOLUTION}).",
    )
    parser.add_argument(
        "--app-name",
        default=os.environ.get("MODAL_TRELLIS_APP", DEFAULT_APP_NAME),
        help="Modal app name to look up the function on.",
    )
    parser.add_argument(
        "--function-name",
        default=os.environ.get("MODAL_TRELLIS_FUNCTION", DEFAULT_FUNCTION_NAME),
        help="Modal function name within the app.",
    )
    namespace = parser.parse_args(argv)

    if namespace.resolution <= 0:
        parser.error(f"resolution must be a positive integer, got {namespace.resolution!r}")

    return RunnerArgs(
        image_path=namespace.image_path,
        output_dir=namespace.output_dir,
        resolution=namespace.resolution,
        app_name=namespace.app_name,
        function_name=namespace.function_name,
    )


def validate_inputs(args: RunnerArgs) -> None:
    if not args.image_path.exists():
        raise RunnerError(f"concept image not found: {args.image_path}")
    if not args.image_path.is_file():
        raise RunnerError(f"concept image is not a regular file: {args.image_path}")
    if args.image_path.stat().st_size == 0:
        raise RunnerError(f"concept image is empty: {args.image_path}")


def ensure_output_dir(args: RunnerArgs) -> None:
    args.output_dir.mkdir(parents=True, exist_ok=True)
    if not args.output_dir.is_dir():
        raise RunnerError(f"output path is not a directory: {args.output_dir}")


def validate_glb_bytes(payload: object) -> bytes:
    if not isinstance(payload, (bytes, bytearray, memoryview)):
        raise RunnerError(
            f"Modal function returned {type(payload).__name__}, expected bytes-like GLB payload"
        )
    data = bytes(payload)
    if len(data) < 12:
        raise RunnerError(f"Modal function returned only {len(data)} bytes; not a valid GLB")
    if not data.startswith(GLB_MAGIC):
        head = data[:4]
        raise RunnerError(
            f"Modal function payload missing glTF magic header; got first 4 bytes={head!r}"
        )
    return data


def write_glb(args: RunnerArgs, payload: bytes) -> Path:
    raw_glb = args.raw_glb_path
    raw_glb.write_bytes(payload)
    if not raw_glb.exists() or raw_glb.stat().st_size == 0:
        raise RunnerError(f"failed to persist raw.glb at {raw_glb}")
    return raw_glb


def invoke_modal(args: RunnerArgs, image_bytes: bytes) -> object:
    """Call the deployed Modal function. Imported lazily so tests can mock it."""
    try:
        import modal  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RunnerError(
            "the 'modal' package is required on the controller; install with "
            "`python -m pip install 'modal>=0.64'` and run `modal token new`."
        ) from exc

    try:
        fn = modal.Function.from_name(args.app_name, args.function_name)
    except AttributeError as exc:
        raise RunnerError(
            "this Modal SDK is too old: `modal.Function.from_name` is unavailable. "
            "Upgrade with `python -m pip install --upgrade 'modal>=0.64'`."
        ) from exc
    except Exception as exc:
        raise RunnerError(
            f"could not look up Modal function {args.app_name}::{args.function_name}: {exc}. "
            "Have you run `modal deploy infra/modal_trellis.py`?"
        ) from exc

    try:
        return fn.remote(image_bytes, args.resolution)
    except Exception as exc:
        raise RunnerError(
            f"Modal function {args.app_name}::{args.function_name} raised: {exc}"
        ) from exc


def run(args: RunnerArgs, *, invoker=invoke_modal) -> Path:
    """Orchestrate the runner using an injectable invoker for testability."""
    validate_inputs(args)
    ensure_output_dir(args)
    image_bytes = args.image_path.read_bytes()
    payload = invoker(args, image_bytes)
    glb_bytes = validate_glb_bytes(payload)
    return write_glb(args, glb_bytes)


def main(argv: list[str] | None = None) -> int:
    raw_argv = sys.argv[1:] if argv is None else argv
    try:
        args = parse_args(raw_argv)
    except SystemExit as exc:
        return int(exc.code) if isinstance(exc.code, int) else 2

    try:
        raw_glb = run(args)
    except RunnerError as exc:
        print(f"modal_trellis_runner: {exc}", file=sys.stderr)
        return 1

    print(f"wrote {raw_glb}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
