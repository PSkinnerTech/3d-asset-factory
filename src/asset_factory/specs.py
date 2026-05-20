from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from asset_factory.models import AssetSpec


def load_asset_spec(path: Path | str) -> AssetSpec:
    spec_path = Path(path)
    raw = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"Asset spec must be a YAML mapping: {spec_path}")
    data: dict[str, Any] = dict(raw)
    data["source_path"] = spec_path
    return AssetSpec.model_validate(data)
