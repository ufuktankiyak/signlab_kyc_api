"""Tests for KYC orchestration service."""

import pytest
from unittest.mock import MagicMock, patch

from app.core.exceptions import NotFoundException
from app.models.kyc import KycTransaction, KycDocument, KycNfc, KycLiveness
from app.services import kyc_service


class TestCreateTransaction:
    def test_creates_and_commits(self, mock_db):
        mock_db.refresh = MagicMock()
        tx = kyc_service.create_transaction(mock_db, "new_id", "REF-001")

        # First add is the transaction, second is the audit log
        assert mock_db.add.call_count == 2
        added_tx = mock_db.add.call_args_list[0][0][0]
        assert added_tx.document_type == "new_id"
        assert added_tx.client_reference == "REF-001"
        assert added_tx.status == "started"

    def test_creates_without_reference(self, mock_db):
        mock_db.refresh = MagicMock()
        kyc_service.create_transaction(mock_db, "passport", None)

        added_tx = mock_db.add.call_args_list[0][0][0]
        assert added_tx.client_reference is None


class TestGetTransaction:
    def test_returns_existing_transaction(self, mock_db):
        mock_tx = MagicMock(spec=KycTransaction)
        mock_db.query.return_value.filter.return_value.first.return_value = mock_tx

        result = kyc_service.get_transaction(mock_db, "abc123")
        assert result == mock_tx

    def test_raises_404_when_not_found(self, mock_db):
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(NotFoundException) as exc_info:
            kyc_service.get_transaction(mock_db, "nonexistent")
        assert exc_info.value.status_code == 404


class TestSaveDocument:
    def test_saves_document_and_updates_status(self, mock_db):
        mock_tx = MagicMock(spec=KycTransaction)
        mock_db.query.return_value.filter.return_value.first.return_value = mock_tx
        mock_db.refresh = MagicMock()

        kyc_service.save_document(
            mock_db,
            tx_id="tx1",
            side="front",
            file_path="/path/to/file.jpg",
            raw_ocr=["text1", "text2"],
            extracted_data={"name": "John"},
        )

        assert mock_db.add.call_count == 2  # document + audit
        assert mock_tx.status == "ocr_done"

        doc = mock_db.add.call_args_list[0][0][0]
        assert doc.tx_id == "tx1"
        assert doc.side == "front"


class TestSaveNfc:
    def test_saves_nfc_and_updates_status(self, mock_db):
        mock_tx = MagicMock(spec=KycTransaction)
        mock_db.query.return_value.filter.return_value.first.return_value = mock_tx
        mock_db.refresh = MagicMock()

        kyc_service.save_nfc(
            mock_db,
            tx_id="tx1",
            mrz_line1="LINE1",
            mrz_line2="LINE2",
            mrz_line3="LINE3",
            parsed_data={"name": "John"},
        )

        assert mock_db.add.call_count == 2  # nfc + audit
        assert mock_tx.status == "nfc_done"


class TestSaveLiveness:
    def test_saves_liveness_and_updates_status(self, mock_db):
        mock_tx = MagicMock(spec=KycTransaction)
        mock_db.query.return_value.filter.return_value.first.return_value = mock_tx
        mock_db.refresh = MagicMock()

        result = {
            "face_detected": True,
            "liveness_score": 0.85,
            "result": "passed",
            "detail": {"frames_analyzed": 10},
        }
        kyc_service.save_liveness(mock_db, "tx1", "/path/video.mp4", result)

        assert mock_db.add.call_count == 2  # liveness + audit
        assert mock_tx.status == "liveness_done"

        liveness = mock_db.add.call_args_list[0][0][0]
        assert liveness.face_detected is True
        assert liveness.liveness_score == 0.85
        assert liveness.result == "passed"


class TestGetStepsCompleted:
    def test_started_only(self):
        tx = MagicMock()
        tx.status = "started"
        tx.documents = []
        tx.nfc_data = None
        tx.liveness = None

        steps = kyc_service.get_steps_completed(tx)
        assert steps == []

    def test_all_steps_completed(self):
        tx = MagicMock()
        tx.status = "liveness_done"
        tx.documents = [MagicMock()]
        tx.nfc_data = MagicMock()
        tx.liveness = MagicMock()

        steps = kyc_service.get_steps_completed(tx)
        assert "start" in steps
        assert "ocr" in steps
        assert "nfc" in steps
        assert "liveness" in steps

    def test_partial_steps(self):
        tx = MagicMock()
        tx.status = "ocr_done"
        tx.documents = [MagicMock()]
        tx.nfc_data = None
        tx.liveness = None

        steps = kyc_service.get_steps_completed(tx)
        assert "start" in steps
        assert "ocr" in steps
        assert "nfc" not in steps
        assert "liveness" not in steps
