"""Tests for liveness detection service."""

import pytest
import numpy as np
from unittest.mock import patch, MagicMock

from app.services.liveness_service import _analyze_frame, check_liveness


class TestAnalyzeFrame:
    def test_no_face_returns_none(self):
        # Plain black image — no face
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        result = _analyze_frame(frame)
        assert result is None

    def test_returns_dict_when_face_found(self):
        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        with patch("app.services.liveness_service._get_cascade") as mock_cascade:
            mock_classifier = MagicMock()
            mock_classifier.detectMultiScale.return_value = np.array([[100, 100, 150, 150]])
            mock_cascade.return_value = mock_classifier

            result = _analyze_frame(frame)
            assert result is not None
            assert "face_ratio" in result
            assert "blur_score" in result
            assert 0 < result["face_ratio"] < 1


class TestCheckLiveness:
    def test_invalid_video_returns_failed(self):
        result = check_liveness(b"not a real video")
        assert result["face_detected"] is False
        assert result["result"] == "failed"

    def test_empty_bytes_returns_failed(self):
        result = check_liveness(b"")
        assert result["face_detected"] is False
        assert result["result"] == "failed"

    @patch("app.services.liveness_service._analyze_frame")
    @patch("app.services.liveness_service.cv2")
    def test_no_faces_in_any_frame(self, mock_cv2, mock_analyze):
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.get.return_value = 10
        mock_cap.read.return_value = (True, np.zeros((480, 640, 3), dtype=np.uint8))
        mock_cv2.VideoCapture.return_value = mock_cap
        mock_cv2.CAP_PROP_FRAME_COUNT = 7
        mock_cv2.CAP_PROP_POS_FRAMES = 1

        mock_analyze.return_value = None  # No face detected

        result = check_liveness(b"fake_video_data")
        assert result["face_detected"] is False
        assert result["result"] == "failed"

    @patch("app.services.liveness_service._analyze_frame")
    @patch("app.services.liveness_service.cv2")
    def test_high_score_returns_passed(self, mock_cv2, mock_analyze):
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.get.return_value = 10
        mock_cap.read.return_value = (True, np.zeros((480, 640, 3), dtype=np.uint8))
        mock_cv2.VideoCapture.return_value = mock_cap
        mock_cv2.CAP_PROP_FRAME_COUNT = 7
        mock_cv2.CAP_PROP_POS_FRAMES = 1

        mock_analyze.return_value = {"face_ratio": 0.15, "blur_score": 200.0}

        result = check_liveness(b"fake_video_data")
        assert result["face_detected"] is True
        assert result["result"] == "passed"
        assert result["liveness_score"] >= 0.55

    @patch("app.services.liveness_service._analyze_frame")
    @patch("app.services.liveness_service.cv2")
    def test_low_score_returns_failed(self, mock_cv2, mock_analyze):
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.get.return_value = 10
        mock_cap.read.return_value = (True, np.zeros((480, 640, 3), dtype=np.uint8))
        mock_cv2.VideoCapture.return_value = mock_cap
        mock_cv2.CAP_PROP_FRAME_COUNT = 7
        mock_cv2.CAP_PROP_POS_FRAMES = 1

        # Only 1 frame has face, rest return None
        mock_analyze.side_effect = [{"face_ratio": 0.01, "blur_score": 5.0}] + [None] * 9

        result = check_liveness(b"fake_video_data")
        assert result["liveness_score"] < 0.30
        assert result["result"] == "failed"
