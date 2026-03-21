from fastapi import APIRouter, Depends, Request, UploadFile, File, Form, HTTPException
from app.core.config import get_settings
from app.core.rate_limit import limiter
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.document import DocumentType, DocumentExtractionResponse
from app.services.document_service import extract_document, preprocess_image, run_ocr

router = APIRouter()
_settings = get_settings()

ALLOWED_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
}


@router.post("/extract", response_model=DocumentExtractionResponse)
@limiter.limit(_settings.RATE_LIMIT_OCR)
async def extract_document_info(
    request: Request,
    file: UploadFile = File(...),
    document_type: DocumentType = Form(DocumentType.turkish_id),
    current_user: User = Depends(get_current_user),
):
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format. Accepted formats: {', '.join(ALLOWED_CONTENT_TYPES)}",
        )

    image_bytes = await file.read()

    if len(image_bytes) > _settings.MAX_IMAGE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"Image too large. Max: {_settings.MAX_IMAGE_SIZE // (1024 * 1024)} MB.",
        )

    # turkish_id is the legacy alias for new_id
    doc_type_key = "new_id" if document_type.value == "turkish_id" else document_type.value
    try:
        extracted, _ = extract_document(image_bytes, doc_type_key)
    except (ValueError, TimeoutError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))

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
        raise HTTPException(
            status_code=413,
            detail=f"Image too large. Max: {_settings.MAX_IMAGE_SIZE // (1024 * 1024)} MB.",
        )

    try:
        img = preprocess_image(image_bytes)
        texts = run_ocr(img)
    except (ValueError, TimeoutError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"texts": texts}
