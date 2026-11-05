"""Punto de entrada de la aplicación de escritorio."""

from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog

from . import APP_ID, APP_NAME, APP_VERSION, COPYRIGHT_OWNER
from .config import Settings
from .core.library import Library
from .utils import IS_WINDOWS


def main() -> int:
    if IS_WINDOWS:
        # Icono propio en la barra de tareas de Windows.
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
        except Exception:
            pass

    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName(COPYRIGHT_OWNER)
    app.setStyle("Fusion")

    from .ui.dialogs import TermsDialog
    from .ui.main_window import MainWindow
    from .ui.theme import STYLESHEET
    from .ui.widgets import app_icon

    app.setStyleSheet(STYLESHEET)
    app.setWindowIcon(app_icon())

    settings = Settings.load()
    if not settings.accepted_terms:
        if TermsDialog().exec() != QDialog.Accepted:
            return 0
        settings.accepted_terms = True
        settings.save()

    window = MainWindow(settings, Library())
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
