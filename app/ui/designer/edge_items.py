"""Graphics item representing a directed edge (connection) between two nodes."""

from __future__ import annotations

from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QPen, QColor, QPolygonF
from PyQt6.QtWidgets import QGraphicsLineItem, QGraphicsPolygonItem
import math

from app.ui.designer.node_items import NodeItem

ARROW_SIZE = 10


class EdgeItem(QGraphicsLineItem):
    """A line from `source.output_port` to `target.input_port`, with an
    arrowhead and optional branch metadata (for condition node outputs).
    """

    def __init__(self, source: NodeItem, target: NodeItem, branch: str | None = None,
                 data: dict | None = None):
        super().__init__()
        self.source = source
        self.target = target
        self.branch = branch
        self.data = data or {}

        pen = QPen(QColor("#555555"), 2)
        self.setPen(pen)
        self.setZValue(0)

        self.arrow_head = QGraphicsPolygonItem()
        self.arrow_head.setBrush(QColor("#555555"))
        self.arrow_head.setZValue(0)

        source.edges.append(self)
        target.edges.append(self)

        self.update_path()

    def update_path(self) -> None:
        start = self.source.output_port.scene_pos()
        end = self.target.input_port.scene_pos()
        self.setLine(start.x(), start.y(), end.x(), end.y())
        self._update_arrow_head(start, end)

    def _update_arrow_head(self, start: QPointF, end: QPointF) -> None:
        angle = math.atan2(end.y() - start.y(), end.x() - start.x())
        p1 = end
        p2 = QPointF(
            end.x() - ARROW_SIZE * math.cos(angle - math.pi / 6),
            end.y() - ARROW_SIZE * math.sin(angle - math.pi / 6),
        )
        p3 = QPointF(
            end.x() - ARROW_SIZE * math.cos(angle + math.pi / 6),
            end.y() - ARROW_SIZE * math.sin(angle + math.pi / 6),
        )
        self.arrow_head.setPolygon(QPolygonF([p1, p2, p3]))

    def graphics_items(self) -> list:
        """All QGraphicsItems making up this edge (for adding/removing from scene)."""
        return [self, self.arrow_head]

    def to_dict(self) -> dict:
        edge = {"from": self.source.node_id, "to": self.target.node_id}
        data = dict(self.data)
        if self.branch:
            data["branch"] = self.branch
        if data:
            edge["data"] = data
        return edge
