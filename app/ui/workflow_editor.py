"""Wraps the WorkflowDesignerWidget canvas with Save Draft / Publish controls
for a specific workflow.
"""

from __future__ import annotations

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QMessageBox

from app.ui.designer.canvas import WorkflowDesignerWidget
from app.services import workflow_service
from app.core.graph import WorkflowGraph, GraphValidationError


class WorkflowEditorWidget(QWidget):
    def __init__(self, workflow_id: int, workflow_name: str, current_user: dict, parent=None):
        super().__init__(parent)
        self.workflow_id = workflow_id
        self.current_user = current_user

        self.canvas = WorkflowDesignerWidget(self)
        self.canvas.load_definition(workflow_service.get_workflow_definition(workflow_id))

        save_button = QPushButton("Save Draft")
        save_button.clicked.connect(self._on_save_draft)

        publish_button = QPushButton("Publish")
        publish_button.clicked.connect(self._on_publish)

        button_row = QHBoxLayout()
        button_row.addWidget(QLabel(f"<b>Editing: {workflow_name}</b>"))
        button_row.addStretch()
        button_row.addWidget(save_button)
        button_row.addWidget(publish_button)

        layout = QVBoxLayout(self)
        layout.addLayout(button_row)
        layout.addWidget(self.canvas)

        self._last_saved_version_id: int | None = None

    def _on_save_draft(self) -> None:
        definition = self.canvas.to_definition()
        try:
            self._last_saved_version_id = workflow_service.save_draft_version(
                self.workflow_id, definition, edited_by_id=self.current_user["id"]
            )
            QMessageBox.information(self, "Saved", "Draft version saved.")
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))

    def _on_publish(self) -> None:
        definition = self.canvas.to_definition()

        try:
            WorkflowGraph(definition).validate()
        except GraphValidationError as exc:
            QMessageBox.warning(self, "Invalid Workflow", str(exc))
            return

        try:
            version_id = workflow_service.save_draft_version(
                self.workflow_id, definition, edited_by_id=self.current_user["id"]
            )
            workflow_service.publish_version(
                self.workflow_id, version_id, published_by_id=self.current_user["id"]
            )
            QMessageBox.information(self, "Published", "Workflow published successfully.")
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))
