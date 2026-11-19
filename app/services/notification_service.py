"""In-app notification service.

TODO: add an email channel here (e.g. via smtplib) for users who want
notifications outside the app, as described in the original spec's
"Notification System" section.
"""

from __future__ import annotations

from app.database import get_session
from app.models.notification import Notification
from app.models.user import User


def notify_user(user_id: int, title: str, message: str, category: str = "info",
                 related_execution_id: int | None = None) -> None:
    with get_session() as session:
        session.add(
            Notification(
                user_id=user_id,
                title=title,
                message=message,
                category=category,
                related_execution_id=related_execution_id,
            )
        )


def notify_role(role_name: str, title: str, message: str, category: str = "info",
                 related_execution_id: int | None = None) -> None:
    with get_session() as session:
        users = session.query(User).join(User.role).filter_by(name=role_name).all()
        for user in users:
            session.add(
                Notification(
                    user_id=user.id,
                    title=title,
                    message=message,
                    category=category,
                    related_execution_id=related_execution_id,
                )
            )


def list_for_user(user_id: int, unread_only: bool = False, limit: int = 50) -> list[dict]:
    with get_session() as session:
        query = session.query(Notification).filter_by(user_id=user_id)
        if unread_only:
            query = query.filter_by(is_read=False)
        notifications = query.order_by(Notification.created_at.desc()).limit(limit).all()
        return [
            {
                "id": n.id,
                "title": n.title,
                "message": n.message,
                "category": n.category,
                "related_execution_id": n.related_execution_id,
                "is_read": n.is_read,
                "created_at": n.created_at.isoformat(),
            }
            for n in notifications
        ]


def mark_read(notification_id: int) -> None:
    with get_session() as session:
        notification = session.get(Notification, notification_id)
        if notification:
            notification.is_read = True
