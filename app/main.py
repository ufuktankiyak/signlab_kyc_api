"""
Signlab OCR & Liveness — Internal Microservice

Endpoints:
  POST /ocr          — document OCR extraction
  POST /liveness     — video liveness + optional face matching
  GET  /health       — health check

No auth, no DB. Called only by the .NET API over internal network.
"""

import logging

from fastapi import FastAPI, UploadFile, File, Form, HTTPException

from app.services.document_service import extract_document
from app.services.liveness_service import check_liveness
from app.services.face_service import get_face_embedding, get_face_embedding_from_array, match

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("signlab.ocr-service")

app = FastAPI(title="Signlab OCR Service", version="2.0.0", docs_url=None, redoc_url=None)


@app.get("/health")
def health():
    return {"status": "ok", "service": "ocr"}


@app.post("/ocr")
async def ocr(
    file: UploadFile = File(...),
    document_type: str = Form(...),
    side: str = Form("front"),
):
    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=422, detail={"error": "Empty file", "code": "OCR_FAILED"})

    try:
        extracted_data, raw_ocr = extract_document(image_bytes, document_type, side)
    except ValueError as e:
        raise HTTPException(status_code=422, detail={"error": str(e), "code": "OCR_FAILED"})
    except TimeoutError as e:
        raise HTTPException(status_code=422, detail={"error": str(e), "code": "OCR_TIMEOUT"})
    except Exception:
        logger.exception("OCR extraction failed")
        raise HTTPException(status_code=500, detail={"error": "Internal OCR error", "code": "OCR_FAILED"})

    return {"extracted_data": extracted_data, "raw_ocr": raw_ocr}


@app.post("/liveness")
async def liveness(
    file: UploadFile = File(...),
    reference_photo: UploadFile | None = File(default=None),
):
    """
    Liveness check with optional face matching.
    - file: video (mp4, webm, mov)
    - reference_photo (optional): reference face image (e.g. document front photo)
      If provided, the best liveness frame is compared against this photo.
    """
    video_bytes = await file.read()
    if not video_bytes:
        raise HTTPException(status_code=422, detail={"error": "Empty file", "code": "LIVENESS_FAILED"})

    try:
        result = check_liveness(video_bytes)
    except Exception:
        logger.exception("Liveness check failed")
        raise HTTPException(status_code=500, detail={"error": "Internal liveness error", "code": "LIVENESS_FAILED"})

    best_frame_bytes: bytes | None = result.pop("best_frame_bytes", None)
    face_match: dict | None = None

    if reference_photo and best_frame_bytes and result.get("face_detected"):
        try:
            ref_bytes = await reference_photo.read()
            ref_embedding = get_face_embedding(ref_bytes)

            import cv2, numpy as np
            nparr = np.frombuffer(best_frame_bytes, np.uint8)
            best_frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            live_embedding = get_face_embedding_from_array(best_frame) if best_frame is not None else None

            if ref_embedding is not None and live_embedding is not None:
                face_match = match(ref_embedding, live_embedding)
            else:
                face_match = {"score": None, "matched": False, "threshold": 0.50, "error": "face_not_detected"}
        except Exception:
            logger.exception("Face matching failed")
            face_match = {"score": None, "matched": False, "threshold": 0.50, "error": "face_match_error"}

    result["face_match"] = face_match
    return result
