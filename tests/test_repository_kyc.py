"""Repository-level tests for KYC service — real in-memory SQLite DB."""

import pytest

from app.core.exceptions import NotFoundException
from app.models.kyc import KycTransaction, KycDocument, KycNfc, KycLiveness
from app.services import kyc_service


# ─── create_transaction ──────────────────────────────────────────────────────

class TestCreateTransactionRepo:
    def test_persists_to_database(self, db_session):
        tx = kyc_service.create_transaction(db_session, "new_id", "REF-001")

        fetched = db_session.query(KycTransaction).filter_by(id=tx.id).first()
        assert fetched is not None
        assert fetched.document_type == "new_id"
        assert fetched.client_reference == "REF-001"
        assert fetched.status == "started"

    def test_generates_unique_ids(self, db_session):
        tx1 = kyc_service.create_transaction(db_session, "new_id", None)
        tx2 = kyc_service.create_transaction(db_session, "passport", None)
        assert tx1.id != tx2.id

    def test_sets_created_at(self, db_session):
        tx = kyc_service.create_transaction(db_session, "new_id", None)
        assert tx.created_at is not None

    def test_null_client_reference(self, db_session):
        tx = kyc_service.create_transaction(db_session, "passport", None)
        assert tx.client_reference is None


# ─── get_transaction ─────────────────────────────────────────────────────────

class TestGetTransactionRepo:
    def test_returns_existing(self, db_session):
        tx = kyc_service.create_transaction(db_session, "new_id", "REF-X")
        result = kyc_service.get_transaction(db_session, tx.id)
        assert result.id == tx.id
        assert result.document_type == "new_id"

    def test_raises_404_for_missing(self, db_session):
        with pytest.raises(NotFoundException) as exc_info:
            kyc_service.get_transaction(db_session, "nonexistent-id")
        assert exc_info.value.status_code == 404

    def test_404_message_includes_tx_id(self, db_session):
        with pytest.raises(NotFoundException) as exc_info:
            kyc_service.get_transaction(db_session, "abc123")
        assert "abc123" in exc_info.value.message


# ─── save_document ───────────────────────────────────────────────────────────

class TestSaveDocumentRepo:
    def test_persists_document(self, db_session):
        tx = kyc_service.create_transaction(db_session, "new_id", None)
        doc = kyc_service.save_document(
            db_session,
            tx_id=tx.id,
            side="front",
            file_path="/storage/tx/doc.jpg",
            raw_ocr=["line1", "line2"],
            extracted_data={"name": "John"},
        )

        fetched = db_session.query(KycDocument).filter_by(id=doc.id).first()
        assert fetched is not None
        assert fetched.tx_id == tx.id
        assert fetched.side == "front"
        assert fetched.file_path == "/storage/tx/doc.jpg"

    def test_updates_transaction_status_to_ocr_done(self, db_session):
        tx = kyc_service.create_transaction(db_session, "new_id", None)
        assert tx.status == "started"

        kyc_service.save_document(
            db_session, tx.id, "front", None, [], {},
        )

        db_session.refresh(tx)
        assert tx.status == "ocr_done"

    def test_saves_multiple_sides(self, db_session):
        tx = kyc_service.create_transaction(db_session, "new_id", None)

        kyc_service.save_document(db_session, tx.id, "front", None, ["f1"], {"f": 1})
        kyc_service.save_document(db_session, tx.id, "back", None, ["b1"], {"b": 1})

        docs = db_session.query(KycDocument).filter_by(tx_id=tx.id).all()
        assert len(docs) == 2
        sides = {d.side for d in docs}
        assert sides == {"front", "back"}

    def test_document_linked_via_relationship(self, db_session):
        tx = kyc_service.create_transaction(db_session, "new_id", None)
        kyc_service.save_document(db_session, tx.id, "front", None, [], {})

        db_session.refresh(tx)
        assert len(tx.documents) == 1
        assert tx.documents[0].side == "front"


# ─── save_nfc ────────────────────────────────────────────────────────────────

class TestSaveNfcRepo:
    def test_persists_nfc_data(self, db_session):
        tx = kyc_service.create_transaction(db_session, "new_id", None)
        nfc = kyc_service.save_nfc(
            db_session,
            tx_id=tx.id,
            mrz_line1="P<TURDOE<<JOHN<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<",
            mrz_line2="U123456784TUR8507200M2512315<<<<<<<<<<<<<<06",
            mrz_line3=None,
            parsed_data={"last_name": "DOE", "first_name": "JOHN"},
        )

        fetched = db_session.query(KycNfc).filter_by(id=nfc.id).first()
        assert fetched is not None
        assert fetched.tx_id == tx.id
        assert fetched.mrz_line1.startswith("P<TUR")
        assert fetched.mrz_line3 is None

    def test_updates_transaction_status_to_nfc_done(self, db_session):
        tx = kyc_service.create_transaction(db_session, "new_id", None)
        kyc_service.save_nfc(
            db_session, tx.id, "L1", "L2", None, {},
        )

        db_session.refresh(tx)
        assert tx.status == "nfc_done"

    def test_nfc_linked_via_relationship(self, db_session):
        tx = kyc_service.create_transaction(db_session, "new_id", None)
        kyc_service.save_nfc(db_session, tx.id, "L1", "L2", "L3", {"key": "val"})

        db_session.refresh(tx)
        assert tx.nfc_data is not None
        assert tx.nfc_data.mrz_line1 == "L1"


