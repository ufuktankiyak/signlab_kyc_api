from pydantic import BaseModel
from enum import Enum
from typing import Optional


class DocumentType(str, Enum):
    turkish_id = "turkish_id"
    passport = "passport"
    blue_card = "blue_card"


class TurkishIDData(BaseModel):
    identity_number: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    date_of_birth: Optional[str] = None
    place_of_birth: Optional[str] = None
    gender: Optional[str] = None
    expiry_date: Optional[str] = None
    serial_number: Optional[str] = None


class DocumentExtractionResponse(BaseModel):
    document_type: DocumentType
    data: TurkishIDData
