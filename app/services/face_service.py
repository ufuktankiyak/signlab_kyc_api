"""
Face recognition using InsightFace ArcFace (buffalo_l model).
LFW benchmark accuracy: 99.77% — threshold 0.5 for ~99% precision.
"""

import logging
import numpy as np
import cv2

logger = logging.getLogger("signlab.face")

MATCH_THRESHOLD = 0.50  # cosine similarity — calibrated for ArcFace buffalo_l
_app = None


def _get_app():
    global _app
    if _app is None:
        from insightface.app import FaceAnalysis
        _app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
        _app.prepare(ctx_id=0, det_size=(640, 640))
    return _app


def get_face_embedding(image_bytes: bytes) -> np.ndarray | None:
    """Extract ArcFace embedding from image bytes. Returns None if no face found."""
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        return None

    app = _get_app()
    faces = app.get(img)
    if not faces:
        return None

    # Pick the largest face
    face = max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))
    return face.normed_embedding


def get_face_embedding_from_array(frame: np.ndarray) -> np.ndarray | None:
    """Extract ArcFace embedding from a BGR numpy array."""
    app = _get_app()
    faces = app.get(frame)
    if not faces:
        return None
    face = max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))
    return face.normed_embedding


def compare_faces(embedding1: np.ndarray, embedding2: np.ndarray) -> float:
    """Cosine similarity between two ArcFace embeddings. Range: -1 to 1."""
    return float(np.dot(embedding1, embedding2))


def match(embedding1: np.ndarray, embedding2: np.ndarray) -> dict:
    score = compare_faces(embedding1, embedding2)
    return {
        "score": round(score, 4),
        "matched": score >= MATCH_THRESHOLD,
        "threshold": MATCH_THRESHOLD,
    }
