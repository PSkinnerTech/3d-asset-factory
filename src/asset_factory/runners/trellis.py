from __future__ import annotations

import json
import os
import shlex
import string
import subprocess
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from asset_factory.runners.base import RunnerRequest, RunnerResult

_SUPPORTED_PLACEHOLDERS = frozenset({"image", "output", "resolution"})


@dataclass(frozen=True)
class TrellisCommandRunner:
    command_template: str

    runner_type = "trellis"
    runner_version = "trellis2-command"

    @classmethod
    def from_env(cls) -> TrellisCommandRunner:
        command_template = os.environ.get("TRELLIS2_COMMAND")
        if not command_template:
            raise RuntimeError(
                "TRELLIS2_COMMAND is required, for example: "
                "python /path/to/trellis2.py {image} {output}"
            )
        return cls(command_template=command_template)

    def run(self, request: RunnerRequest) -> RunnerResult:
        request.output_dir.mkdir(parents=True, exist_ok=True)
        raw_glb_path = request.output_dir / "raw.glb"
        report_path = request.output_dir / "raw_report.json"

        started_at = datetime.now(tz=UTC)
        command: str | None = None
        command_args: list[str] | None = None
        returncode: int | None = None
        stdout: str | None = None
        stderr: str | None = None
        error_type: str | None = None
        error_message: str | None = None

        try:
            command_args = _build_command_args(self.command_template, request)
            command = shlex.join(command_args)
            completed = subprocess.run(
                command_args,
                check=False,
                capture_output=True,
                text=True,
            )
            returncode = completed.returncode
            stdout = completed.stdout
            stderr = completed.stderr
            if completed.returncode != 0:
                error_type = "NonZeroReturnCodeError"
                error_message = f"TRELLIS command exited with status {completed.returncode}"
            elif not raw_glb_path.exists():
                error_type = "MissingRawGlbError"
                error_message = f"TRELLIS command completed but did not create {raw_glb_path}"
        except (OSError, ValueError) as exc:
            error_type = type(exc).__name__
            error_message = str(exc)
        ended_at = datetime.now(tz=UTC)

        success = error_type is None and returncode == 0 and raw_glb_path.exists()
        _write_report(
            report_path=report_path,
            runner_type=self.runner_type,
            runner_version=self.runner_version,
            request=request,
            raw_glb_path=raw_glb_path,
            started_at=started_at,
            ended_at=ended_at,
            success=success,
            command_template=self.command_template,
            command=command,
            command_args=command_args,
            returncode=returncode,
            stdout=stdout,
            stderr=stderr,
            error_type=error_type,
            error_message=error_message,
        )

        if not success:
            raise RuntimeError(f"TRELLIS command failed; see {report_path}")

        return RunnerResult(
            raw_glb_path=raw_glb_path,
            report_path=report_path,
            runner_type=self.runner_type,
            runner_version=self.runner_version,
            success=True,
        )


def _build_command_args(command_template: str, request: RunnerRequest) -> list[str]:
    placeholder_values = {
        "image": str(request.concept_image),
        "output": str(request.output_dir),
        "resolution": str(request.resolution),
    }
    sentinel_command, placeholder_tokens = _build_sentinel_command(command_template)
    try:
        sentinel_args = shlex.split(sentinel_command)
    except ValueError as exc:
        raise ValueError(f"Invalid TRELLIS2_COMMAND shell syntax: {exc}") from exc
    if not sentinel_args:
        raise ValueError("TRELLIS2_COMMAND must include an executable")

    command_args: list[str] = []
    for arg in sentinel_args:
        for token, placeholder in placeholder_tokens.items():
            arg = arg.replace(token, placeholder_values[placeholder])
        command_args.append(arg)
    return command_args


def _build_sentinel_command(command_template: str) -> tuple[str, dict[str, str]]:
    formatter = string.Formatter()
    parts: list[str] = []
    placeholder_tokens: dict[str, str] = {}
    try:
        parsed_template = formatter.parse(command_template)
        for index, (
            literal_text,
            field_name,
            format_spec,
            conversion,
        ) in enumerate(parsed_template):
            parts.append(literal_text)
            if field_name is None:
                continue
            if field_name not in _SUPPORTED_PLACEHOLDERS:
                raise ValueError(
                    f"Unsupported placeholder {{{field_name}}}; supported placeholders are "
                    "{image}, {output}, and {resolution}"
                )
            if format_spec or conversion:
                raise ValueError(
                    f"Unsupported format syntax for {{{field_name}}}; use only "
                    "{image}, {output}, or {resolution}"
                )
            token = f"__TRELLIS_PLACEHOLDER_{index}_{uuid.uuid4().hex}__"
            placeholder_tokens[token] = field_name
            parts.append(token)
    except ValueError as exc:
        if str(exc).startswith(("Unsupported placeholder", "Unsupported format syntax")):
            raise
        raise ValueError(f"Invalid TRELLIS2_COMMAND format: {exc}") from exc
    return "".join(parts), placeholder_tokens


def _write_report(
    *,
    report_path: Path,
    runner_type: str,
    runner_version: str,
    request: RunnerRequest,
    raw_glb_path: Path,
    started_at: datetime,
    ended_at: datetime,
    success: bool,
    command_template: str,
    command: str | None,
    command_args: list[str] | None,
    returncode: int | None,
    stdout: str | None,
    stderr: str | None,
    error_type: str | None,
    error_message: str | None,
) -> None:
    report = {
        "runner_type": runner_type,
        "runner_version": runner_version,
        "command_template": command_template,
        "command": command,
        "command_args": command_args,
        "returncode": returncode,
        "stdout": stdout,
        "stderr": stderr,
        "started_at": started_at.isoformat(),
        "ended_at": ended_at.isoformat(),
        "raw_glb": str(raw_glb_path),
        "resolution": request.resolution,
        "concept_image": str(request.concept_image),
        "success": success,
    }
    if error_type is not None:
        report["error_type"] = error_type
    if error_message is not None:
        report["error_message"] = error_message
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
