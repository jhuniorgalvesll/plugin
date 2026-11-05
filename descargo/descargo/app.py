"""Punto de entrada de la aplicación de escritorio."""

from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog

from . import APP_ID, APP_NAME, APP_VERSION, COPYRIGHT_OWNER
from .config import Settings
from .core.library import Library
from .utils import IS_WINDOWS, app_data_dir


def diagnostics() -> str:
    """«DescarGO --diagnostico»: muestra qué componentes del motor están disponibles."""
    from .core import updater
    lines = [f"{APP_NAME} {APP_VERSION}",
             f"Motor: {updater.current_engine_version()} ({updater.engine_source()})"]
    try:
        import curl_cffi
        lines.append(f"curl_cffi: {curl_cffi.__version__}")
    except Exception as exc:
        lines.append(f"curl_cffi: NO DISPONIBLE ({exc})")
    try:
        import yt_dlp
        with yt_dlp.YoutubeDL({"quiet": True}) as ydl:
            targets = list(ydl._get_available_impersonate_targets())
        lines.append(f"Navegadores simulables: {len(targets)}")
    except Exception as exc:
        lines.append(f"Navegadores simulables: error ({exc})")
    return "\n".join(lines)


def main() -> int:
    # Usa el motor de descarga actualizado (si existe) antes de cualquier import de yt_dlp.
    from .core.updater import activate_engine
    activate_engine()
    if "--diagnostico" in sys.argv:
        report = diagnostics()
        print(report)
        try:
            (app_data_dir() / "diagnostico.txt").write_text(report, encoding="utf-8")
        except OSError:
            pass
        return 0

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
