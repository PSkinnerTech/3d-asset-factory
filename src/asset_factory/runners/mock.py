from __future__ import annotations

import json
from datetime import UTC, datetime

import trimesh

from asset_factory.runners.base import RunnerRequest, RunnerResult


class MockRunner:
    runner_type = "mock"
    runner_version = "0.1.0"

    def run(self, request: RunnerRequest) -> RunnerResult:
        request.output_dir.mkdir(parents=True, exist_ok=True)
        raw_glb_path = request.output_dir / "raw.glb"
        report_path = request.output_dir / "raw_report.json"

        started_at = datetime.now(tz=UTC)
        mesh = trimesh.creation.box(extents=(1.0, 1.0, 1.0))
        mesh.visual = trimesh.visual.ColorVisuals(mesh, vertex_colors=[90, 140, 210, 255])
        mesh.export(raw_glb_path)
        ended_at = datetime.now(tz=UTC)

        report = {
            "runner_type": self.runner_type,
            "runner_version": self.runner_version,
            "resolution": request.resolution,
            "concept_image": str(request.concept_image),
            "raw_glb": str(raw_glb_path),
            "started_at": started_at.isoformat(),
            "ended_at": ended_at.isoformat(),
            "success": True,
        }
        report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
        return RunnerResult(
            raw_glb_path=raw_glb_path,
            report_path=report_path,
            runner_type=self.runner_type,
            runner_version=self.runner_version,
            success=True,
        )
