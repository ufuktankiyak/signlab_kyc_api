from fastapi import APIRouter, Depends, Request, UploadFile, File, Form
from app.core.config import get_settings
from app.core.exceptions import ValidationException, FileTooLargeException, ProcessingException, ErrorCode
from app.core.file_validation import validate_image_bytes
from app.core.rate_limit import limiter
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.document import DocumentType, DocumentExtractionResponse
from app.services.document_service import extract_document, preprocess_image, run_ocr

router = APIRouter()
_settings = get_settings()


@router.post("/extract", response_model=DocumentExtractionResponse)
@limiter.limit(_settings.RATE_LIMIT_OCR)
async def extract_document_info(
    request: Request,
    file: UploadFile = File(...),
    document_type: DocumentType = Form(DocumentType.turkish_id),
    current_user: User = Depends(get_current_user),
):
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

    # turkish_id is the legacy alias for new_id
    doc_type_key = "new_id" if document_type.value == "turkish_id" else document_type.value
    try:
        extracted, _ = extract_document(image_bytes, doc_type_key)
    except TimeoutError as exc:
        raise ProcessingException(code=ErrorCode.OCR_TIMEOUT, message=str(exc))
    except ValueError as exc:
        raise ProcessingException(code=ErrorCode.OCR_FAILED, message=str(exc))

    return DocumentExtractionResponse(document_type=document_type, data=extracted)


@router.post("/debug-ocr")
@limiter.limit(_settings.RATE_LIMIT_OCR)
async def debug_ocr(
    request: Request,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """Returns the raw OCR output — used for tuning regex patterns."""
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

    try:
        img = preprocess_image(image_bytes)
        texts = run_ocr(img)
    except TimeoutError as exc:
        raise ProcessingException(code=ErrorCode.OCR_TIMEOUT, message=str(exc))
    except ValueError as exc:
        raise ProcessingException(code=ErrorCode.OCR_FAILED, message=str(exc))
    return {"texts": texts}
