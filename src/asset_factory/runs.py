from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from asset_factory.models import AssetSpec


@dataclass(frozen=True)
class RunLayout:
    root_dir: Path
    run_dir: Path
    input_dir: Path
    image_dir: Path
    trellis_dir: Path
    optimize_dir: Path
    previews_dir: Path
    exports_dir: Path
    reports_dir: Path
    manifest_path: Path


def utc_timestamp() -> str:
    return datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")


def create_run_layout(
    spec: AssetSpec,
    root_dir: Path | str,
    timestamp: str | None = None,
) -> RunLayout:
    root = Path(root_dir)
    stamp = timestamp or utc_timestamp()
    run_dir = root / "runs" / spec.id / stamp
    layout = RunLayout(
        root_dir=root,
        run_dir=run_dir,
        input_dir=run_dir / "input",
        image_dir=run_dir / "image",
        trellis_dir=run_dir / "trellis",
        optimize_dir=run_dir / "optimize",
        previews_dir=run_dir / "previews",
        exports_dir=run_dir / "exports",
        reports_dir=run_dir / "reports",
        manifest_path=run_dir / "manifest.json",
    )
    layout.run_dir.mkdir(parents=True, exist_ok=False)
    for directory in (
        layout.input_dir,
        layout.image_dir,
        layout.trellis_dir,
        layout.optimize_dir,
        layout.previews_dir,
        layout.exports_dir,
        layout.reports_dir,
    ):
        directory.mkdir(exist_ok=False)
    if spec.source_path and spec.source_path.exists():
        shutil.copy2(spec.source_path, layout.input_dir / "asset.yaml")
    return layout
