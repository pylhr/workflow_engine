"""Audit log model: records significant actions for compliance/traceability."""

from datetime import datetime

from sqlalchemy import String, Integer, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=True)

    # e.g. "workflow_created", "workflow_published", "execution_started",
    # "approval_approved", "approval_rejected", "execution_failed"
    action: Mapped[str] = mapped_column(String(100), nullable=False)

    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<AuditLog {self.action} user={self.user_id} at={self.timestamp}>"
