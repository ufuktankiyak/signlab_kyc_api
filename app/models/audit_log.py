from sqlalchemy import Column, Integer, String, DateTime, JSON
from datetime import datetime, timezone
from app.db.base import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    event_type = Column(String, nullable=False, index=True)
    actor_id = Column(Integer, nullable=True)
    actor_email = Column(String, nullable=True)
    resource_type = Column(String, nullable=True)
    resource_id = Column(String, nullable=True)
    detail = Column(JSON, nullable=True)
    request_id = Column(String, nullable=True, index=True)
