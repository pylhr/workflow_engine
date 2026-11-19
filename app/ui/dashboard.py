"""Monitoring dashboard: summary stats, recent executions, and (for
Managers/Admins) pending approvals that can be approved/rejected inline.
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QLabel,
    QGridLayout,
    QTableWidget,
    QTableWidgetItem,
    QPushButton,
    QHeaderView,
    QMessageBox,
    QInputDialog,
)

from app.services import execution_service


class DashboardWidget(QWidget):
    def __init__(self, current_user: dict, parent=None):
        super().__init__(parent)
        self.current_user = current_user

        layout = QVBoxLayout(self)
        layout.addWidget(self._build_summary_box())
        layout.addWidget(self._build_executions_box())

        if current_user.get("role") in ("Manager", "Admin"):
            layout.addWidget(self._build_approvals_box())

        refresh_button = QPushButton("Refresh Dashboard")
        refresh_button.clicked.connect(self.refresh)
        layout.addWidget(refresh_button)

        self.refresh()

    # ------------------------------------------------------------------
    def _build_summary_box(self) -> QGroupBox:
        box = QGroupBox("Summary")
        grid = QGridLayout(box)

        self._summary_labels = {}
        fields = [
            ("total", "Total Executions"),
            ("running", "Running"),
            ("waiting", "Waiting"),
            ("completed", "Completed"),
            ("failed", "Failed"),
            ("pending_approvals", "Pending Approvals"),
        ]
        for i, (key, caption) in enumerate(fields):
            value_label = QLabel("0")
            value_label.setStyleSheet("font-size: 20px; font-weight: bold;")
            grid.addWidget(QLabel(caption), 0, i)
            grid.addWidget(value_label, 1, i)
            self._summary_labels[key] = value_label

        return box

    def _build_executions_box(self) -> QGroupBox:
        box = QGroupBox("Recent Executions")
        layout = QVBoxLayout(box)

        self.executions_table = QTableWidget(0, 6)
        self.executions_table.setHorizontalHeaderLabels(
            ["ID", "Workflow", "Status", "Current Node", "Started", "Duration (s)"]
        )
        self.executions_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.executions_table)
        return box

    def _build_approvals_box(self) -> QGroupBox:
        box = QGroupBox("Pending Approvals")
        layout = QVBoxLayout(box)

        self.approvals_table = QTableWidget(0, 4)
        self.approvals_table.setHorizontalHeaderLabels(
            ["Approval ID", "Execution", "Workflow", "Node"]
        )
        self.approvals_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.approvals_table)

        button_row = QHBoxLayout()
        approve_button = QPushButton("Approve Selected")
        approve_button.clicked.connect(lambda: self._decide_selected(True))
        reject_button = QPushButton("Reject Selected")
        reject_button.clicked.connect(lambda: self._decide_selected(False))
        button_row.addWidget(approve_button)
        button_row.addWidget(reject_button)
        button_row.addStretch()
        layout.addLayout(button_row)

        return box

    # ------------------------------------------------------------------
    def refresh(self) -> None:
        summary = execution_service.dashboard_summary()
        for key, label in self._summary_labels.items():
            label.setText(str(summary.get(key, 0)))

        executions = execution_service.list_executions(limit=50)
        self.executions_table.setRowCount(len(executions))
        for row, e in enumerate(executions):
            self.executions_table.setItem(row, 0, QTableWidgetItem(str(e["id"])))
            self.executions_table.setItem(row, 1, QTableWidgetItem(e["workflow_name"]))
            self.executions_table.setItem(row, 2, QTableWidgetItem(e["status"]))
            self.executions_table.setItem(row, 3, QTableWidgetItem(e["current_node_id"] or ""))
            self.executions_table.setItem(row, 4, QTableWidgetItem(e["started_at"]))
            duration = f"{e['duration_seconds']:.1f}" if e["duration_seconds"] is not None else ""
            self.executions_table.setItem(row, 5, QTableWidgetItem(duration))

        if hasattr(self, "approvals_table"):
            role = self.current_user.get("role")
            approvals = execution_service.list_pending_approvals(role_name=role)
            self._pending_approvals = approvals
            self.approvals_table.setRowCount(len(approvals))
            for row, a in enumerate(approvals):
                self.approvals_table.setItem(row, 0, QTableWidgetItem(str(a["id"])))
                self.approvals_table.setItem(row, 1, QTableWidgetItem(str(a["execution_id"])))
                self.approvals_table.setItem(row, 2, QTableWidgetItem(a["workflow_name"]))
                self.approvals_table.setItem(row, 3, QTableWidgetItem(a["node_id"]))

    def _decide_selected(self, approved: bool) -> None:
        row = self.approvals_table.currentRow()
        if row < 0 or row >= len(self._pending_approvals):
            QMessageBox.information(self, "No selection", "Select an approval first.")
            return

        approval = self._pending_approvals[row]
        comment = ""
        if not approved:
            comment, _ok = QInputDialog.getText(self, "Rejection reason", "Comment (optional):")

        try:
            new_status = execution_service.decide_approval(
                approval_id=approval["id"],
                approved=approved,
                decided_by_id=self.current_user["id"],
                comment=comment,
            )
            QMessageBox.information(
                self, "Decision Recorded",
                f"Execution #{approval['execution_id']} is now '{new_status}'.",
            )
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))

        self.refresh()
