"""Pluggable workflow node types.

Each node type implements `execute(context, node_data, execution_helpers)`
and returns a `NodeResult` telling the executor what to do next:
advance, wait (for approval/delay), or fail.

`execution_helpers` is a small bag of callables injected by the executor
so node implementations don't need direct DB/session access:
    - create_approval_request(node_id, assigned_role=None, assigned_to_id=None)
    - schedule_resume(node_id, run_at) -> used by delay nodes
    - send_notification(user_id, title, message, category)
    - log(message)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable


@dataclass
class NodeResult:
    # "advance" | "wait" | "fail" | "complete"
    status: str
    # For condition nodes: which outgoing branch to follow ("true"/"false"/label)
    branch: str | None = None
    # Updates to merge into the execution's context dict
    context_updates: dict[str, Any] = field(default_factory=dict)
    message: str = ""


class BaseNode:
    """Base class for all node types. Subclasses set `node_type`."""

    node_type: str = "base"

    def execute(self, context: dict, node_data: dict, helpers: dict[str, Callable]) -> NodeResult:
        raise NotImplementedError


class StartNode(BaseNode):
    node_type = "start"

    def execute(self, context, node_data, helpers):
        helpers["log"]("Workflow started.")
        return NodeResult(status="advance")


class EndNode(BaseNode):
    node_type = "end"

    def execute(self, context, node_data, helpers):
        helpers["log"]("Workflow reached end node.")
        return NodeResult(status="complete")


class ApprovalNode(BaseNode):
    """Pauses execution until a Manager/Admin approves or rejects."""

    node_type = "approval"

    def execute(self, context, node_data, helpers):
        assigned_role = node_data.get("assigned_role", "Manager")
        helpers["create_approval_request"](node_data["id"], assigned_role=assigned_role)
        helpers["log"](f"Waiting for approval (role={assigned_role}).")
        return NodeResult(status="wait", message="Waiting for approval")


class ConditionNode(BaseNode):
    """Evaluates a simple boolean expression against the context.

    `node_data["condition"]` is a Python expression string, e.g.
    "amount > 10000", evaluated with `context` as the local namespace.
    On True, follows edges where edge.data.branch == "true"; otherwise "false".
    """

    node_type = "condition"

    def execute(self, context, node_data, helpers):
        expr = node_data.get("condition", "True")
        try:
            # Restricted eval: no builtins, only the workflow context variables.
            result = bool(eval(expr, {"__builtins__": {}}, dict(context)))
        except Exception as exc:
            return NodeResult(status="fail", message=f"Condition evaluation error: {exc}")

        branch = "true" if result else "false"
        helpers["log"](f"Condition '{expr}' evaluated to {result} -> branch '{branch}'.")
        return NodeResult(status="advance", branch=branch)


class DelayNode(BaseNode):
    """Pauses execution for a configured duration.

    `node_data["delay"]` example: {"hours": 24} or {"days": 7} or {"minutes": 30}.
    The executor's scheduler will resume the workflow at the computed time.
    """

    node_type = "delay"

    def execute(self, context, node_data, helpers):
        delay_kwargs = node_data.get("delay", {"minutes": 1})
        run_at = datetime.utcnow() + timedelta(**delay_kwargs)
        helpers["schedule_resume"](node_data["id"], run_at)
        helpers["log"](f"Delaying until {run_at.isoformat()} ({delay_kwargs}).")
        return NodeResult(status="wait", message=f"Delayed until {run_at.isoformat()}")


class NotificationNode(BaseNode):
    """Sends an in-app notification (email channel is a TODO extension)."""

    node_type = "notification"

    def execute(self, context, node_data, helpers):
        title = node_data.get("title", "Workflow Notification")
        message = node_data.get("message", "").format(**context) if context else node_data.get("message", "")
        target_user_id = node_data.get("user_id")
        target_role = node_data.get("role")

        helpers["send_notification"](
            user_id=target_user_id,
            role=target_role,
            title=title,
            message=message,
            category="info",
        )
        helpers["log"](f"Sent notification '{title}'.")
        return NodeResult(status="advance")


class WebhookNode(BaseNode):
    """Calls an external HTTP endpoint.

    TODO: implement actual HTTP request (e.g. via `requests` or
    `urllib.request`) using node_data["url"], node_data["method"], and
    node_data["payload_template"]. Left unimplemented to avoid making
    outbound calls from this skeleton.
    """

    node_type = "webhook"

    def execute(self, context, node_data, helpers):
        helpers["log"](
            f"[TODO] Webhook node would call {node_data.get('method', 'POST')} "
            f"{node_data.get('url', '<no url configured>')}"
        )
        return NodeResult(status="advance")


class ScriptNode(BaseNode):
    """Executes a small Python expression against the context and stores the result.

    `node_data["script"]` is an expression string (e.g. "salary * tax_rate").
    `node_data["output_key"]` is the context key to store the result under.
    Uses a restricted `eval` (no builtins) — fine for simple arithmetic,
    NOT a substitute for a real sandbox if scripts come from untrusted users.
    """

    node_type = "script"

    def execute(self, context, node_data, helpers):
        script = node_data.get("script", "")
        output_key = node_data.get("output_key", "result")
        try:
            result = eval(script, {"__builtins__": {}}, dict(context))
        except Exception as exc:
            return NodeResult(status="fail", message=f"Script error: {exc}")

        helpers["log"](f"Script '{script}' -> {output_key} = {result!r}")
        return NodeResult(status="advance", context_updates={output_key: result})


# Registry mapping node "type" strings (as used in workflow JSON) to implementations.
NODE_REGISTRY: dict[str, BaseNode] = {
    "start": StartNode(),
    "end": EndNode(),
    "approval": ApprovalNode(),
    "condition": ConditionNode(),
    "delay": DelayNode(),
    "notification": NotificationNode(),
    "webhook": WebhookNode(),
    "script": ScriptNode(),
}


def get_node_handler(node_type: str) -> BaseNode:
    try:
        return NODE_REGISTRY[node_type]
    except KeyError:
        raise ValueError(f"Unknown node type: '{node_type}'")
