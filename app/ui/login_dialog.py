"""Simple username/password login dialog."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog,
    QFormLayout,
    QLineEdit,
    QPushButton,
    QLabel,
    QVBoxLayout,
    QMessageBox,
)

from app.auth.auth_service import authenticate, AuthError


class LoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Workflow Automation Engine - Login")
        self.setMinimumWidth(320)

        self.authenticated_user: dict | None = None

        self.username_input = QLineEdit()
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)

        form = QFormLayout()
        form.addRow("Username:", self.username_input)
        form.addRow("Password:", self.password_input)

        login_button = QPushButton("Log In")
        login_button.clicked.connect(self._on_login)
        self.password_input.returnPressed.connect(self._on_login)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<b>Workflow Automation Engine</b>"))
        layout.addLayout(form)
        layout.addWidget(login_button)
        layout.addWidget(QLabel(
            "Default admin login: admin / admin123 (change this in a real deployment)"
        ))

    def _on_login(self) -> None:
        username = self.username_input.text().strip()
        password = self.password_input.text()
        try:
            self.authenticated_user = authenticate(username, password)
            self.accept()
        except AuthError as exc:
            QMessageBox.warning(self, "Login Failed", str(exc))
