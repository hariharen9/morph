from typer.testing import CliRunner

from morph.cli import app

runner = CliRunner()


def test_formats_command():
    result = runner.invoke(app, ["formats"])
    assert result.exit_code == 0
    assert "morph" in result.stdout
    assert "document" in result.stdout
    assert "video" in result.stdout


def test_deps_command():
    result = runner.invoke(app, ["deps"])
    assert result.exit_code == 0
    assert "Tool" in result.stdout
    assert "ffmpeg" in result.stdout
    assert "pandoc" in result.stdout


def test_convert_invalid_file():
    result = runner.invoke(app, ["does_not_exist.csv", "out.xlsx"])
    assert result.exit_code != 0


def test_convert_unsupported_path():
    # Make sure we give a graceful error for unknown extension paths
    result = runner.invoke(app, ["fake.unknown_ext1", "fake.unknown_ext2"])
    assert result.exit_code != 0
