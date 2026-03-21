import logging

from sqlalchemy.orm import Session
from app.models.audit_log import AuditLog
from app.core.request_context import get_log_context

logger = logging.getLogger("signlab.audit")


def log_event(
    db: Session,
    event_type: str,
    actor_id: int | None = None,
    actor_email: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    detail: dict | None = None,
    request_id: str | None = None,
) -> None:
    entry = AuditLog(
        event_type=event_type,
        actor_id=actor_id,
        actor_email=actor_email,
        resource_type=resource_type,
        resource_id=resource_id,
        detail=detail,
        request_id=request_id,
    )
    db.add(entry)
    db.commit()

    logger.info(
        "audit event",
        extra={
            **get_log_context(),
            "event_type": event_type,
            "actor_id": actor_id,
            "actor_email": actor_email,
            "resource_type": resource_type,
            "resource_id": resource_id,
        },
    )
