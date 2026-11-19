"""Drag-and-drop workflow designer canvas.

`WorkflowCanvasScene` hosts `NodeItem`s and `EdgeItem`s. Connections are
made by dragging from a node's output port (right side) to another node's
input port (left side); a temporary rubber-band line is shown while
dragging.

`WorkflowDesignerWidget` wraps the scene/view in a toolbar (one button per
node type) plus Save/Publish actions, and provides `to_definition()` /
`load_definition()` to convert to/from the JSON graph format used by
`WorkflowVersion.definition`.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, QPointF, QLineF
from PyQt6.QtGui import QPen, QColor, QBrush
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGraphicsScene,
    QGraphicsView,
    QGraphicsLineItem,
    QPushButton,
    QToolBar,
    QInputDialog,
    QMessageBox,
    QLabel,
)

from app.ui.designer.node_items import NodeItem, PortItem, NODE_LABELS
from app.ui.designer.edge_items import EdgeItem


class WorkflowCanvasScene(QGraphicsScene):
    """QGraphicsScene that supports dragging connections between node ports."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pending_edge_source: PortItem | None = None
        self._temp_line: QGraphicsLineItem | None = None

    def _port_at(self, scene_pos) -> PortItem | None:
        """Return a PortItem near `scene_pos`, even if other items overlap it.

        Uses `items()` (all items under the point) rather than `itemAt()`
        (topmost only), since a NodeItem's rect can otherwise shadow its
        own port handles.
        """
        for item in self.items(scene_pos):
            if isinstance(item, PortItem):
                return item
        return None

    def mousePressEvent(self, event):
        port = self._port_at(event.scenePos())
        if port is not None and port.is_output:
            self._pending_edge_source = port
            pos = port.scene_pos()
            self._temp_line = QGraphicsLineItem(QLineF(pos, pos))
            self._temp_line.setPen(QPen(QColor("#888888"), 2, Qt.PenStyle.DashLine))
            self._temp_line.setZValue(20)
            self.addItem(self._temp_line)
            return  # don't propagate, so the node itself doesn't get dragged
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._temp_line is not None and self._pending_edge_source is not None:
            start = self._pending_edge_source.scene_pos()
            self._temp_line.setLine(QLineF(start, event.scenePos()))
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._temp_line is not None:
            target_port = self._port_at(event.scenePos())
            self.removeItem(self._temp_line)
            self._temp_line = None

            if target_port is not None and not target_port.is_output:
                source_node = self._pending_edge_source.node_item
                target_node = target_port.node_item
                if source_node is not target_node:
                    self._create_edge(source_node, target_node)

            self._pending_edge_source = None
            return
        super().mouseReleaseEvent(event)

    def _create_edge(self, source: NodeItem, target: NodeItem) -> None:
        branch = None
        if source.node_type == "condition":
            # Ask which branch this edge represents.
            choice, ok = QInputDialog.getItem(
                self.views()[0] if self.views() else None,
                "Condition Branch",
                "This edge should be followed when the condition is:",
                ["true", "false"],
                editable=False,
            )
            if not ok:
                return
            branch = choice

        edge = EdgeItem(source, target, branch=branch)
        for graphics_item in edge.graphics_items():
            self.addItem(graphics_item)


class WorkflowDesignerWidget(QWidget):
    """Toolbar + canvas for visually building a workflow graph."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._next_node_index = 1
        self.node_items: dict[str, NodeItem] = {}
        self.edge_items: list[EdgeItem] = []

        self.scene = WorkflowCanvasScene(self)
        self.scene.setSceneRect(0, 0, 2000, 1200)

        self.view = QGraphicsView(self.scene)
        self.view.setRenderHints(self.view.renderHints())
        self.view.setDragMode(QGraphicsView.DragMode.RubberBandDrag)

        layout = QVBoxLayout(self)
        layout.addWidget(self._build_toolbar())
        layout.addWidget(self.view)

        layout.addWidget(QLabel(
            "Tip: drag from the right-side circle of a node to the left-side "
            "circle of another node to connect them. Double-click a node to "
            "edit its settings (where applicable)."
        ))

    # ------------------------------------------------------------------
    def _build_toolbar(self) -> QToolBar:
        toolbar = QToolBar()
        for node_type, label in NODE_LABELS.items():
            button = QPushButton(f"+ {label}")
            button.clicked.connect(lambda _checked, t=node_type: self.add_node(t))
            toolbar.addWidget(button)

        clear_button = QPushButton("Clear Canvas")
        clear_button.clicked.connect(self.clear_canvas)
        toolbar.addWidget(clear_button)
        return toolbar

    # ------------------------------------------------------------------
    def add_node(self, node_type: str, x: float | None = None, y: float | None = None,
                  data: dict | None = None, node_id: str | None = None) -> NodeItem:
        if node_type == "start" and any(n.node_type == "start" for n in self.node_items.values()):
            QMessageBox.warning(self, "Invalid", "A workflow can only have one Start node.")
            return None

        if node_id is None:
            node_id = str(self._next_node_index)
        self._next_node_index = max(self._next_node_index, _safe_int(node_id) + 1)

        if x is None:
            x = 40 + 160 * (len(self.node_items) % 6)
        if y is None:
            y = 40 + 100 * (len(self.node_items) // 6)

        node_item = NodeItem(node_id=node_id, node_type=node_type, data=data, x=x, y=y)
        self.scene.addItem(node_item)
        self.node_items[node_id] = node_item
        return node_item

    def clear_canvas(self) -> None:
        self.scene.clear()
        self.node_items.clear()
        self.edge_items.clear()
        self._next_node_index = 1

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------
    def to_definition(self) -> dict:
        nodes = [node.to_dict() for node in self.node_items.values()]
        edges = []
        seen_edges = set()
        for node in self.node_items.values():
            for edge in node.edges:
                key = id(edge)
                if key in seen_edges:
                    continue
                seen_edges.add(key)
                edges.append(edge.to_dict())
        return {"nodes": nodes, "edges": edges}

    def load_definition(self, definition: dict) -> None:
        self.clear_canvas()
        node_lookup: dict[str, NodeItem] = {}

        for i, node in enumerate(definition.get("nodes", [])):
            x = 40 + 160 * (i % 6)
            y = 40 + 100 * (i // 6)
            item = self.add_node(
                node["type"], x=x, y=y, data=node.get("data"), node_id=node["id"]
            )
            node_lookup[node["id"]] = item

        for edge in definition.get("edges", []):
            source = node_lookup.get(edge["from"])
            target = node_lookup.get(edge["to"])
            if source is None or target is None:
                continue
            branch = edge.get("data", {}).get("branch")
            edge_item = EdgeItem(source, target, branch=branch, data=edge.get("data"))
            for graphics_item in edge_item.graphics_items():
                self.scene.addItem(graphics_item)


def _safe_int(value: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
