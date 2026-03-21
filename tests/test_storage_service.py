"""Tests for file storage service."""

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
import tempfile
import shutil

from app.services.storage_service import save_file


class TestSaveFile:
    @patch("app.services.storage_service.settings")
    def test_creates_file_and_returns_relative_path(self, mock_settings):
        tmp_dir = tempfile.mkdtemp()
        mock_settings.STORAGE_PATH = tmp_dir

        try:
            result = save_file("tx123", "documents", "photo.jpg", b"fake image data")

            assert result.startswith("tx123/documents/")
            assert result.endswith(".jpg")

            full_path = Path(tmp_dir) / result
            assert full_path.exists()
            assert full_path.read_bytes() == b"fake image data"
        finally:
            shutil.rmtree(tmp_dir)

    @patch("app.services.storage_service.settings")
    def test_creates_nested_directories(self, mock_settings):
        tmp_dir = tempfile.mkdtemp()
        mock_settings.STORAGE_PATH = tmp_dir

        try:
            save_file("tx999", "liveness", "video.mp4", b"video")

            dir_path = Path(tmp_dir) / "tx999" / "liveness"
            assert dir_path.is_dir()
        finally:
            shutil.rmtree(tmp_dir)

    @patch("app.services.storage_service.settings")
    def test_uses_bin_extension_as_fallback(self, mock_settings):
        tmp_dir = tempfile.mkdtemp()
        mock_settings.STORAGE_PATH = tmp_dir

        try:
            result = save_file("tx1", "other", "noext", b"data")
            assert result.endswith(".bin")
        finally:
            shutil.rmtree(tmp_dir)

    @patch("app.services.storage_service.settings")
    def test_unique_filenames(self, mock_settings):
        tmp_dir = tempfile.mkdtemp()
        mock_settings.STORAGE_PATH = tmp_dir

        try:
            r1 = save_file("tx1", "docs", "file.pdf", b"data1")
            r2 = save_file("tx1", "docs", "file.pdf", b"data2")
            assert r1 != r2  # UUID-based filenames should differ
        finally:
            shutil.rmtree(tmp_dir)
