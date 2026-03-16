from fastapi import APIRouter, UploadFile, File, Form, HTTPException
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
):
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format. Accepted formats: {', '.join(ALLOWED_CONTENT_TYPES)}",
        )

    image_bytes = await file.read()

    data = extract_document(image_bytes, file.content_type, document_type)

    return DocumentExtractionResponse(document_type=document_type, data=data)


@router.post("/debug-ocr")
async def debug_ocr(file: UploadFile = File(...)):
    """Returns the raw OCR output — used for tuning regex patterns."""
    image_bytes = await file.read()
    img = preprocess_image(image_bytes)
    texts = run_ocr(img)
    return {"texts": texts}
