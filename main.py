"""Application entry point.

Initializes the database (creating tables + seeding the default admin
user on first run), starts the in-process scheduler, shows the login
dialog, and then opens the main window for the authenticated user.
"""

import sys

from PyQt6.QtWidgets import QApplication

from app.database import init_db
from app.core.scheduler import scheduler_service
from app.ui.login_dialog import LoginDialog
from app.ui.main_window import MainWindow


def main() -> int:
    init_db()
    scheduler_service.start()

    app = QApplication(sys.argv)

    login = LoginDialog()
    if login.exec() != LoginDialog.DialogCode.Accepted or login.authenticated_user is None:
        return 0

    window = MainWindow(login.authenticated_user)
    window.show()

    exit_code = app.exec()
    scheduler_service.shutdown()
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
