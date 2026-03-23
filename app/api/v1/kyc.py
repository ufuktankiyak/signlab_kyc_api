from fastapi import APIRouter, Depends, Request, UploadFile, File, Form
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import ValidationException, FileTooLargeException, ProcessingException, ErrorCode
from app.core.file_validation import validate_image_bytes, validate_video_bytes
from app.core.rate_limit import limiter
from app.core.security import get_current_user
from app.core.request_context import user_id_var, tx_id_var, client_ip_var
from app.db.session import get_db
from app.models.user import User
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
_settings = get_settings()


# ─── 1. Start ─────────────────────────────────────────────────────────────────

@router.post("/start", response_model=KycStartResponse, summary="Start KYC session")
@limiter.limit(_settings.RATE_LIMIT_DEFAULT)
def start_kyc(
    request: Request,
    body: KycStartRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Starts a new KYC transaction and returns a unique **tx_id**.
    Pass this tx_id to all subsequent steps.
    """
    user_id_var.set(current_user.id)
    tx = kyc_service.create_transaction(
        db, body.document_type.value, body.client_reference,
        actor_id=current_user.id,
        client_ip=client_ip_var.get(),
    )
    tx_id_var.set(tx.id)
    return KycStartResponse(
        tx_id=tx.id,
        status=tx.status,
        document_type=tx.document_type,
        client_reference=tx.client_reference,
        created_at=tx.created_at,
    )


# ─── 2. OCR ───────────────────────────────────────────────────────────────────

@router.post("/{tx_id}/ocr", response_model=OcrResponse, summary="Document OCR")
@limiter.limit(_settings.RATE_LIMIT_OCR)
async def document_ocr(
    request: Request,
    tx_id: str,
    file: UploadFile = File(...),
    side: str = Form("front"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload a document image (front or back). Runs OCR and extracts structured data.
    Supported types: new_id, passport, foreign_id, blue_card.
    """
    # Set context vars for downstream logging
    user_id_var.set(current_user.id)
    tx_id_var.set(tx_id)

    tx = kyc_service.get_transaction(db, tx_id)
    image_bytes = await file.read()

    if len(image_bytes) > _settings.MAX_IMAGE_SIZE:
        raise FileTooLargeException(
            message=f"Image too large. Max: {_settings.MAX_IMAGE_SIZE // (1024 * 1024)} MB.",
        )

    if validate_image_bytes(image_bytes) is None:
        raise ValidationException(
            code=ErrorCode.INVALID_FILE_CONTENT,
            message="File content is not a valid image. Accepted: JPEG, PNG, WebP, GIF.",
        )

    # Extract data
    try:
        extracted_data, raw_ocr = extract_document(image_bytes, tx.document_type, side)
    except TimeoutError as exc:
        raise ProcessingException(code=ErrorCode.OCR_TIMEOUT, message=str(exc))
    except ValueError as exc:
        raise ProcessingException(code=ErrorCode.OCR_FAILED, message=str(exc))

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
        actor_id=current_user.id,
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
@limiter.limit(_settings.RATE_LIMIT_DEFAULT)
def submit_nfc(
    request: Request,
    tx_id: str,
    body: NfcRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Submit MRZ lines read from NFC chip or document scan.
    Supports TD3 (passport, 2×44) and TD1 (ID card, 3×30).
    """
    user_id_var.set(current_user.id)
    tx_id_var.set(tx_id)

    kyc_service.get_transaction(db, tx_id)  # validate tx exists

    parsed = parse_mrz(body.mrz_line1, body.mrz_line2, body.mrz_line3)

    kyc_service.save_nfc(
        db=db,
        tx_id=tx_id,
        mrz_line1=body.mrz_line1,
        mrz_line2=body.mrz_line2,
        mrz_line3=body.mrz_line3,
        parsed_data=parsed,
        actor_id=current_user.id,
    )

    return NfcResponse(tx_id=tx_id, parsed_data=parsed)


# ─── 4. Liveness ──────────────────────────────────────────────────────────────

@router.post("/{tx_id}/liveness", response_model=LivenessResponse, summary="Liveness check")
@limiter.limit(_settings.RATE_LIMIT_OCR)
async def liveness_check(
    request: Request,
    tx_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload a video for liveness check (mp4, webm, mov).
    Multiple frames are sampled from the video and face detection is performed on each.
    Result: passed | review | failed.
    """
    user_id_var.set(current_user.id)
    tx_id_var.set(tx_id)

    kyc_service.get_transaction(db, tx_id)
    video_bytes = await file.read()

    if len(video_bytes) > _settings.MAX_VIDEO_SIZE:
        raise FileTooLargeException(
            message=f"Video too large. Max: {_settings.MAX_VIDEO_SIZE // (1024 * 1024)} MB.",
        )

    if validate_video_bytes(video_bytes) is None:
        raise ValidationException(
            code=ErrorCode.INVALID_FILE_CONTENT,
            message="File content is not a valid video. Accepted: MP4, WebM, MOV.",
        )

    result = check_liveness(video_bytes)

    file_path = storage_service.save_file(
        tx_id=tx_id,
        category="liveness",
        original_filename=file.filename or "liveness.mp4",
        data=video_bytes,
    )

    kyc_service.save_liveness(db=db, tx_id=tx_id, file_path=file_path, result=result, actor_id=current_user.id)

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
@limiter.limit(_settings.RATE_LIMIT_DEFAULT)
def transaction_status(
    request: Request,
    tx_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
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