# ─── save_liveness ───────────────────────────────────────────────────────────

class TestSaveLivenessRepo:
    def test_persists_liveness_result(self, db_session):
        tx = kyc_service.create_transaction(db_session, "new_id", None)
        result = {
            "face_detected": True,
            "liveness_score": 0.82,
            "result": "passed",
            "detail": {"frames_analyzed": 10, "frames_with_face": 9},
        }
        liveness = kyc_service.save_liveness(
            db_session, tx.id, "/storage/tx/video.mp4", result,
        )

        fetched = db_session.query(KycLiveness).filter_by(id=liveness.id).first()
        assert fetched is not None
        assert fetched.face_detected is True
        assert fetched.liveness_score == 0.82
        assert fetched.result == "passed"
        assert fetched.file_path == "/storage/tx/video.mp4"

    def test_updates_transaction_status_to_liveness_done(self, db_session):
        tx = kyc_service.create_transaction(db_session, "new_id", None)
        kyc_service.save_liveness(
            db_session, tx.id, None,
            {"face_detected": False, "liveness_score": 0.0, "result": "failed", "detail": "no face"},
        )

        db_session.refresh(tx)
        assert tx.status == "liveness_done"

    def test_failed_liveness_persists(self, db_session):
        tx = kyc_service.create_transaction(db_session, "new_id", None)
        kyc_service.save_liveness(
            db_session, tx.id, None,
            {"face_detected": False, "liveness_score": 0.1, "result": "failed"},
        )

        fetched = db_session.query(KycLiveness).filter_by(tx_id=tx.id).first()
        assert fetched.face_detected is False
        assert fetched.result == "failed"

    def test_liveness_linked_via_relationship(self, db_session):
        tx = kyc_service.create_transaction(db_session, "new_id", None)
        kyc_service.save_liveness(
            db_session, tx.id, None,
            {"face_detected": True, "liveness_score": 0.7, "result": "passed", "detail": {}},
        )

        db_session.refresh(tx)
        assert tx.liveness is not None
        assert tx.liveness.result == "passed"


# ─── get_steps_completed ─────────────────────────────────────────────────────

class TestGetStepsCompletedRepo:
    def test_no_steps_at_start(self, db_session):
        tx = kyc_service.create_transaction(db_session, "new_id", None)
        steps = kyc_service.get_steps_completed(tx)
        assert steps == []

    def test_after_ocr(self, db_session):
        tx = kyc_service.create_transaction(db_session, "new_id", None)
        kyc_service.save_document(db_session, tx.id, "front", None, [], {})

        db_session.refresh(tx)
        steps = kyc_service.get_steps_completed(tx)
        assert "start" in steps
        assert "ocr" in steps
        assert "nfc" not in steps

    def test_after_nfc(self, db_session):
        tx = kyc_service.create_transaction(db_session, "new_id", None)
        kyc_service.save_document(db_session, tx.id, "front", None, [], {})
        kyc_service.save_nfc(db_session, tx.id, "L1", "L2", None, {})

        db_session.refresh(tx)
        steps = kyc_service.get_steps_completed(tx)
        assert "start" in steps
        assert "ocr" in steps
        assert "nfc" in steps
        assert "liveness" not in steps

    def test_full_flow(self, db_session):
        tx = kyc_service.create_transaction(db_session, "new_id", "REF-FULL")
        kyc_service.save_document(db_session, tx.id, "front", None, [], {})
        kyc_service.save_nfc(db_session, tx.id, "L1", "L2", None, {})
        kyc_service.save_liveness(
            db_session, tx.id, None,
            {"face_detected": True, "liveness_score": 0.9, "result": "passed", "detail": {}},
        )

        db_session.refresh(tx)
        steps = kyc_service.get_steps_completed(tx)
        assert steps == ["start", "ocr", "nfc", "liveness"]


# ─── Status flow ─────────────────────────────────────────────────────────────

class TestStatusFlowRepo:
    def test_full_status_progression(self, db_session):
        tx = kyc_service.create_transaction(db_session, "passport", None)
        assert tx.status == "started"

        kyc_service.save_document(db_session, tx.id, "front", None, [], {})
        db_session.refresh(tx)
        assert tx.status == "ocr_done"

        kyc_service.save_nfc(db_session, tx.id, "L1", "L2", None, {})
        db_session.refresh(tx)
        assert tx.status == "nfc_done"

        kyc_service.save_liveness(
            db_session, tx.id, None,
            {"face_detected": True, "liveness_score": 0.8, "result": "passed", "detail": {}},
        )
        db_session.refresh(tx)
        assert tx.status == "liveness_done"
