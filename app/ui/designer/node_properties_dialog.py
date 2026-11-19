"""Property editor dialog for workflow nodes.

Opened by double-clicking a node on the designer canvas. Shows different
fields depending on `node.node_type`, and writes results back into
`node.data` (the dict that gets serialized into the workflow JSON).
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog,
    QFormLayout,
    QVBoxLayout,
    QLineEdit,
    QComboBox,
    QSpinBox,
    QTextEdit,
    QPushButton,
    QHBoxLayout,
    QLabel,
)


# Roles available for approval-node / notification-node assignment.
# Mirrors the seeded roles in app/database.py (_seed_default_data).
ROLE_CHOICES = ["Admin", "Manager", "Employee"]

DELAY_UNITS = ["minutes", "hours", "days"]


class NodePropertiesDialog(QDialog):
    """Type-aware form for editing a single node's `data` dict."""

    def __init__(self, node_type: str, data: dict, parent=None):
        super().__init__(parent)
        self.node_type = node_type
        self.data = dict(data)  # working copy; only written back on Save
        self._fields: dict[str, object] = {}

        self.setWindowTitle(f"Edit {node_type.title()} Node")
        self.setMinimumWidth(380)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        builder = getattr(self, f"_build_{node_type}_fields", self._build_generic_fields)
        builder(form)

        layout.addLayout(form)
        layout.addLayout(self._build_buttons())

    # ------------------------------------------------------------------
    # Per-node-type field builders
    # ------------------------------------------------------------------
    def _build_start_fields(self, form: QFormLayout) -> None:
        form.addRow(QLabel("Start node has no configurable settings."))

    def _build_end_fields(self, form: QFormLayout) -> None:
        form.addRow(QLabel("End node has no configurable settings."))

    def _build_approval_fields(self, form: QFormLayout) -> None:
        role_box = QComboBox()
        role_box.addItems(ROLE_CHOICES)
        current_role = self.data.get("assigned_role", "Manager")
        if current_role in ROLE_CHOICES:
            role_box.setCurrentText(current_role)
        form.addRow("Assigned role:", role_box)
        self._fields["assigned_role"] = role_box

        note = QLabel(
            "Any user with this role will see the request in their\n"
            "Dashboard → Pending Approvals tab."
        )
        note.setStyleSheet("color: #666;")
        form.addRow(note)

    def _build_condition_fields(self, form: QFormLayout) -> None:
        expr_input = QLineEdit(self.data.get("condition", ""))
        expr_input.setPlaceholderText("e.g. amount > 10000")
        form.addRow("Condition expression:", expr_input)
        self._fields["condition"] = expr_input

        note = QLabel(
            "Written as a Python expression evaluated against the\n"
            "execution's context (the data passed in when the workflow\n"
            "was started, plus anything set by earlier Script nodes).\n"
            "Connect the 'true' branch edge and 'false' branch edge\n"
            "separately by dragging from this node — you'll be asked\n"
            "which branch each edge represents."
        )
        note.setStyleSheet("color: #666;")
        form.addRow(note)

    def _build_delay_fields(self, form: QFormLayout) -> None:
        existing_delay = self.data.get("delay", {"hours": 1})
        existing_unit = next(iter(existing_delay), "hours")
        existing_amount = existing_delay.get(existing_unit, 1)

        amount_box = QSpinBox()
        amount_box.setRange(1, 100000)
        amount_box.setValue(existing_amount)
        form.addRow("Wait amount:", amount_box)
        self._fields["delay_amount"] = amount_box

        unit_box = QComboBox()
        unit_box.addItems(DELAY_UNITS)
        if existing_unit in DELAY_UNITS:
            unit_box.setCurrentText(existing_unit)
        form.addRow("Wait unit:", unit_box)
        self._fields["delay_unit"] = unit_box

    def _build_notification_fields(self, form: QFormLayout) -> None:
        title_input = QLineEdit(self.data.get("title", "Workflow Notification"))
        form.addRow("Title:", title_input)
        self._fields["title"] = title_input

        message_input = QTextEdit(self.data.get("message", ""))
        message_input.setPlaceholderText(
            "e.g. Request for {requester} needs review.\n"
            "Use {key} to insert values from the execution context."
        )
        message_input.setFixedHeight(70)
        form.addRow("Message:", message_input)
        self._fields["message"] = message_input

        role_box = QComboBox()
        role_box.addItems(["(none)"] + ROLE_CHOICES)
        current_role = self.data.get("role") or "(none)"
        if current_role in ROLE_CHOICES:
            role_box.setCurrentText(current_role)
        form.addRow("Notify role:", role_box)
        self._fields["role"] = role_box

    def _build_webhook_fields(self, form: QFormLayout) -> None:
        url_input = QLineEdit(self.data.get("url", ""))
        url_input.setPlaceholderText("https://example.com/api/endpoint")
        form.addRow("URL:", url_input)
        self._fields["url"] = url_input

        method_box = QComboBox()
        method_box.addItems(["POST", "GET", "PUT", "PATCH", "DELETE"])
        current_method = self.data.get("method", "POST")
        if current_method in ["POST", "GET", "PUT", "PATCH", "DELETE"]:
            method_box.setCurrentText(current_method)
        form.addRow("Method:", method_box)
        self._fields["method"] = method_box

        note = QLabel(
            "Note: the webhook HTTP call itself is not yet implemented\n"
            "in the execution engine (see WebhookNode TODO) — this\n"
            "just records the configuration for now."
        )
        note.setStyleSheet("color: #b00;")
        form.addRow(note)

    def _build_script_fields(self, form: QFormLayout) -> None:
        script_input = QLineEdit(self.data.get("script", ""))
        script_input.setPlaceholderText("e.g. amount * 0.1")
        form.addRow("Expression:", script_input)
        self._fields["script"] = script_input

        output_input = QLineEdit(self.data.get("output_key", "result"))
        form.addRow("Store result as:", output_input)
        self._fields["output_key"] = output_input

        note = QLabel(
            "A Python expression evaluated against the execution context.\n"
            "The result is saved under 'Store result as' and becomes\n"
            "available to later nodes (e.g. in a Condition expression)."
        )
        note.setStyleSheet("color: #666;")
        form.addRow(note)

    def _build_generic_fields(self, form: QFormLayout) -> None:
        form.addRow(QLabel("No editable settings for this node type."))

    # ------------------------------------------------------------------
    def _build_buttons(self) -> QHBoxLayout:
        row = QHBoxLayout()
        save_button = QPushButton("Save")
        save_button.clicked.connect(self._on_save)
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        row.addStretch()
        row.addWidget(cancel_button)
        row.addWidget(save_button)
        return row

    def _on_save(self) -> None:
        if self.node_type == "approval":
            self.data["assigned_role"] = self._fields["assigned_role"].currentText()

        elif self.node_type == "condition":
            self.data["condition"] = self._fields["condition"].text().strip()

        elif self.node_type == "delay":
            amount = self._fields["delay_amount"].value()
            unit = self._fields["delay_unit"].currentText()
            self.data["delay"] = {unit: amount}

        elif self.node_type == "notification":
            self.data["title"] = self._fields["title"].text().strip()
            self.data["message"] = self._fields["message"].toPlainText().strip()
            role = self._fields["role"].currentText()
            self.data["role"] = None if role == "(none)" else role

        elif self.node_type == "webhook":
            self.data["url"] = self._fields["url"].text().strip()
            self.data["method"] = self._fields["method"].currentText()

        elif self.node_type == "script":
            self.data["script"] = self._fields["script"].text().strip()
            self.data["output_key"] = self._fields["output_key"].text().strip() or "result"

        self.accept()

    def result_data(self) -> dict:
        return self.data
