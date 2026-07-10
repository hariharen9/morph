from pathlib import Path
from morph.converters.web import url_to_md, url_to_html

def test_url_to_md(tmp_path, mocker):
    # Mock the internal trafilatura calls inside morph.converters.web
    mock_fetch = mocker.patch("morph.converters.web.trafilatura.fetch_url", return_value="<html><body>Mock Data</body></html>")
    mock_extract = mocker.patch("morph.converters.web.trafilatura.extract", return_value="# Mock Data")
    
    out_file = tmp_path / "out.md"
    url = "https://example.com/test"
    
    result = url_to_md(url, out_file)
    
    mock_fetch.assert_called_once_with(url)
    mock_extract.assert_called_once_with("<html><body>Mock Data</body></html>", output_format="markdown")
    
    assert result.output.exists()
    assert result.output.read_text(encoding="utf-8") == "# Mock Data"


def test_url_to_html(tmp_path, mocker):
    mock_fetch = mocker.patch("morph.converters.web.trafilatura.fetch_url", return_value="<html><body>Raw dump</body></html>")
    
    out_file = tmp_path / "out.html"
    url = "http://example.org"
    
    result = url_to_html(url, out_file)
    
    mock_fetch.assert_called_once_with(url)
    
    assert result.output.exists()
    assert result.output.read_text(encoding="utf-8") == "<html><body>Raw dump</body></html>"
