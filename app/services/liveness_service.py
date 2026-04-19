"""
Liveness detection from video using OpenCV.

Per-frame pipeline:
  1. Face detection (Haar cascade)
  2. Face-to-frame ratio and sharpness score
  3. Optical flow anti-spoofing (low variance → replay attack)
  4. FFT frequency analysis (regular peaks → screen/print display)

Result: "passed" | "review" | "failed"
Best frame bytes returned for face matching by the caller.
"""

import logging
import time
import cv2
import numpy as np
import tempfile
import os

logger = logging.getLogger("signlab.liveness")

_FACE_CASCADE = None
SAMPLE_FRAMES = 12


def _get_cascade() -> cv2.CascadeClassifier:
    global _FACE_CASCADE
    if _FACE_CASCADE is None:
        path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        _FACE_CASCADE = cv2.CascadeClassifier(path)
    return _FACE_CASCADE


def _analyze_frame(frame: np.ndarray) -> dict | None:
    """Returns face metrics for a single frame, or None if no face detected."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    cascade = _get_cascade()
    faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))

    if len(faces) == 0:
        return None

    x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
    img_area = frame.shape[0] * frame.shape[1]
    face_ratio = (w * h) / img_area
    face_roi = gray[y:y + h, x:x + w]
    blur_score = cv2.Laplacian(face_roi, cv2.CV_64F).var()

    return {"face_ratio": face_ratio, "blur_score": blur_score, "frame": frame}


def _check_optical_flow(frames: list[np.ndarray]) -> dict:
    """
    Replay attack detection via optical flow.
    Real face: varied, spatially non-uniform motion between frames.
    Photo/video replay: near-zero or perfectly uniform motion.
    """
    if len(frames) < 3:
        return {"is_real": True, "flow_variance": None}

    flow_variances = []
    prev_gray = cv2.cvtColor(frames[0], cv2.COLOR_BGR2GRAY)

    for frame in frames[1:]:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        flow = cv2.calcOpticalFlowFarneback(
            prev_gray, gray, None,
            pyr_scale=0.5, levels=3, winsize=15,
            iterations=3, poly_n=5, poly_sigma=1.2,
            flags=0,
        )
        magnitude = np.sqrt(flow[..., 0] ** 2 + flow[..., 1] ** 2)
        flow_variances.append(float(np.var(magnitude)))
        prev_gray = gray

    avg_variance = float(np.mean(flow_variances))
    # Below 0.3 = nearly no movement = likely still photo/screen
    is_real = avg_variance > 0.30
    return {"is_real": is_real, "flow_variance": round(avg_variance, 4)}


def _check_fft_pattern(frame: np.ndarray) -> dict:
    """
    Screen/print display detection via 2-D FFT.
    LCD/OLED screens and printed photos produce strong regular frequency peaks
    that real skin does not generate.
    """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).astype(np.float32)
    fshift = np.fft.fftshift(np.fft.fft2(gray))
    magnitude = np.abs(fshift)

    # Blank out DC component so it doesn't dominate
    rows, cols = gray.shape
    cr, cc = rows // 2, cols // 2
    magnitude[cr - 8:cr + 8, cc - 8:cc + 8] = 0

    threshold = np.percentile(magnitude, 99.9)
    peak_count = int(np.sum(magnitude > threshold))

    # Empirical: screens produce ≥ 30 strong symmetric peaks; real faces < 15
    has_screen_pattern = peak_count >= 30
    return {"has_screen_pattern": has_screen_pattern, "peak_count": peak_count}


def check_liveness(video_bytes: bytes) -> dict:
    """
    Returns:
        face_detected, liveness_score, result, detail, best_frame_bytes
    best_frame_bytes is the JPEG bytes of the sharpest frame with a face,
    intended for face matching by the caller.
    """
    start = time.time()
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
    try:
        tmp.write(video_bytes)
        tmp.flush()
        tmp.close()

        cap = cv2.VideoCapture(tmp.name)
        if not cap.isOpened():
            return _failed("Could not open video")

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total_frames <= 0:
            return _failed("Video is empty or could not be read")

        sample_count = min(SAMPLE_FRAMES, total_frames)
        indices = [int(i * total_frames / sample_count) for i in range(sample_count)]

        raw_frames: list[np.ndarray] = []
        frame_results: list[dict] = []

        for idx in indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ret, frame = cap.read()
            if not ret:
                continue
            raw_frames.append(frame)
            analysis = _analyze_frame(frame)
            if analysis:
                frame_results.append(analysis)

        cap.release()
    finally:
        os.unlink(tmp.name)

    if not frame_results:
        return _failed("No face detected in any frame")

    # ── Anti-spoofing ──────────────────────────────────────────────────────────
    flow_result = _check_optical_flow(raw_frames)
    fft_result = _check_fft_pattern(raw_frames[len(raw_frames) // 2])  # middle frame

    spoofing_detected = (not flow_result["is_real"]) or fft_result["has_screen_pattern"]

    # ── Liveness score ─────────────────────────────────────────────────────────
    face_ratio_avg = sum(r["face_ratio"] for r in frame_results) / len(frame_results)
    blur_avg = sum(r["blur_score"] for r in frame_results) / len(frame_results)
    face_presence_ratio = len(frame_results) / sample_count

    face_ratio_score = min(1.0, face_ratio_avg / 0.10)
    blur_normalized = min(1.0, blur_avg / 150.0)
    flow_score = min(1.0, (flow_result["flow_variance"] or 0) / 2.0) if flow_result["flow_variance"] else 0.5

    score = round(
        0.30 * face_ratio_score +
        0.20 * blur_normalized +
        0.25 * face_presence_ratio +
        0.25 * flow_score,
        3,
    )

    if spoofing_detected:
        result = "failed"
        score = min(score, 0.25)
    elif score >= 0.55:
        result = "passed"
    elif score >= 0.30:
        result = "review"
    else:
        result = "failed"

    # ── Best frame for face matching ───────────────────────────────────────────
    best = max(frame_results, key=lambda r: r["blur_score"])
    _, best_frame_jpeg = cv2.imencode(".jpg", best["frame"])
    best_frame_bytes = best_frame_jpeg.tobytes()

    duration_ms = round((time.time() - start) * 1000, 2)
    logger.info(
        "Liveness check completed",
        extra={
            "result": result,
            "liveness_score": score,
            "spoofing_detected": spoofing_detected,
            "flow_variance": flow_result["flow_variance"],
            "fft_peak_count": fft_result["peak_count"],
            "frames_analyzed": sample_count,
            "frames_with_face": len(frame_results),
            "duration_ms": duration_ms,
        },
    )

    return {
        "face_detected": True,
        "liveness_score": score,
        "result": result,
        "best_frame_bytes": best_frame_bytes,
        "detail": {
            "frames_analyzed": sample_count,
            "frames_with_face": len(frame_results),
            "face_presence_ratio": round(face_presence_ratio, 2),
            "avg_face_ratio": round(face_ratio_avg, 4),
            "avg_blur_score": round(blur_avg, 2),
            "flow_variance": flow_result["flow_variance"],
            "spoofing_detected": spoofing_detected,
            "fft_peak_count": fft_result["peak_count"],
        },
    }


def _failed(detail: str) -> dict:
    return {
        "face_detected": False,
        "liveness_score": 0.0,
        "result": "failed",
        "best_frame_bytes": None,
        "detail": detail,
    }
