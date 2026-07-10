import os
from pathlib import Path

import pytest


@pytest.fixture
def dummy_files(tmp_path):
    """Provides a bunch of dummy files in a temporary directory for tests to use."""
    
    # Create simple dummy files
    csv_file = tmp_path / "data.csv"
    csv_file.write_text("a,b,c\n1,2,3", encoding="utf-8")
    
    md_file = tmp_path / "doc.md"
    md_file.write_text("# Hello World", encoding="utf-8")
    
    # Fake binary file just to have a valid path to feed the mocked commands
    mp4_file = tmp_path / "video.mp4"
    mp4_file.write_bytes(b"fake_video_data")
    
    png_file = tmp_path / "image.png"
    # A valid tiny 1x1 PNG so Pillow doesn't crash if we actually test it
    png_file.write_bytes(
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08"
        b"\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\x0bIDATx\x9cc\xf8\xff\xff"
        b"?\x00\x05\xfe\x02\xfe\xa7\x35\x81\x84\x00\x00\x00\x00IEND\xaeB`\x82"
    )

    return {
        "csv": csv_file,
        "md": md_file,
        "mp4": mp4_file,
        "png": png_file,
        "dir": tmp_path
    }
