"""
KYC orchestration service.
Handles database interactions for all KYC steps.
"""

from sqlalchemy.orm import Session
from app.core.exceptions import NotFoundException, ErrorCode
from app.models.kyc import KycTransaction, KycDocument, KycNfc, KycLiveness
from app.services import audit_service


def create_transaction(
    db: Session, document_type: str, client_reference: str | None,
    actor_id: int | None = None, client_ip: str | None = None,
) -> KycTransaction:
    tx = KycTransaction(
        document_type=document_type,
        client_reference=client_reference,
        user_id=actor_id,
        client_ip=client_ip,
        status="started",
    )
    db.add(tx)
    db.commit()
    db.refresh(tx)

    audit_service.log_event(
        db, "kyc.started",
        actor_id=actor_id,
        resource_type="kyc_transaction",
        resource_id=tx.id,
        detail={"document_type": document_type},
    )
    return tx


def get_transaction(db: Session, tx_id: str) -> KycTransaction:
    tx = db.query(KycTransaction).filter(KycTransaction.id == tx_id).first()
    if not tx:
        raise NotFoundException(
            code=ErrorCode.TRANSACTION_NOT_FOUND,
            message=f"Transaction {tx_id} not found",
            details={"tx_id": tx_id},
        )
    return tx


def save_document(
    db: Session,
    tx_id: str,
    side: str,
    file_path: str | None,
    raw_ocr: list,
    extracted_data: dict,
    actor_id: int | None = None,
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

    audit_service.log_event(
        db, "kyc.ocr_done",
        actor_id=actor_id,
        resource_type="kyc_transaction",
        resource_id=tx_id,
        detail={"side": side},
    )
    return doc


def save_nfc(
    db: Session, tx_id: str, mrz_line1, mrz_line2, mrz_line3, parsed_data: dict,
    actor_id: int | None = None,
) -> KycNfc:
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

    audit_service.log_event(
        db, "kyc.nfc_done",
        actor_id=actor_id,
        resource_type="kyc_transaction",
        resource_id=tx_id,
    )
    return nfc


def save_liveness(
    db: Session, tx_id: str, file_path: str | None, result: dict,
    actor_id: int | None = None,
) -> KycLiveness:
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

    audit_service.log_event(
        db, "kyc.liveness_done",
        actor_id=actor_id,
        resource_type="kyc_transaction",
        resource_id=tx_id,
        detail={"result": result.get("result")},
    )
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
