from pydantic import BaseModel
from typing import Optional, Any
from enum import Enum


class DocumentType(str, Enum):
    turkish_id = "turkish_id"   # kept for backwards compat on /documents/extract
    new_id = "new_id"
    passport = "passport"
    foreign_id = "foreign_id"
    blue_card = "blue_card"


class TurkishIDData(BaseModel):
    identity_number: Optional[str] = None
    document_number: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    date_of_birth: Optional[str] = None
    place_of_birth: Optional[str] = None
    gender: Optional[str] = None
    expiry_date: Optional[str] = None
    serial_number: Optional[str] = None
    nationality: Optional[str] = None
    permit_type: Optional[str] = None
    mrz_lines: Optional[list[str]] = None


class DocumentExtractionResponse(BaseModel):
    document_type: DocumentType
    data: dict[str, Any]
