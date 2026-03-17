"""
KYC orchestration service.
Handles database interactions for all KYC steps.
"""

from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.models.kyc import KycTransaction, KycDocument, KycNfc, KycLiveness


def create_transaction(db: Session, document_type: str, client_reference: str | None) -> KycTransaction:
    tx = KycTransaction(
        document_type=document_type,
        client_reference=client_reference,
        status="started",
    )
    db.add(tx)
    db.commit()
    db.refresh(tx)
    return tx


def get_transaction(db: Session, tx_id: str) -> KycTransaction:
    tx = db.query(KycTransaction).filter(KycTransaction.id == tx_id).first()
    if not tx:
        raise HTTPException(status_code=404, detail=f"Transaction {tx_id} not found")
    return tx


def save_document(
    db: Session,
    tx_id: str,
    side: str,
    file_path: str | None,
    raw_ocr: list,
    extracted_data: dict,
) -> KycDocument:
    doc = KycDocument(
        tx_id=tx_id,
        side=side,
        file_path=file_path,
        raw_ocr=raw_ocr,
        extracted_data=extracted_data,
    )
    db.add(doc)

    # Update transaction status
    tx = db.query(KycTransaction).filter(KycTransaction.id == tx_id).first()
    if tx:
        tx.status = "ocr_done"

    db.commit()
    db.refresh(doc)
    return doc


def save_nfc(db: Session, tx_id: str, mrz_line1, mrz_line2, mrz_line3, parsed_data: dict) -> KycNfc:
    nfc = KycNfc(
        tx_id=tx_id,
        mrz_line1=mrz_line1,
        mrz_line2=mrz_line2,
        mrz_line3=mrz_line3,
        parsed_data=parsed_data,
    )
    db.add(nfc)

    tx = db.query(KycTransaction).filter(KycTransaction.id == tx_id).first()
    if tx:
        tx.status = "nfc_done"

    db.commit()
    db.refresh(nfc)
    return nfc


def save_liveness(db: Session, tx_id: str, file_path: str | None, result: dict) -> KycLiveness:
    liveness = KycLiveness(
        tx_id=tx_id,
        file_path=file_path,
        face_detected=result.get("face_detected", False),
        liveness_score=result.get("liveness_score"),
        result=result.get("result", "failed"),
        detail=result.get("detail"),
    )
    db.add(liveness)

    tx = db.query(KycTransaction).filter(KycTransaction.id == tx_id).first()
    if tx:
        tx.status = "liveness_done"

    db.commit()
    db.refresh(liveness)
    return liveness


def get_steps_completed(tx: KycTransaction) -> list[str]:
    steps = []
    if tx.status != "started":
        steps.append("start")
    if tx.documents:
        steps.append("ocr")
    if tx.nfc_data:
        steps.append("nfc")
    if tx.liveness:
        steps.append("liveness")
    return steps
