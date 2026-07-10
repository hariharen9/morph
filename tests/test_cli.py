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

def test_config_command(monkeypatch, tmp_path):
    # Mock home directory to prevent overwriting real user config
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    
    # 1. First run generates the file
    result = runner.invoke(app, ["config"])
    assert result.exit_code == 0
    assert "Generated full configuration file" in result.stdout
    assert (tmp_path / ".morphrc").exists()
    
    # 2. Check the content
    content = (tmp_path / ".morphrc").read_text(encoding="utf-8")
    assert "Morph Configuration File" in content
    assert "global:" in content
    
    # 3. Second run refuses to overwrite
    result2 = runner.invoke(app, ["config"])
    assert result2.exit_code == 1
    assert "already exists" in result2.stdout
