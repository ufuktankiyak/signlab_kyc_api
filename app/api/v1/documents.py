from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.document import DocumentType, DocumentExtractionResponse
from app.services.document_service import extract_document, preprocess_image, run_ocr

router = APIRouter()

ALLOWED_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
}


@router.post("/extract", response_model=DocumentExtractionResponse)
async def extract_document_info(
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

    # turkish_id is the legacy alias for new_id
    doc_type_key = "new_id" if document_type.value == "turkish_id" else document_type.value
    extracted, _ = extract_document(image_bytes, doc_type_key)

    return DocumentExtractionResponse(document_type=document_type, data=extracted)


@router.post("/debug-ocr")
async def debug_ocr(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """Returns the raw OCR output — used for tuning regex patterns."""
    image_bytes = await file.read()
    img = preprocess_image(image_bytes)
    texts = run_ocr(img)
    return {"texts": texts}
