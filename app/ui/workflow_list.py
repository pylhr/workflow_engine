"""Widget listing existing workflows, with actions to create, edit (open in
designer), publish, and start (run) a workflow.
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QPushButton,
    QInputDialog,
    QMessageBox,
    QHeaderView,
)

from app.services import workflow_service, execution_service
from app.auth.auth_service import require_role


class WorkflowListWidget(QWidget):
    """Shows all workflows. Emits nothing directly; uses callbacks passed in
    from MainWindow to open the designer for a given workflow.
    """

    def __init__(self, current_user: dict, open_designer_callback, parent=None):
        super().__init__(parent)
        self.current_user = current_user
        self.open_designer_callback = open_designer_callback

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Name", "Description", "Published?", "Versions"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)

        new_button = QPushButton("New Workflow")
        new_button.clicked.connect(self._on_new_workflow)

        edit_button = QPushButton("Open in Designer")
        edit_button.clicked.connect(self._on_edit_workflow)

        run_button = QPushButton("Run Now")
        run_button.clicked.connect(self._on_run_workflow)

        refresh_button = QPushButton("Refresh")
        refresh_button.clicked.connect(self.refresh)

        button_row = QHBoxLayout()
        button_row.addWidget(new_button)
        button_row.addWidget(edit_button)
        button_row.addWidget(run_button)
        button_row.addWidget(refresh_button)
        button_row.addStretch()

        layout = QVBoxLayout(self)
        layout.addLayout(button_row)
        layout.addWidget(self.table)

        self._workflows: list[dict] = []
        self.refresh()

    def refresh(self) -> None:
        self._workflows = workflow_service.list_workflows()
        self.table.setRowCount(len(self._workflows))
        for row, wf in enumerate(self._workflows):
            self.table.setItem(row, 0, QTableWidgetItem(wf["name"]))
            self.table.setItem(row, 1, QTableWidgetItem(wf["description"]))
            published = "Yes" if wf["published_version_id"] else "No (draft only)"
            self.table.setItem(row, 2, QTableWidgetItem(published))
            self.table.setItem(row, 3, QTableWidgetItem(str(wf["version_count"])))

    def _selected_workflow(self) -> dict | None:
        row = self.table.currentRow()
        if row < 0 or row >= len(self._workflows):
            return None
        return self._workflows[row]

    def _on_new_workflow(self) -> None:
        name, ok = QInputDialog.getText(self, "New Workflow", "Workflow name:")
        if not ok or not name.strip():
            return
        workflow_service.create_workflow(
            name=name.strip(), description="", created_by_id=self.current_user["id"]
        )
        self.refresh()

    def _on_edit_workflow(self) -> None:
        workflow = self._selected_workflow()
        if workflow is None:
            QMessageBox.information(self, "No selection", "Select a workflow first.")
            return
        self.open_designer_callback(workflow["id"], workflow["name"])

    def _on_run_workflow(self) -> None:
        workflow = self._selected_workflow()
        if workflow is None:
            QMessageBox.information(self, "No selection", "Select a workflow first.")
            return
        if not workflow["published_version_id"]:
            QMessageBox.warning(
                self, "Not Published",
                "This workflow has no published version yet. "
                "Open it in the designer and click Publish first.",
            )
            return
        try:
            execution_id = execution_service.start_execution(
                workflow_id=workflow["id"], started_by_id=self.current_user["id"]
            )
            QMessageBox.information(self, "Started", f"Started execution #{execution_id}.")
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))
