"""
Signlab OCR & Liveness — Internal Microservice

Minimal FastAPI service exposing only two endpoints:
  POST /ocr       — document OCR extraction
  POST /liveness  — video liveness detection
  GET  /health    — health check

No auth, no DB, no rate limiting. Called only by the .NET API over internal network.
"""

import logging

from fastapi import FastAPI, UploadFile, File, Form, HTTPException

from app.services.document_service import extract_document
from app.services.liveness_service import check_liveness

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("signlab.ocr-service")

app = FastAPI(title="Signlab OCR Service", version="1.0.0", docs_url=None, redoc_url=None)


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
        raise HTTPException(status_code=422, detail={"error": str(e), "code": "OCR_FAILED"})
    except Exception:
        logger.exception("OCR extraction failed")
        raise HTTPException(status_code=500, detail={"error": "Internal OCR error", "code": "OCR_FAILED"})

    return {
        "extracted_data": extracted_data,
        "raw_ocr": raw_ocr,
    }


@app.post("/liveness")
async def liveness(file: UploadFile = File(...)):
    video_bytes = await file.read()
    if not video_bytes:
        raise HTTPException(status_code=422, detail={"error": "Empty file", "code": "LIVENESS_FAILED"})

    try:
        result = check_liveness(video_bytes)
    except Exception:
        logger.exception("Liveness check failed")
        raise HTTPException(status_code=500, detail={"error": "Internal liveness error", "code": "LIVENESS_FAILED"})

    return result
