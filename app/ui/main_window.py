"""Main application window.

Holds the logged-in user for the session, and provides a tabbed
navigation: Dashboard, Workflows (list), dynamically-opened Workflow
Editor tabs, and (Admin only) an Audit Log tab.
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QMainWindow,
    QTabWidget,
    QWidget,
    QVBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QPushButton,
    QHeaderView,
    QLabel,
)
from PyQt6.QtCore import QTimer

from app.ui.dashboard import DashboardWidget
from app.ui.workflow_list import WorkflowListWidget
from app.ui.workflow_editor import WorkflowEditorWidget
from app.services import audit_service


class AuditLogWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Timestamp", "User ID", "Action", "Metadata"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        refresh_button = QPushButton("Refresh")
        refresh_button.clicked.connect(self.refresh)

        layout.addWidget(refresh_button)
        layout.addWidget(self.table)
        self.refresh()

    def refresh(self) -> None:
        entries = audit_service.list_recent(limit=200)
        self.table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            self.table.setItem(row, 0, QTableWidgetItem(entry["timestamp"]))
            self.table.setItem(row, 1, QTableWidgetItem(str(entry["user_id"])))
            self.table.setItem(row, 2, QTableWidgetItem(entry["action"]))
            self.table.setItem(row, 3, QTableWidgetItem(str(entry["metadata"])))


class MainWindow(QMainWindow):
    def __init__(self, current_user: dict):
        super().__init__()
        self.current_user = current_user

        self.setWindowTitle(
            f"Workflow Automation Engine — {current_user['full_name'] or current_user['username']} "
            f"({current_user['role']})"
        )
        self.resize(1200, 800)

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.dashboard = DashboardWidget(current_user)
        self.workflow_list = WorkflowListWidget(current_user, self.open_workflow_editor)

        self.tabs.addTab(self.dashboard, "Dashboard")
        self.tabs.addTab(self.workflow_list, "Workflows")

        if current_user.get("role") == "Admin":
            self.audit_log = AuditLogWidget()
            self.tabs.addTab(self.audit_log, "Audit Log")

        # Periodically refresh the dashboard so delay/approval-driven
        # status changes (which may happen via the scheduler thread)
        # show up without manual interaction.
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._refresh_dashboard)
        self._refresh_timer.start(5000)

    def _refresh_dashboard(self) -> None:
        self.dashboard.refresh()

    def open_workflow_editor(self, workflow_id: int, workflow_name: str) -> None:
        """Open (or focus) a designer tab for the given workflow."""
        tab_title = f"Edit: {workflow_name}"

        for i in range(self.tabs.count()):
            widget = self.tabs.widget(i)
            if isinstance(widget, WorkflowEditorWidget) and widget.workflow_id == workflow_id:
                self.tabs.setCurrentIndex(i)
                return

        editor = WorkflowEditorWidget(workflow_id, workflow_name, self.current_user)
        index = self.tabs.addTab(editor, tab_title)
        self.tabs.setCurrentIndex(index)
