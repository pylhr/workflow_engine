"""Workflow execution engine.

Drives a single `WorkflowExecution` through its graph one node at a time.
Designed to be called either:

  - synchronously from a service call (small workflows, instant feedback), or
  - from a background QThread / APScheduler job (so the PyQt UI thread is
    never blocked)

The engine is intentionally DB-driven and stateless between steps: each
call to `run_to_completion_or_wait()` loads the execution + graph fresh,
advances as far as it can without human input, and persists state after
every node. This means execution can safely resume after an app restart.
"""

from __future__ import annotations

from datetime import datetime

from app.database import get_session
from app.core.graph import WorkflowGraph, GraphValidationError
from app.core.engine.nodes import get_node_handler, NodeResult
from app.models.execution import (
    WorkflowExecution,
    ExecutionLog,
    ApprovalRequest,
    STATUS_RUNNING,
    STATUS_WAITING,
    STATUS_COMPLETED,
    STATUS_FAILED,
)
from app.models.workflow import WorkflowVersion
from app.models.user import User
from app.models.notification import Notification


class ExecutionEngine:
    """Stateless-ish engine: each public method opens its own DB session."""

    def run_to_completion_or_wait(self, execution_id: int) -> str:
        """Advance an execution until it completes, fails, or starts waiting.

        Returns the final status string.
        """
        with get_session() as session:
            execution: WorkflowExecution = session.get(WorkflowExecution, execution_id)
            if execution is None:
                raise ValueError(f"No execution with id {execution_id}")

            version: WorkflowVersion = session.get(WorkflowVersion, execution.workflow_version_id)
            graph = WorkflowGraph(version.definition)

            try:
                graph.validate()
            except GraphValidationError as exc:
                execution.status = STATUS_FAILED
                execution.error_message = str(exc)
                execution.completed_at = datetime.utcnow()
                self._log(session, execution, None, None, f"Validation failed: {exc}")
                return STATUS_FAILED

            execution.status = STATUS_RUNNING

            current_node_id = execution.current_node_id or graph.start_node()["id"]

            while True:
                node = graph.get_node(current_node_id)
                handler = get_node_handler(node["type"])
                helpers = self._build_helpers(session, execution)

                result: NodeResult = handler.execute(execution.context or {}, {**node.get("data", {}), "id": node["id"]}, helpers)

                if result.context_updates:
                    execution.context = {**(execution.context or {}), **result.context_updates}

                if result.status == "fail":
                    execution.status = STATUS_FAILED
                    execution.error_message = result.message
                    execution.completed_at = datetime.utcnow()
                    self._log(session, execution, node["id"], node["type"], result.message or "Node failed")
                    return STATUS_FAILED

                if result.status == "complete":
                    execution.status = STATUS_COMPLETED
                    execution.current_node_id = node["id"]
                    execution.completed_at = datetime.utcnow()
                    self._log(session, execution, node["id"], node["type"], "Execution completed")
                    return STATUS_COMPLETED

                if result.status == "wait":
                    execution.status = STATUS_WAITING
                    execution.current_node_id = node["id"]
                    self._log(session, execution, node["id"], node["type"], result.message or "Waiting")
                    return STATUS_WAITING

                # status == "advance"
                next_ids = graph.next_node_ids(node["id"], branch=result.branch)
                self._log(session, execution, node["id"], node["type"], "Advanced")

                if not next_ids:
                    # No outgoing edge and not an explicit end node -> treat as completion.
                    execution.status = STATUS_COMPLETED
                    execution.completed_at = datetime.utcnow()
                    return STATUS_COMPLETED

                # NOTE: simple engine — only follows the first next node.
                # Fan-out to multiple branches would require tracking
                # multiple "active tokens", which is a natural extension
                # point if you need parallel branches.
                current_node_id = next_ids[0]
                execution.current_node_id = current_node_id

    def resume_after_approval(self, execution_id: int) -> str:
        """Call after an ApprovalRequest tied to `execution_id` is decided.

        If approved, moves past the approval node and continues execution.
        If rejected, marks the execution failed.
        """
        with get_session() as session:
            execution: WorkflowExecution = session.get(WorkflowExecution, execution_id)
            version: WorkflowVersion = session.get(WorkflowVersion, execution.workflow_version_id)
            graph = WorkflowGraph(version.definition)

            pending_approval = (
                session.query(ApprovalRequest)
                .filter_by(execution_id=execution_id, node_id=execution.current_node_id)
                .order_by(ApprovalRequest.id.desc())
                .first()
            )
            if pending_approval is None:
                raise ValueError("No approval request found for this execution's current node.")

            if pending_approval.status == "rejected":
                execution.status = STATUS_FAILED
                execution.error_message = f"Rejected at node {execution.current_node_id}"
                execution.completed_at = datetime.utcnow()
                self._log(session, execution, execution.current_node_id, "approval", "Approval rejected")
                return STATUS_FAILED

            next_ids = graph.next_node_ids(execution.current_node_id)
            if not next_ids:
                execution.status = STATUS_COMPLETED
                execution.completed_at = datetime.utcnow()
                return STATUS_COMPLETED

            execution.current_node_id = next_ids[0]
            execution.status = STATUS_RUNNING

        # Continue running outside the approval-handling session.
        return self.run_to_completion_or_wait(execution_id)

    def resume_after_delay(self, execution_id: int) -> str:
        """Called by the scheduler once a delay node's wait time has elapsed."""
        with get_session() as session:
            execution: WorkflowExecution = session.get(WorkflowExecution, execution_id)
            version: WorkflowVersion = session.get(WorkflowVersion, execution.workflow_version_id)
            graph = WorkflowGraph(version.definition)

            next_ids = graph.next_node_ids(execution.current_node_id)
            if not next_ids:
                execution.status = STATUS_COMPLETED
                execution.completed_at = datetime.utcnow()
                return STATUS_COMPLETED

            execution.current_node_id = next_ids[0]
            execution.status = STATUS_RUNNING

        return self.run_to_completion_or_wait(execution_id)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _log(self, session, execution: WorkflowExecution, node_id, node_type, message: str) -> None:
        session.add(
            ExecutionLog(
                execution_id=execution.id,
                node_id=node_id,
                node_type=node_type,
                message=message,
            )
        )

    def _build_helpers(self, session, execution: WorkflowExecution) -> dict:
        def create_approval_request(node_id, assigned_role=None, assigned_to_id=None):
            session.add(
                ApprovalRequest(
                    execution_id=execution.id,
                    node_id=node_id,
                    assigned_role=assigned_role,
                    assigned_to_id=assigned_to_id,
                )
            )
            # Notify everyone with the assigned role
            if assigned_role:
                for user in session.query(User).join(User.role).filter_by(name=assigned_role).all():
                    session.add(
                        Notification(
                            user_id=user.id,
                            title="Approval requested",
                            message=f"Execution #{execution.id} needs your approval.",
                            category="approval_request",
                            related_execution_id=execution.id,
                        )
                    )

        def schedule_resume(node_id, run_at):
            # The actual APScheduler job is registered by core/scheduler.py
            # via execution_service, which has access to the scheduler
            # instance. This helper just records intent in the log;
            # see execution_service.advance_execution() for wiring.
            pass

        def send_notification(user_id=None, role=None, title="", message="", category="info"):
            recipients = []
            if user_id:
                recipients.append(user_id)
            if role:
                recipients.extend(
                    u.id for u in session.query(User).join(User.role).filter_by(name=role).all()
                )
            for uid in recipients or [None]:
                if uid is None:
                    continue
                session.add(
                    Notification(
                        user_id=uid,
                        title=title,
                        message=message,
                        category=category,
                        related_execution_id=execution.id,
                    )
                )

        def log(message: str):
            self._log(session, execution, execution.current_node_id, None, message)

        return {
            "create_approval_request": create_approval_request,
            "schedule_resume": schedule_resume,
            "send_notification": send_notification,
            "log": log,
        }
