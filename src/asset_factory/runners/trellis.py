from __future__ import annotations

import json
import os
import shlex
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime

from asset_factory.runners.base import RunnerRequest, RunnerResult


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

        command = self.command_template.format(
            image=request.concept_image,
            output=request.output_dir,
            resolution=request.resolution,
        )
        started_at = datetime.now(tz=UTC)
        completed = subprocess.run(
            shlex.split(command),
            check=False,
            capture_output=True,
            text=True,
        )
        ended_at = datetime.now(tz=UTC)
        success = completed.returncode == 0 and raw_glb_path.exists()

        report = {
            "runner_type": self.runner_type,
            "runner_version": self.runner_version,
            "command": command,
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "started_at": started_at.isoformat(),
            "ended_at": ended_at.isoformat(),
            "raw_glb": str(raw_glb_path),
            "resolution": request.resolution,
            "success": success,
        }
        report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

        if not success:
            raise RuntimeError(f"TRELLIS command failed; see {report_path}")

        return RunnerResult(
            raw_glb_path=raw_glb_path,
            report_path=report_path,
            runner_type=self.runner_type,
            runner_version=self.runner_version,
            success=True,
        )
