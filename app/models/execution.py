"""Models tracking a single run of a workflow and any approval steps it needs."""

from datetime import datetime

from sqlalchemy import String, Integer, DateTime, ForeignKey, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


# Execution / node statuses (kept as plain strings for SQLite simplicity)
STATUS_PENDING = "pending"
STATUS_RUNNING = "running"
STATUS_WAITING = "waiting"        # waiting on approval / delay
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"
STATUS_CANCELLED = "cancelled"


class WorkflowExecution(Base):
    __tablename__ = "workflow_executions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workflow_id: Mapped[int] = mapped_column(ForeignKey("workflows.id"), nullable=False)
    workflow_version_id: Mapped[int] = mapped_column(
        ForeignKey("workflow_versions.id"), nullable=False
    )
    started_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=True)

    status: Mapped[str] = mapped_column(String(20), default=STATUS_PENDING)
    current_node_id: Mapped[str] = mapped_column(String(50), nullable=True)

    # Arbitrary key/value data the workflow operates on
    # (e.g. {"amount": 12000, "requester": "alice"})
    context: Mapped[dict] = mapped_column(JSON, default=dict)

    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    error_message: Mapped[str] = mapped_column(Text, nullable=True)

    logs: Mapped[list["ExecutionLog"]] = relationship(
        back_populates="execution", cascade="all, delete-orphan"
    )
    approvals: Mapped[list["ApprovalRequest"]] = relationship(
        back_populates="execution", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<WorkflowExecution {self.id} status={self.status} node={self.current_node_id}>"


class ExecutionLog(Base):
    """A record of each node transition / event for an execution."""

    __tablename__ = "execution_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    execution_id: Mapped[int] = mapped_column(ForeignKey("workflow_executions.id"))
    node_id: Mapped[str] = mapped_column(String(50), nullable=True)
    node_type: Mapped[str] = mapped_column(String(50), nullable=True)
    message: Mapped[str] = mapped_column(Text, default="")
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    execution: Mapped["WorkflowExecution"] = relationship(back_populates="logs")


class ApprovalRequest(Base):
    """Represents a pending/decided human approval for an approval node."""

    __tablename__ = "approval_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    execution_id: Mapped[int] = mapped_column(ForeignKey("workflow_executions.id"))
    node_id: Mapped[str] = mapped_column(String(50), nullable=False)

    assigned_to_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=True)
    # Optionally, assign by role instead of a specific user (e.g. "Manager")
    assigned_role: Mapped[str] = mapped_column(String(50), nullable=True)

    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending/approved/rejected
    comment: Mapped[str] = mapped_column(Text, default="")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    decided_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    decided_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=True)

    execution: Mapped["WorkflowExecution"] = relationship(back_populates="approvals")

    def __repr__(self) -> str:
        return f"<ApprovalRequest exec={self.execution_id} node={self.node_id} status={self.status}>"
