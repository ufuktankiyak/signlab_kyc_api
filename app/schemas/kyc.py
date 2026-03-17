from pydantic import BaseModel
from typing import Optional, Any
from datetime import datetime
from enum import Enum


class DocumentType(str, Enum):
    new_id = "new_id"
    passport = "passport"
    foreign_id = "foreign_id"
    blue_card = "blue_card"


# ─── Start ────────────────────────────────────────────────────────────────────

class KycStartRequest(BaseModel):
    document_type: DocumentType
    client_reference: Optional[str] = None


class KycStartResponse(BaseModel):
    tx_id: str
    status: str
    document_type: str
    client_reference: Optional[str] = None
    created_at: datetime


# ─── OCR ──────────────────────────────────────────────────────────────────────

class OcrResponse(BaseModel):
    tx_id: str
    side: str
    document_type: str
    extracted_data: dict[str, Any]
    file_path: Optional[str] = None


# ─── NFC / MRZ ────────────────────────────────────────────────────────────────

class NfcRequest(BaseModel):
    mrz_line1: Optional[str] = None
    mrz_line2: Optional[str] = None
    mrz_line3: Optional[str] = None


class NfcResponse(BaseModel):
    tx_id: str
    parsed_data: dict[str, Any]


# ─── Liveness ─────────────────────────────────────────────────────────────────

class LivenessResponse(BaseModel):
    tx_id: str
    face_detected: bool
    liveness_score: Optional[float] = None
    result: str  # passed, review, failed
    file_path: Optional[str] = None
    detail: Optional[Any] = None


# ─── Status ───────────────────────────────────────────────────────────────────

class KycStatusResponse(BaseModel):
    tx_id: str
    status: str
    document_type: str
    client_reference: Optional[str] = None
    steps_completed: list[str]
    created_at: datetime
    updated_at: datetime
