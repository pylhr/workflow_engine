"""CRUD and versioning operations for Workflows.

Versioning rules (per the spec):
  - Editing a workflow creates/updates a draft `WorkflowVersion`
    (is_published=False).
  - Publishing a version sets `Workflow.published_version_id` and marks
    that version `is_published=True`. New manual/scheduled executions use
    the published version.
  - Already-running executions keep using the `workflow_version_id` they
    were started with (stored on `WorkflowExecution`), so publishing a
    new version never affects in-flight executions.
"""

from __future__ import annotations

from app.database import get_session
from app.models.workflow import Workflow, WorkflowVersion
from app.services import audit_service


EMPTY_DEFINITION = {"nodes": [], "edges": []}


def create_workflow(name: str, description: str, created_by_id: int | None,
                     definition: dict | None = None) -> int:
    with get_session() as session:
        workflow = Workflow(name=name, description=description, created_by_id=created_by_id)
        session.add(workflow)
        session.flush()

        version = WorkflowVersion(
            workflow_id=workflow.id,
            version_number=1,
            definition=definition or EMPTY_DEFINITION,
            is_published=False,
        )
        session.add(version)
        session.flush()
        workflow_id = workflow.id

    audit_service.log_action(created_by_id, "workflow_created", {"workflow_id": workflow_id, "name": name})
    return workflow_id


def save_draft_version(workflow_id: int, definition: dict, edited_by_id: int | None) -> int:
    """Create a new draft version with the given definition. Returns version id."""
    with get_session() as session:
        latest = (
            session.query(WorkflowVersion)
            .filter_by(workflow_id=workflow_id)
            .order_by(WorkflowVersion.version_number.desc())
            .first()
        )
        next_number = (latest.version_number + 1) if latest else 1

        version = WorkflowVersion(
            workflow_id=workflow_id,
            version_number=next_number,
            definition=definition,
            is_published=False,
        )
        session.add(version)
        session.flush()
        version_id = version.id

    audit_service.log_action(
        edited_by_id, "workflow_updated",
        {"workflow_id": workflow_id, "version": next_number},
    )
    return version_id


def publish_version(workflow_id: int, version_id: int, published_by_id: int | None) -> None:
    with get_session() as session:
        workflow = session.get(Workflow, workflow_id)
        version = session.get(WorkflowVersion, version_id)
        if version.workflow_id != workflow_id:
            raise ValueError("Version does not belong to this workflow.")

        # Validate before publishing
        from app.core.graph import WorkflowGraph
        WorkflowGraph(version.definition).validate()

        version.is_published = True
        workflow.published_version_id = version.id
        version_number = version.version_number

    audit_service.log_action(
        published_by_id, "workflow_published",
        {"workflow_id": workflow_id, "version": version_number},
    )


def list_workflows() -> list[dict]:
    with get_session() as session:
        workflows = session.query(Workflow).all()
        return [
            {
                "id": w.id,
                "name": w.name,
                "description": w.description,
                "published_version_id": w.published_version_id,
                "version_count": len(w.versions),
            }
            for w in workflows
        ]


def get_workflow_definition(workflow_id: int, version_id: int | None = None) -> dict:
    """Return the JSON definition for `version_id`, or the latest version if None."""
    with get_session() as session:
        if version_id is not None:
            version = session.get(WorkflowVersion, version_id)
        else:
            version = (
                session.query(WorkflowVersion)
                .filter_by(workflow_id=workflow_id)
                .order_by(WorkflowVersion.version_number.desc())
                .first()
            )
        if version is None:
            return EMPTY_DEFINITION
        return version.definition


def get_published_version_id(workflow_id: int) -> int | None:
    with get_session() as session:
        workflow = session.get(Workflow, workflow_id)
        return workflow.published_version_id if workflow else None


def list_versions(workflow_id: int) -> list[dict]:
    with get_session() as session:
        versions = (
            session.query(WorkflowVersion)
            .filter_by(workflow_id=workflow_id)
            .order_by(WorkflowVersion.version_number.desc())
            .all()
        )
        return [
            {"id": v.id, "version_number": v.version_number, "is_published": v.is_published}
            for v in versions
        ]


def delete_workflow(workflow_id: int, deleted_by_id: int | None) -> None:
    with get_session() as session:
        workflow = session.get(Workflow, workflow_id)
        if workflow is None:
            return
        session.delete(workflow)

    audit_service.log_action(deleted_by_id, "workflow_deleted", {"workflow_id": workflow_id})
