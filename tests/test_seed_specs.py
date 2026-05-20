from pathlib import Path

from asset_factory.specs import load_asset_spec


def test_all_seed_specs_validate():
    seed_paths = sorted(Path("assets/seeds").glob("*.yaml"))

    assert len(seed_paths) == 10
    for path in seed_paths:
        spec = load_asset_spec(path)
        assert spec.id
        assert spec.learning_goal
        assert spec.exports
