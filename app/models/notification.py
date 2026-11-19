"""In-app notification model.

Email/Slack/Teams channels are future extensions (see notification_service
for where to plug those in) — for the standalone desktop edition,
notifications are stored locally and shown in the dashboard's
"Notifications" panel / a tray popup.
"""

from datetime import datetime

from sqlalchemy import String, Integer, DateTime, ForeignKey, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, default="")

    # e.g. "approval_request", "workflow_failed", "workflow_completed"
    category: Mapped[str] = mapped_column(String(50), default="info")

    related_execution_id: Mapped[int] = mapped_column(
        ForeignKey("workflow_executions.id"), nullable=True
    )

    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<Notification user={self.user_id} {self.title!r} read={self.is_read}>"
