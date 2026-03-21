"""Tests for audit service."""

import pytest
from app.models.audit_log import AuditLog
from app.services.audit_service import log_event


class TestLogEvent:
    def test_persists_audit_log(self, db_session):
        log_event(
            db_session,
            event_type="auth.login",
            actor_id=1,
            actor_email="admin@signlab.com",
            resource_type="user",
            resource_id="1",
        )

        entry = db_session.query(AuditLog).first()
        assert entry is not None
        assert entry.event_type == "auth.login"
        assert entry.actor_id == 1
        assert entry.actor_email == "admin@signlab.com"
        assert entry.resource_type == "user"
        assert entry.resource_id == "1"
        assert entry.timestamp is not None

    def test_persists_with_detail(self, db_session):
        log_event(
            db_session,
            event_type="auth.login_failed",
            actor_email="attacker@test.com",
            detail={"reason": "invalid_credentials"},
        )

        entry = db_session.query(AuditLog).first()
        assert entry.detail == {"reason": "invalid_credentials"}
        assert entry.actor_id is None

    def test_persists_with_request_id(self, db_session):
        log_event(
            db_session,
            event_type="kyc.started",
            request_id="abc123def456",
            resource_type="kyc_transaction",
            resource_id="tx-001",
        )

        entry = db_session.query(AuditLog).first()
        assert entry.request_id == "abc123def456"

    def test_multiple_events_append(self, db_session):
        log_event(db_session, "auth.login", actor_id=1)
        log_event(db_session, "auth.login", actor_id=2)
        log_event(db_session, "kyc.started", actor_id=1)

        count = db_session.query(AuditLog).count()
        assert count == 3

    def test_kyc_state_change_events(self, db_session):
        events = ["kyc.started", "kyc.ocr_done", "kyc.nfc_done", "kyc.liveness_done"]
        for event in events:
            log_event(
                db_session, event,
                actor_id=1,
                resource_type="kyc_transaction",
                resource_id="tx-abc",
            )

        entries = db_session.query(AuditLog).filter_by(resource_id="tx-abc").all()
        assert len(entries) == 4
        assert [e.event_type for e in entries] == events
