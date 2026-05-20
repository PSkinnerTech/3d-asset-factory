import importlib
import sys

from typer.testing import CliRunner

from asset_factory import __version__


def test_package_version_is_exposed():
    assert __version__ == "0.1.0"


def test_cli_help_renders():
    from asset_factory.cli import app

    result = CliRunner().invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "generate" in result.output
    assert "review" in result.output


def test_cli_import_does_not_import_review():
    module_names = (
        "asset_factory.cli",
        "asset_factory.pipeline",
        "asset_factory.review",
    )
    previous_modules = {name: sys.modules.get(name) for name in module_names}

    try:
        for name in module_names:
            sys.modules.pop(name, None)

        importlib.import_module("asset_factory.cli")

        assert "asset_factory.review" not in sys.modules
    finally:
        for name in module_names:
            sys.modules.pop(name, None)
        for name, module in previous_modules.items():
            if module is not None:
                sys.modules[name] = module
