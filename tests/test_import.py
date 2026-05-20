from typer.testing import CliRunner

from asset_factory import __version__
from asset_factory.cli import app


def test_package_version_is_exposed():
    assert __version__ == "0.1.0"


def test_cli_help_renders():
    result = CliRunner().invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "generate" in result.output
    assert "review" in result.output
