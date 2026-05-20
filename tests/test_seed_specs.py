from pathlib import Path

from asset_factory.models import ExportProfile
from asset_factory.specs import load_asset_spec

REPO_ROOT = Path(__file__).resolve().parents[1]
SEED_DIR = REPO_ROOT / "assets" / "seeds"
EXPECTED_EXPORTS = {
    ExportProfile.WEB,
    ExportProfile.UNITY,
    ExportProfile.UNREAL,
}


def test_all_seed_specs_validate():
    seed_paths = sorted(SEED_DIR.glob("*.yaml"))

    assert len(seed_paths) == 10
    for path in seed_paths:
        spec = load_asset_spec(path)
        assert spec.id
        assert spec.learning_goal
        assert set(spec.exports) == EXPECTED_EXPORTS
