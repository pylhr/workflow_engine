"""Graphics items representing workflow nodes on the PyQt designer canvas.

Each `NodeItem` is a draggable rounded rectangle with a label, plus an
input port (left) and output port (right) that `EdgeItem`s attach to.
Double-clicking a node opens a small property editor dialog (for things
like an approval node's `assigned_role`, a condition node's `condition`
expression, a delay node's duration, etc.).
"""

from __future__ import annotations

from PyQt6.QtCore import QRectF, Qt, QPointF
from PyQt6.QtGui import QBrush, QColor, QPen, QFont
from PyQt6.QtWidgets import (
    QGraphicsItem,
    QGraphicsRectItem,
    QGraphicsEllipseItem,
    QGraphicsTextItem,
    QGraphicsSceneMouseEvent,
)

NODE_WIDTH = 140
NODE_HEIGHT = 60
PORT_RADIUS = 7
PORT_CLICK_RADIUS = 12  # larger invisible hit-area so ports are easy to grab

# Color per node type, used as a quick visual legend on the canvas.
NODE_COLORS = {
    "start": "#4CAF50",
    "end": "#F44336",
    "approval": "#2196F3",
    "condition": "#FF9800",
    "delay": "#9C27B0",
    "notification": "#00BCD4",
    "webhook": "#607D8B",
    "script": "#795548",
}

NODE_LABELS = {
    "start": "Start",
    "end": "End",
    "approval": "Approval",
    "condition": "Condition",
    "delay": "Delay",
    "notification": "Notification",
    "webhook": "Webhook",
    "script": "Script",
}


class PortItem(QGraphicsEllipseItem):
    """A connection point on a NodeItem (input or output).

    Drawn as a small circle, but with a larger invisible bounding/shape
    area (PORT_CLICK_RADIUS) so it's easy to click and drag precisely.
    """

    def __init__(self, parent: "NodeItem", is_output: bool):
        size = PORT_RADIUS * 2
        super().__init__(-PORT_RADIUS, -PORT_RADIUS, size, size, parent)
        self.node_item = parent
        self.is_output = is_output
        self.setBrush(QBrush(QColor("#FFEB3B")))  # bright yellow handle, easy to spot
        self.setPen(QPen(QColor("#333333"), 1.5))
        self.setAcceptHoverEvents(True)
        self.setZValue(10)

    def boundingRect(self) -> QRectF:
        r = PORT_CLICK_RADIUS
        return QRectF(-r, -r, r * 2, r * 2)

    def shape(self):
        from PyQt6.QtGui import QPainterPath
        path = QPainterPath()
        r = PORT_CLICK_RADIUS
        path.addEllipse(QRectF(-r, -r, r * 2, r * 2))
        return path

    def scene_pos(self) -> QPointF:
        return self.mapToScene(0, 0)


class NodeItem(QGraphicsRectItem):
    """A draggable workflow node box with input/output ports and a label."""

    def __init__(self, node_id: str, node_type: str, data: dict | None = None,
                 x: float = 0, y: float = 0):
        super().__init__(0, 0, NODE_WIDTH, NODE_HEIGHT)
        self.node_id = node_id
        self.node_type = node_type
        self.data = data or {}

        self.setPos(x, y)
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
            | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )

        color = QColor(NODE_COLORS.get(node_type, "#9E9E9E"))
        self.setBrush(QBrush(color))
        self.setPen(QPen(QColor("#333333"), 1.5))

        label_text = NODE_LABELS.get(node_type, node_type.title())
        self.label = QGraphicsTextItem(label_text, self)
        self.label.setDefaultTextColor(QColor("#FFFFFF"))
        self.label.setFont(QFont("Sans Serif", 9, QFont.Weight.Bold))
        self._center_label()

        # Output port on the right edge, input port on the left edge.
        self.input_port = PortItem(self, is_output=False)
        self.input_port.setPos(0, NODE_HEIGHT / 2)
        self.output_port = PortItem(self, is_output=True)
        self.output_port.setPos(NODE_WIDTH, NODE_HEIGHT / 2)

        # Edges connected to this node, kept so they can be updated on move.
        self.edges: list = []

        if self.data:
            self._refresh_label()

    def _center_label(self) -> None:
        rect = self.label.boundingRect()
        self.label.setPos(
            (NODE_WIDTH - rect.width()) / 2,
            (NODE_HEIGHT - rect.height()) / 2,
        )

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            for edge in self.edges:
                edge.update_path()
        return super().itemChange(change, value)

    def mouseDoubleClickEvent(self, event):
        from app.ui.designer.node_properties_dialog import NodePropertiesDialog

        dialog = NodePropertiesDialog(self.node_type, self.data, parent=event.widget())
        if dialog.exec() == NodePropertiesDialog.DialogCode.Accepted:
            self.data = dialog.result_data()
            self._refresh_label()
        event.accept()

    def _refresh_label(self) -> None:
        """Update the node's on-canvas label to reflect key configured data,
        so configured nodes are visually distinguishable at a glance.
        """
        base_label = NODE_LABELS.get(self.node_type, self.node_type.title())
        summary = ""
        if self.node_type == "condition" and self.data.get("condition"):
            summary = self.data["condition"]
        elif self.node_type == "approval" and self.data.get("assigned_role"):
            summary = f"role: {self.data['assigned_role']}"
        elif self.node_type == "delay" and self.data.get("delay"):
            unit, amount = next(iter(self.data["delay"].items()))
            summary = f"{amount} {unit}"
        elif self.node_type == "notification" and self.data.get("title"):
            summary = self.data["title"]
        elif self.node_type == "script" and self.data.get("script"):
            summary = self.data["script"]
        elif self.node_type == "webhook" and self.data.get("url"):
            summary = self.data["url"]

        text = base_label if not summary else f"{base_label}\n{_truncate(summary, 20)}"
        self.label.setPlainText(text)
        self._center_label()

    def to_dict(self) -> dict:
        return {"id": self.node_id, "type": self.node_type, "data": dict(self.data)}


def _truncate(text: str, max_len: int) -> str:
    return text if len(text) <= max_len else text[: max_len - 1] + "…"
