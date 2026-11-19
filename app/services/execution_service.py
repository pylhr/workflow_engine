"""Execution-related operations: starting workflows, listing executions for
the monitoring dashboard, and handling approval decisions.
"""

from __future__ import annotations

from datetime import datetime

from app.database import get_session
from app.core.engine.executor import ExecutionEngine
from app.core.engine.nodes import DelayNode
from app.models.execution import WorkflowExecution, ApprovalRequest, ExecutionLog
from app.models.workflow import Workflow, WorkflowVersion
from app.services import audit_service

_engine = ExecutionEngine()


def start_execution(workflow_id: int, started_by_id: int | None, context: dict | None = None) -> int:
    """Create a new WorkflowExecution using the workflow's published version
    and run it until it completes, fails, or needs to wait. Returns the
    execution id.
    """
    with get_session() as session:
        workflow = session.get(Workflow, workflow_id)
        if workflow is None:
            raise ValueError(f"No workflow with id {workflow_id}")
        if workflow.published_version_id is None:
            raise ValueError(f"Workflow '{workflow.name}' has no published version.")

        execution = WorkflowExecution(
            workflow_id=workflow_id,
            workflow_version_id=workflow.published_version_id,
            started_by_id=started_by_id,
            context=context or {},
        )
        session.add(execution)
        session.flush()
        execution_id = execution.id

    audit_service.log_action(
        started_by_id, "execution_started",
        {"workflow_id": workflow_id, "execution_id": execution_id},
    )

    _engine.run_to_completion_or_wait(execution_id)
    _register_delay_jobs_if_any(execution_id)
    return execution_id


def list_executions(status: str | None = None, limit: int = 100) -> list[dict]:
    with get_session() as session:
        query = session.query(WorkflowExecution)
        if status:
            query = query.filter_by(status=status)
        executions = query.order_by(WorkflowExecution.started_at.desc()).limit(limit).all()

        results = []
        for e in executions:
            workflow = session.get(Workflow, e.workflow_id)
            duration = None
            if e.completed_at:
                duration = (e.completed_at - e.started_at).total_seconds()
            results.append({
                "id": e.id,
                "workflow_id": e.workflow_id,
                "workflow_name": workflow.name if workflow else "?",
                "status": e.status,
                "current_node_id": e.current_node_id,
                "started_at": e.started_at.isoformat(),
                "completed_at": e.completed_at.isoformat() if e.completed_at else None,
                "duration_seconds": duration,
            })
        return results


def dashboard_summary() -> dict:
    with get_session() as session:
        total = session.query(WorkflowExecution).count()
        running = session.query(WorkflowExecution).filter_by(status="running").count()
        waiting = session.query(WorkflowExecution).filter_by(status="waiting").count()
        completed = session.query(WorkflowExecution).filter_by(status="completed").count()
        failed = session.query(WorkflowExecution).filter_by(status="failed").count()
        pending_approvals = session.query(ApprovalRequest).filter_by(status="pending").count()

        return {
            "total": total,
            "running": running,
            "waiting": waiting,
            "completed": completed,
            "failed": failed,
            "pending_approvals": pending_approvals,
        }


def get_execution_logs(execution_id: int) -> list[dict]:
    with get_session() as session:
        logs = (
            session.query(ExecutionLog)
            .filter_by(execution_id=execution_id)
            .order_by(ExecutionLog.timestamp.asc())
            .all()
        )
        return [
            {
                "node_id": log.node_id,
                "node_type": log.node_type,
                "message": log.message,
                "timestamp": log.timestamp.isoformat(),
            }
            for log in logs
        ]


# ----------------------------------------------------------------------
# Approvals
# ----------------------------------------------------------------------
def list_pending_approvals(role_name: str | None = None, user_id: int | None = None) -> list[dict]:
    with get_session() as session:
        query = session.query(ApprovalRequest).filter_by(status="pending")
        if role_name:
            query = query.filter_by(assigned_role=role_name)
        if user_id:
            query = query.filter_by(assigned_to_id=user_id)
        approvals = query.order_by(ApprovalRequest.created_at.asc()).all()

        results = []
        for a in approvals:
            execution = session.get(WorkflowExecution, a.execution_id)
            workflow = session.get(Workflow, execution.workflow_id) if execution else None
            results.append({
                "id": a.id,
                "execution_id": a.execution_id,
                "workflow_name": workflow.name if workflow else "?",
                "node_id": a.node_id,
                "assigned_role": a.assigned_role,
                "created_at": a.created_at.isoformat(),
            })
        return results


def decide_approval(approval_id: int, approved: bool, decided_by_id: int, comment: str = "") -> str:
    """Record the decision and resume the execution. Returns the new execution status."""
    with get_session() as session:
        approval = session.get(ApprovalRequest, approval_id)
        if approval is None:
            raise ValueError(f"No approval request with id {approval_id}")
        if approval.status != "pending":
            raise ValueError("Approval request has already been decided.")

        approval.status = "approved" if approved else "rejected"
        approval.comment = comment
        approval.decided_at = datetime.utcnow()
        approval.decided_by_id = decided_by_id

        execution_id = approval.execution_id

    audit_service.log_action(
        decided_by_id,
        "approval_approved" if approved else "approval_rejected",
        {"execution_id": execution_id, "approval_id": approval_id},
    )

    new_status = _engine.resume_after_approval(execution_id)
    _register_delay_jobs_if_any(execution_id)
    return new_status


# ----------------------------------------------------------------------
# Internal: register APScheduler jobs for any delay node the execution
# is currently waiting on.
# ----------------------------------------------------------------------
def _register_delay_jobs_if_any(execution_id: int) -> None:
    from app.core.scheduler import scheduler_service
    from app.core.graph import WorkflowGraph

    with get_session() as session:
        execution = session.get(WorkflowExecution, execution_id)
        if execution is None or execution.status != "waiting":
            return

        version = session.get(WorkflowVersion, execution.workflow_version_id)
        graph = WorkflowGraph(version.definition)
        node = graph.get_node(execution.current_node_id)
        if node["type"] != "delay":
            return

        from datetime import timedelta
        delay_kwargs = node.get("data", {}).get("delay", {"minutes": 1})
        run_at = datetime.utcnow() + timedelta(**delay_kwargs)

    scheduler_service.schedule_delay_resume(execution_id, run_at)
