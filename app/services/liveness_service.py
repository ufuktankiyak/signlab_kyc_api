"""
Liveness detection from video using OpenCV.

Frames are sampled from the video stream at regular intervals.
For each frame:
  1. Face detection (Haar cascade)
  2. Face-to-frame ratio (is the user close enough)
  3. Sharpness score (Laplacian variance)

Result: "passed" | "review" | "failed"
"""

import cv2
import numpy as np
import tempfile
import os

_FACE_CASCADE = None
SAMPLE_FRAMES = 10   # how many frames to analyze from the video


def _get_cascade() -> cv2.CascadeClassifier:
    global _FACE_CASCADE
    if _FACE_CASCADE is None:
        path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        _FACE_CASCADE = cv2.CascadeClassifier(path)
    return _FACE_CASCADE


def _analyze_frame(frame: np.ndarray) -> dict | None:
    """Analyze a single frame. Returns None if no face is detected."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    cascade = _get_cascade()
    faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))

    if len(faces) == 0:
        return None

    x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
    img_area = frame.shape[0] * frame.shape[1]
    face_ratio = (w * h) / img_area

    face_roi = gray[y: y + h, x: x + w]
    blur_score = cv2.Laplacian(face_roi, cv2.CV_64F).var()

    return {"face_ratio": face_ratio, "blur_score": blur_score}


def check_liveness(video_bytes: bytes) -> dict:
    # Write video to a temporary file (OpenCV requires a file path)
    suffix = ".mp4"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        tmp.write(video_bytes)
        tmp.flush()
        tmp.close()

        cap = cv2.VideoCapture(tmp.name)
        if not cap.isOpened():
            return {
                "face_detected": False,
                "liveness_score": 0.0,
                "result": "failed",
                "detail": "Could not open video",
            }

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total_frames <= 0:
            return {
                "face_detected": False,
                "liveness_score": 0.0,
                "result": "failed",
                "detail": "Video is empty or could not be read",
            }

        # Select SAMPLE_FRAMES frames at equal intervals
        sample_count = min(SAMPLE_FRAMES, total_frames)
        indices = [int(i * total_frames / sample_count) for i in range(sample_count)]

        frame_results = []
        for idx in indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ret, frame = cap.read()
            if not ret:
                continue
            analysis = _analyze_frame(frame)
            if analysis:
                frame_results.append(analysis)

        cap.release()
    finally:
        os.unlink(tmp.name)

    if not frame_results:
        return {
            "face_detected": False,
            "liveness_score": 0.0,
            "result": "failed",
            "detail": "No face detected in any frame",
        }

    # Average the results across all frames
    face_ratio_avg = sum(r["face_ratio"] for r in frame_results) / len(frame_results)
    blur_avg = sum(r["blur_score"] for r in frame_results) / len(frame_results)
    face_presence_ratio = len(frame_results) / sample_count  # ratio of frames in which a face was present

    face_ratio_score = min(1.0, face_ratio_avg / 0.10)
    blur_normalized = min(1.0, blur_avg / 150.0)

    # Consistent face presence across multiple frames is an indicator of liveness
    score = round(
        0.4 * face_ratio_score +
        0.3 * blur_normalized +
        0.3 * face_presence_ratio,
        3,
    )

    if score >= 0.55:
        result = "passed"
    elif score >= 0.30:
        result = "review"
    else:
        result = "failed"

    return {
        "face_detected": True,
        "liveness_score": score,
        "result": result,
        "detail": {
            "frames_analyzed": sample_count,
            "frames_with_face": len(frame_results),
            "face_presence_ratio": round(face_presence_ratio, 2),
            "avg_face_ratio": round(face_ratio_avg, 4),
            "avg_blur_score": round(blur_avg, 2),
        },
    }
