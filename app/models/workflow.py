"""Workflow definition and versioning models.

A `Workflow` is a named container; each `WorkflowVersion` stores the actual
graph definition (nodes + edges) as JSON, mirroring the node/edge format
produced by the PyQt designer canvas:

{
  "nodes": [{"id": "1", "type": "start", "data": {...}}, ...],
  "edges": [{"from": "1", "to": "2", "data": {...}}, ...]
}
"""

from datetime import datetime

from sqlalchemy import String, Integer, DateTime, ForeignKey, Boolean, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Workflow(Base):
    __tablename__ = "workflows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # The version number that new manual executions / schedules should use.
    published_version_id: Mapped[int] = mapped_column(
        ForeignKey("workflow_versions.id"), nullable=True
    )

    versions: Mapped[list["WorkflowVersion"]] = relationship(
        back_populates="workflow",
        foreign_keys="WorkflowVersion.workflow_id",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Workflow {self.name!r} (id={self.id})>"


class WorkflowVersion(Base):
    __tablename__ = "workflow_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workflow_id: Mapped[int] = mapped_column(ForeignKey("workflows.id"), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)

    # Graph definition: {"nodes": [...], "edges": [...]}
    definition: Mapped[dict] = mapped_column(JSON, nullable=False)

    is_published: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    workflow: Mapped["Workflow"] = relationship(
        back_populates="versions", foreign_keys=[workflow_id]
    )

    def __repr__(self) -> str:
        return f"<WorkflowVersion {self.workflow_id}/v{self.version_number}>"


class WorkflowSchedule(Base):
    """Optional recurring trigger for a workflow (APScheduler job)."""

    __tablename__ = "workflow_schedules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workflow_id: Mapped[int] = mapped_column(ForeignKey("workflows.id"), nullable=False)

    # "interval" or "cron"
    trigger_type: Mapped[str] = mapped_column(String(20), nullable=False)
    # For interval: e.g. {"hours": 24}. For cron: e.g. {"hour": 9, "minute": 0}
    trigger_args: Mapped[dict] = mapped_column(JSON, default=dict)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    apscheduler_job_id: Mapped[str] = mapped_column(String(100), nullable=True)

    def __repr__(self) -> str:
        return f"<WorkflowSchedule workflow={self.workflow_id} {self.trigger_type}>"
