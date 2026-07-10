from pathlib import Path

import pytest



def test_pandas_native_conversion(dummy_files):
    # Actually test csv -> parquet
    # PyArrow and pandas are installed, so this will work natively
    from morph.converters.pandas_extra import csv_to_parquet
    
    csv_file = dummy_files["csv"]
    parquet_out = dummy_files["dir"] / "out.parquet"
    
    result = csv_to_parquet(csv_file, parquet_out)
    
    assert result.output.exists()
    assert result.output.stat().st_size > 0


def test_ffmpeg_video_conversion_mocked(dummy_files, mocker):
    # We don't want to actually run ffmpeg, so we mock `run_ffmpeg`
    mock_run = mocker.patch("morph.converters.video.run_ffmpeg")
    from morph.converters.video import _video_convert
    
    mp4_file = dummy_files["mp4"]
    mkv_out = dummy_files["dir"] / "out.mkv"
    
    # We pass in some options to ensure they get appended
    _video_convert(
        mp4_file, 
        mkv_out, 
        resolution="1920x1080",
        fps=30,
        crf=18
    )
    
    # Verify the command construction
    mock_run.assert_called_once()
    called_cmd = mock_run.call_args[0][0]
    
    # Assert critical flags are in the ffmpeg command array
    assert "ffmpeg" in called_cmd
    assert "-i" in called_cmd
    assert str(mp4_file) in called_cmd
    assert "-r" in called_cmd
    assert "30" in called_cmd
    assert "-crf" in called_cmd
    assert "18" in called_cmd
    assert "-vf" in called_cmd
    assert any("scale=1920:1080" in flag for flag in called_cmd)


def test_ffmpeg_extract_audio_mocked(dummy_files, mocker):
    mock_run = mocker.patch("morph.converters.video.run_ffmpeg")
    from morph.converters.video import _extract_audio
    
    mp4_file = dummy_files["mp4"]
    mp3_out = dummy_files["dir"] / "out.mp3"
    
    _extract_audio(mp4_file, mp3_out, bitrate="192k")
    
    called_cmd = mock_run.call_args[0][0]
    assert "-vn" in called_cmd  # Video null (extract audio)
    assert "-b:a" in called_cmd
    assert "192k" in called_cmd


def test_pandoc_fallback_mocked(dummy_files, mocker):
    """Test that pandoc correctly falls back to pdflatex if xelatex fails."""
    # We mock subprocess.run in documents.py
    # xelatex fails (returncode 1), pdflatex succeeds (returncode 0)
    mock_run = mocker.patch("morph.converters.documents.subprocess.run")
    
    class MockCompletedProcess:
        def __init__(self, returncode, stderr):
            self.returncode = returncode
            self.stderr = stderr
            self.stdout = b""

    def mock_run_side_effect(cmd, **kwargs):
        if "xelatex" in cmd:
            return MockCompletedProcess(1, b"xelatex error")
        return MockCompletedProcess(0, b"")
        
    mock_run.side_effect = mock_run_side_effect
    mocker.patch("morph.converters.documents.shutil.which", return_value="path")
    
    from morph.converters.documents import _pandoc_convert
    
    md_file = dummy_files["md"]
    pdf_out = dummy_files["dir"] / "out.pdf"
    
    _pandoc_convert(md_file, pdf_out, src="md", dst="pdf")
    
    # It should have called subprocess.run at least twice (one for xelatex, one for pdflatex fallback)
    assert mock_run.call_count >= 2
    first_call_cmd = mock_run.call_args_list[0][0][0]
    assert "--pdf-engine" in first_call_cmd
    assert "xelatex" in first_call_cmd
