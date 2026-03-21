from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, JSON, ForeignKey, Text  # noqa: F401
from sqlalchemy.orm import relationship
from datetime import datetime
from uuid import uuid4
from app.db.base import Base


class KycTransaction(Base):
    __tablename__ = "kyc_transactions"

    id = Column(String, primary_key=True, default=lambda: uuid4().hex)
    user_id = Column(Integer, nullable=True, index=True)
    status = Column(String, default="started")  # started, ocr_done, nfc_done, liveness_done, completed, failed
    document_type = Column(String, nullable=False)  # new_id, passport, foreign_id, blue_card
    client_reference = Column(String, nullable=True)
    client_ip = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    documents = relationship("KycDocument", back_populates="transaction")
    nfc_data = relationship("KycNfc", back_populates="transaction", uselist=False)
    liveness = relationship("KycLiveness", back_populates="transaction", uselist=False)


class KycDocument(Base):
    __tablename__ = "kyc_documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tx_id = Column(String, ForeignKey("kyc_transactions.id"), nullable=False)
    side = Column(String, default="front")  # front, back
    file_path = Column(String, nullable=True)
    raw_ocr = Column(JSON, nullable=True)
    extracted_data = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    transaction = relationship("KycTransaction", back_populates="documents")


class KycNfc(Base):
    __tablename__ = "kyc_nfc"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tx_id = Column(String, ForeignKey("kyc_transactions.id"), nullable=False)
    mrz_line1 = Column(Text, nullable=True)
    mrz_line2 = Column(Text, nullable=True)
    mrz_line3 = Column(Text, nullable=True)
    parsed_data = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    transaction = relationship("KycTransaction", back_populates="nfc_data")


class KycLiveness(Base):
    __tablename__ = "kyc_liveness"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tx_id = Column(String, ForeignKey("kyc_transactions.id"), nullable=False)
    file_path = Column(String, nullable=True)
    face_detected = Column(Boolean, default=False)
    liveness_score = Column(Float, nullable=True)
    result = Column(String, nullable=True)  # passed, review, failed
    detail = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    transaction = relationship("KycTransaction", back_populates="liveness")


