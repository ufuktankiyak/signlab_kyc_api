import re

from pydantic import BaseModel, Field, field_validator
from typing import Optional, Any
from datetime import datetime
from enum import Enum


class DocumentType(str, Enum):
    new_id = "new_id"
    passport = "passport"
    foreign_id = "foreign_id"
    blue_card = "blue_card"


def _sanitize(v: str | None) -> str | None:
    """Strip whitespace and collapse internal whitespace for string inputs."""
    if v is None:
        return None
    return re.sub(r"\s+", " ", v.strip())


# ─── Start ────────────────────────────────────────────────────────────────────

class KycStartRequest(BaseModel):
    document_type: DocumentType
    client_reference: Optional[str] = Field(None, max_length=255)

    @field_validator("client_reference")
    @classmethod
    def sanitize_client_reference(cls, v: str | None) -> str | None:
        return _sanitize(v)


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
    mrz_line1: Optional[str] = Field(None, max_length=50)
    mrz_line2: Optional[str] = Field(None, max_length=50)
    mrz_line3: Optional[str] = Field(None, max_length=50)

    @field_validator("mrz_line1", "mrz_line2", "mrz_line3")
    @classmethod
    def sanitize_mrz(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return v.strip()


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
