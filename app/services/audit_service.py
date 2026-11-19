"""Audit logging service."""

from __future__ import annotations

from app.database import get_session
from app.models.audit import AuditLog


def log_action(user_id: int | None, action: str, metadata: dict | None = None) -> None:
    with get_session() as session:
        session.add(AuditLog(user_id=user_id, action=action, metadata_json=metadata or {}))


def list_recent(limit: int = 100) -> list[dict]:
    with get_session() as session:
        entries = (
            session.query(AuditLog)
            .order_by(AuditLog.timestamp.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "id": e.id,
                "user_id": e.user_id,
                "action": e.action,
                "metadata": e.metadata_json,
                "timestamp": e.timestamp.isoformat(),
            }
            for e in entries
        ]
