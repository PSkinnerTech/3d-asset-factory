from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class RunnerRequest:
    concept_image: Path
    output_dir: Path
    resolution: int = 1024


@dataclass(frozen=True)
class RunnerResult:
    raw_glb_path: Path
    report_path: Path
    runner_type: str
    runner_version: str
    success: bool


class AssetRunner(Protocol):
    def run(self, request: RunnerRequest) -> RunnerResult:
        pass
