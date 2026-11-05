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
    # Usa el motor de descarga actualizado (si existe) antes de cualquier import de yt_dlp.
    from .core.updater import activate_engine
    activate_engine()

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

    from .ui.dialogs import TermsDialog, WhatsNewDialog
    from .ui.main_window import MainWindow
    from .ui.theme import build_stylesheet
    from .ui.widgets import app_icon

    settings = Settings.load()
    app.setStyleSheet(build_stylesheet(settings.theme))
    app.setWindowIcon(app_icon())

    first_run = not settings.accepted_terms
    if first_run:
        if TermsDialog().exec() != QDialog.Accepted:
            return 0
        settings.accepted_terms = True

    window = MainWindow(settings, Library())
    window.show()
    if settings.last_seen_version != APP_VERSION:
        if not first_run:
            WhatsNewDialog(window).exec()
        settings.last_seen_version = APP_VERSION
    settings.save()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
