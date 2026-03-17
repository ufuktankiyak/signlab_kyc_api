from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.kyc import (
    KycStartRequest, KycStartResponse,
    OcrResponse,
    NfcRequest, NfcResponse,
    LivenessResponse,
    KycStatusResponse,
)
from app.services import kyc_service, storage_service
from app.services.document_service import extract_document
from app.services.mrz_service import parse_mrz
from app.services.liveness_service import check_liveness

router = APIRouter()

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
ALLOWED_VIDEO_TYPES = {"video/mp4", "video/webm", "video/quicktime", "video/x-msvideo", "video/mpeg"}


# ─── 1. Start ─────────────────────────────────────────────────────────────────

@router.post("/start", response_model=KycStartResponse, summary="Start KYC session")
def start_kyc(body: KycStartRequest, db: Session = Depends(get_db)):
    """
    Starts a new KYC transaction and returns a unique **tx_id**.
    Pass this tx_id to all subsequent steps.
    """
    tx = kyc_service.create_transaction(db, body.document_type.value, body.client_reference)
    return KycStartResponse(
        tx_id=tx.id,
        status=tx.status,
        document_type=tx.document_type,
        client_reference=tx.client_reference,
        created_at=tx.created_at,
    )


# ─── 2. OCR ───────────────────────────────────────────────────────────────────

@router.post("/{tx_id}/ocr", response_model=OcrResponse, summary="Document OCR")
async def document_ocr(
    tx_id: str,
    file: UploadFile = File(...),
    side: str = Form("front"),
    db: Session = Depends(get_db),
):
    """
    Upload a document image (front or back). Runs OCR and extracts structured data.
    Supported types: new_id, passport, foreign_id, blue_card.
    """
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Allowed: {', '.join(ALLOWED_IMAGE_TYPES)}",
        )

    tx = kyc_service.get_transaction(db, tx_id)
    image_bytes = await file.read()

    # Extract data
    extracted_data, raw_ocr = extract_document(image_bytes, tx.document_type, side)

    # Save file to storage
    file_path = storage_service.save_file(
        tx_id=tx_id,
        category=f"ocr_{side}",
        original_filename=file.filename or "document.jpg",
        data=image_bytes,
    )

    # Persist to DB
    kyc_service.save_document(
        db=db,
        tx_id=tx_id,
        side=side,
        file_path=file_path,
        raw_ocr=raw_ocr,
        extracted_data=extracted_data,
    )

    return OcrResponse(
        tx_id=tx_id,
        side=side,
        document_type=tx.document_type,
        extracted_data=extracted_data,
        file_path=file_path,
    )


# ─── 3. NFC / MRZ ─────────────────────────────────────────────────────────────

@router.post("/{tx_id}/nfc", response_model=NfcResponse, summary="NFC / MRZ data")
def submit_nfc(tx_id: str, body: NfcRequest, db: Session = Depends(get_db)):
    """
    Submit MRZ lines read from NFC chip or document scan.
    Supports TD3 (passport, 2×44) and TD1 (ID card, 3×30).
    """
    kyc_service.get_transaction(db, tx_id)  # validate tx exists

    parsed = parse_mrz(body.mrz_line1, body.mrz_line2, body.mrz_line3)

    kyc_service.save_nfc(
        db=db,
        tx_id=tx_id,
        mrz_line1=body.mrz_line1,
        mrz_line2=body.mrz_line2,
        mrz_line3=body.mrz_line3,
        parsed_data=parsed,
    )

    return NfcResponse(tx_id=tx_id, parsed_data=parsed)


# ─── 4. Liveness ──────────────────────────────────────────────────────────────

@router.post("/{tx_id}/liveness", response_model=LivenessResponse, summary="Liveness check")
async def liveness_check(
    tx_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Upload a video for liveness check (mp4, webm, mov).
    Multiple frames are sampled from the video and face detection is performed on each.
    Result: passed | review | failed.
    """
    if file.content_type not in ALLOWED_VIDEO_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Allowed: {', '.join(ALLOWED_VIDEO_TYPES)}",
        )

    kyc_service.get_transaction(db, tx_id)
    video_bytes = await file.read()

    result = check_liveness(video_bytes)

    file_path = storage_service.save_file(
        tx_id=tx_id,
        category="liveness",
        original_filename=file.filename or "liveness.mp4",
        data=video_bytes,
    )

    kyc_service.save_liveness(db=db, tx_id=tx_id, file_path=file_path, result=result)

    return LivenessResponse(
        tx_id=tx_id,
        face_detected=result["face_detected"],
        liveness_score=result.get("liveness_score"),
        result=result["result"],
        file_path=file_path,
        detail=result.get("detail"),
    )


# ─── Status ───────────────────────────────────────────────────────────────────

@router.get("/{tx_id}/status", response_model=KycStatusResponse, summary="Transaction status")
def transaction_status(tx_id: str, db: Session = Depends(get_db)):
    """Returns the current status and completed steps of a KYC transaction."""
    tx = kyc_service.get_transaction(db, tx_id)
    return KycStatusResponse(
        tx_id=tx.id,
        status=tx.status,
        document_type=tx.document_type,
        client_reference=tx.client_reference,
        steps_completed=kyc_service.get_steps_completed(tx),
        created_at=tx.created_at,
        updated_at=tx.updated_at,
    )
