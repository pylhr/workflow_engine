"""Graph representation of a workflow definition.

Wraps the {"nodes": [...], "edges": [...]} JSON produced by the PyQt
designer canvas and provides validation + traversal helpers used by the
execution engine.

Node dict shape:
    {"id": "2", "type": "approval", "data": {...}}

Edge dict shape:
    {"from": "1", "to": "2", "data": {"condition": "amount > 10000"}}
    (the optional "data.condition" is used by condition nodes to pick
    which outgoing edge to follow)
"""

from collections import defaultdict, deque


class GraphValidationError(Exception):
    pass


class WorkflowGraph:
    def __init__(self, definition: dict):
        self.nodes: dict[str, dict] = {n["id"]: n for n in definition.get("nodes", [])}
        self.edges: list[dict] = list(definition.get("edges", []))

        self._outgoing: dict[str, list[dict]] = defaultdict(list)
        self._incoming: dict[str, list[dict]] = defaultdict(list)
        for edge in self.edges:
            self._outgoing[edge["from"]].append(edge)
            self._incoming[edge["to"]].append(edge)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    def validate(self) -> None:
        """Raise GraphValidationError if the graph is structurally invalid."""
        if not self.nodes:
            raise GraphValidationError("Workflow has no nodes.")

        start_nodes = [n for n in self.nodes.values() if n["type"] == "start"]
        end_nodes = [n for n in self.nodes.values() if n["type"] == "end"]

        if len(start_nodes) != 1:
            raise GraphValidationError(
                f"Workflow must have exactly one 'start' node (found {len(start_nodes)})."
            )
        if not end_nodes:
            raise GraphValidationError("Workflow must have at least one 'end' node.")

        # All edge endpoints must reference existing nodes
        for edge in self.edges:
            if edge["from"] not in self.nodes:
                raise GraphValidationError(f"Edge references unknown source node '{edge['from']}'.")
            if edge["to"] not in self.nodes:
                raise GraphValidationError(f"Edge references unknown target node '{edge['to']}'.")

        if self._has_cycle():
            raise GraphValidationError("Workflow graph contains a cycle (must be a DAG).")

        # Every node except 'start' must be reachable from the start node
        reachable = self._reachable_from(self.start_node()["id"])
        unreachable = set(self.nodes) - reachable
        if unreachable:
            raise GraphValidationError(
                f"Nodes not reachable from start: {sorted(unreachable)}"
            )

    def _has_cycle(self) -> bool:
        visiting, visited = set(), set()

        def dfs(node_id: str) -> bool:
            if node_id in visiting:
                return True
            if node_id in visited:
                return False
            visiting.add(node_id)
            for edge in self._outgoing.get(node_id, []):
                if dfs(edge["to"]):
                    return True
            visiting.discard(node_id)
            visited.add(node_id)
            return False

        return any(dfs(n) for n in self.nodes)

    def _reachable_from(self, node_id: str) -> set[str]:
        seen = {node_id}
        queue = deque([node_id])
        while queue:
            current = queue.popleft()
            for edge in self._outgoing.get(current, []):
                if edge["to"] not in seen:
                    seen.add(edge["to"])
                    queue.append(edge["to"])
        return seen

    # ------------------------------------------------------------------
    # Traversal
    # ------------------------------------------------------------------
    def start_node(self) -> dict:
        for node in self.nodes.values():
            if node["type"] == "start":
                return node
        raise GraphValidationError("No start node found.")

    def get_node(self, node_id: str) -> dict:
        return self.nodes[node_id]

    def outgoing_edges(self, node_id: str) -> list[dict]:
        return self._outgoing.get(node_id, [])

    def next_node_ids(self, node_id: str, branch: str | None = None) -> list[str]:
        """Return the id(s) of the node(s) following `node_id`.

        For condition nodes, `branch` should be "true"/"false" (or any
        label matching `edge["data"]["branch"]`) to select the matching
        outgoing edge. For all other node types, every outgoing edge is
        followed (allows simple fan-out/fan-in patterns).
        """
        edges = self.outgoing_edges(node_id)
        if branch is not None:
            matching = [e for e in edges if e.get("data", {}).get("branch") == branch]
            return [e["to"] for e in matching] if matching else [e["to"] for e in edges]
        return [e["to"] for e in edges]

    def topological_order(self) -> list[str]:
        """Return node ids in an order respecting dependencies (Kahn's algorithm)."""
        in_degree = {n: len(self._incoming.get(n, [])) for n in self.nodes}
        queue = deque([n for n, deg in in_degree.items() if deg == 0])
        order = []
        while queue:
            node_id = queue.popleft()
            order.append(node_id)
            for edge in self._outgoing.get(node_id, []):
                in_degree[edge["to"]] -= 1
                if in_degree[edge["to"]] == 0:
                    queue.append(edge["to"])
        if len(order) != len(self.nodes):
            raise GraphValidationError("Cycle detected during topological sort.")
        return order
