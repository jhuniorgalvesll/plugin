"""Centro de actualizaciones: motor de descarga y nuevas versiones de DescarGO."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import QProcess, Qt, QThreadPool, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QApplication, QCheckBox, QDialog, QFrame, QHBoxLayout, QLabel,
                               QMessageBox, QProgressBar, QPushButton, QTextBrowser,
                               QVBoxLayout, QWidget)

from .. import APP_NAME, APP_VERSION
from ..config import Settings
from ..core import updater
from ..utils import IS_WINDOWS, human_size
from .workers import TaskWorker

_pool = QThreadPool()


def restart_app() -> None:
    """Reinicia DescarGO (para usar el motor recién instalado)."""
    if getattr(sys, "frozen", False):
        QProcess.startDetached(sys.executable, sys.argv[1:])
    else:
        QProcess.startDetached(sys.executable, sys.argv)
    for widget in QApplication.topLevelWidgets():
        widget.close()
    QApplication.quit()


# Instalación invisible: sin asistente ni ventanas.
SILENT_INSTALL_ARGS = ["/VERYSILENT", "/SP-", "/NOCANCEL", "/SUPPRESSMSGBOXES", "/NORESTART",
                       "/CLOSEAPPLICATIONS"]


def _ps_quote(text: str) -> str:
    return "'" + str(text).replace("'", "''") + "'"


def build_update_script(installer: str, exe: str, pid: int, local_appdata: str = "") -> str:
    """Script de PowerShell: esperar cierre → instalar sin ventanas → abrir la nueva versión."""
    per_user = bool(local_appdata) and str(exe).lower().startswith(local_appdata.lower())
    args = ",".join(_ps_quote(a) for a in SILENT_INSTALL_ARGS + ["/CURRENTUSER" if per_user else "/ALLUSERS"])
    return "\r\n".join([
        "$ErrorActionPreference = 'SilentlyContinue'",
        f"Wait-Process -Id {int(pid)} -Timeout 60",
        "Start-Sleep -Milliseconds 800",
        f"Start-Process -FilePath {_ps_quote(installer)} -ArgumentList {args} -Wait",
        f"Start-Process -FilePath {_ps_quote(exe)}",
    ])


def run_installer(path: str) -> None:
    """Actualiza en segundo plano y vuelve a abrir DescarGO ya actualizado.

    Un pequeño script (oculto) espera a que esta app termine de cerrarse —así el
    instalador nunca encuentra DescarGO.exe en uso—, instala sin ventanas y abre la
    nueva versión, que muestra «¡Actualizado!».
    """
    if not IS_WINDOWS or not getattr(sys, "frozen", False):
        if not QProcess.startDetached(path, []):
            raise updater.UpdateError("No se pudo abrir el instalador.")
        _quit_all()
        return
    script = build_update_script(path, sys.executable, os.getpid(), os.environ.get("LOCALAPPDATA", ""))
    script_path = Path(path).with_name("actualizar.ps1")
    script_path.write_text(script, encoding="utf-8-sig")
    started = QProcess.startDetached("powershell.exe", [
        "-NoProfile", "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden", "-File", str(script_path)])
    if not started:
        raise updater.UpdateError("No se pudo iniciar la actualización.")
    _quit_all()


def _quit_all() -> None:
    for widget in QApplication.topLevelWidgets():
        widget.close()
    QApplication.quit()


def _start(worker: TaskWorker) -> TaskWorker:
    worker.setAutoDelete(False)
    _pool.start(worker)
    return worker


class _Section(QFrame):
    def __init__(self, icon: str, title: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("Card")
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(18, 16, 18, 16)
        self.lay.setSpacing(8)
        head = QLabel(f"{icon}  {title}")
        head.setObjectName("SectionTitle")
        self.lay.addWidget(head)


class UpdatesDialog(QDialog):
    def __init__(self, settings: Settings, parent: QWidget | None = None,
                 known_update: updater.AppUpdate | None = None):
        super().__init__(parent)
        self.settings = settings
        self.app_update = known_update
        self._workers: list[TaskWorker] = []
        self.setWindowTitle(f"Actualizaciones — {APP_NAME}")
        self.setMinimumWidth(600)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 18)
        root.setSpacing(14)
        title = QLabel("🔄  Actualizaciones")
        title.setObjectName("DialogTitle")
        root.addWidget(title)

        # --- Aplicación ---------------------------------------------------
        app_box = _Section("⬇", f"{APP_NAME}")
        self.app_status = QLabel(f"Versión instalada: <b>{APP_VERSION}</b>")
        self.app_status.setTextFormat(Qt.RichText)
        self.app_status.setWordWrap(True)
        app_box.lay.addWidget(self.app_status)
        self.notes = QTextBrowser()
        self.notes.setOpenExternalLinks(True)
        self.notes.setMinimumHeight(90)
        self.notes.setMaximumHeight(160)
        self.notes.hide()
        app_box.lay.addWidget(self.notes)
        self.app_progress = QProgressBar()
        self.app_progress.setFixedHeight(8)
        self.app_progress.setTextVisible(False)
        self.app_progress.hide()
        app_box.lay.addWidget(self.app_progress)
        row = QHBoxLayout()
        self.btn_check_app = QPushButton("Buscar nueva versión")
        self.btn_check_app.clicked.connect(self.check_app)
        self.btn_install_app = QPushButton("⬇  Descargar e instalar")
        self.btn_install_app.setObjectName("Primary")
        self.btn_install_app.clicked.connect(self.install_app)
        self.btn_install_app.hide()
        row.addWidget(self.btn_check_app)
        row.addStretch(1)
        row.addWidget(self.btn_install_app)
        app_box.lay.addLayout(row)
        self.cb_app = QCheckBox("Avisarme cuando haya una versión nueva")
        self.cb_app.setChecked(settings.check_app_updates)
        app_box.lay.addWidget(self.cb_app)
        root.addWidget(app_box)

        # --- Motor ----------------------------------------------------------
        engine_box = _Section("⚙", "Motor de descarga")
        source = "actualizado" if updater.engine_source() == "actualizado" else "incluido en el instalador"
        self.engine_status = QLabel(
            f"Versión: <b>{updater.current_engine_version()}</b> ({source})")
        self.engine_status.setTextFormat(Qt.RichText)
        engine_box.lay.addWidget(self.engine_status)
        info = QLabel("Las plataformas cambian seguido. Mantener el motor al día evita que "
                      "las descargas dejen de funcionar. Se descarga solo desde el sitio oficial "
                      "y se verifica su huella SHA-256 antes de usarlo.")
        info.setWordWrap(True)
        info.setProperty("muted", True)
        engine_box.lay.addWidget(info)
        self.engine_progress = QProgressBar()
        self.engine_progress.setFixedHeight(8)
        self.engine_progress.setTextVisible(False)
        self.engine_progress.hide()
        engine_box.lay.addWidget(self.engine_progress)
        row2 = QHBoxLayout()
        self.btn_engine = QPushButton("Actualizar motor ahora")
        self.btn_engine.clicked.connect(self.update_engine)
        row2.addWidget(self.btn_engine)
        row2.addStretch(1)
        engine_box.lay.addLayout(row2)
        self.cb_engine = QCheckBox("Actualizar el motor automáticamente (una vez al día)")
        self.cb_engine.setChecked(settings.auto_update_engine)
        engine_box.lay.addWidget(self.cb_engine)
        root.addWidget(engine_box)

        close = QPushButton("Cerrar")
        close.clicked.connect(self.accept)
        bottom = QHBoxLayout()
        bottom.addStretch(1)
        bottom.addWidget(close)
        root.addLayout(bottom)

        if known_update:
            self._show_app_update(known_update)

    # -- aplicación -------------------------------------------------------------
    def check_app(self) -> None:
        self.btn_check_app.setEnabled(False)
        self.app_status.setText("Buscando nuevas versiones…")
        worker = _start(TaskWorker(updater.check_app_update))
        worker.signals.finished.connect(self._app_checked)
        worker.signals.failed.connect(self._app_failed)
        self._workers.append(worker)

    def _app_checked(self, update) -> None:
        self.btn_check_app.setEnabled(True)
        if update is None:
            self.app_status.setText(f"Versión instalada: <b>{APP_VERSION}</b> — ✅ Tienes la última versión.")
            return
        self._show_app_update(update)

    def _show_app_update(self, update: updater.AppUpdate) -> None:
        self.app_update = update
        self.app_status.setText(
            f"🎉 <b>Nueva versión {update.version} disponible</b> (tienes la {APP_VERSION}).")
        self.notes.setMarkdown(update.notes or "Mejoras y correcciones.")
        self.notes.show()
        self.btn_install_app.setText("⬇  Descargar e instalar" if IS_WINDOWS and update.installer_url
                                     else "Abrir página de descarga")
        self.btn_install_app.show()

    def _app_failed(self, message: str) -> None:
        self.btn_check_app.setEnabled(True)
        self.app_status.setText(f"No se pudo comprobar: {message}")

    def install_app(self) -> None:
        update = self.app_update
        if not update:
            return
        if not (IS_WINDOWS and update.installer_url and update.sha256_url):
            QDesktopServices.openUrl(QUrl(update.page_url))
            return
        self.btn_install_app.setEnabled(False)
        self.app_progress.show()
        self.app_progress.setRange(0, 0)
        worker = _start(TaskWorker(updater.download_installer, update, with_progress=True))
        worker.signals.progress.connect(lambda d, t: self._progress(self.app_progress, self.app_status, d, t))
        worker.signals.finished.connect(self._installer_ready)
        worker.signals.failed.connect(self._installer_failed)
        self._workers.append(worker)

    def _installer_ready(self, path) -> None:
        self.app_progress.hide()
        answer = QMessageBox.question(
            self, "Instalar actualización",
            "El instalador se descargó y su huella SHA-256 fue verificada.\n\n"
            f"{APP_NAME} se cerrará unos segundos, se actualizará en segundo plano "
            "(sin ventanas) y se volverá a abrir solo. ¿Continuar?")
        if answer == QMessageBox.Yes:
            try:
                run_installer(str(path))
            except updater.UpdateError as exc:
                QMessageBox.warning(self, "Actualización", str(exc))
        self.btn_install_app.setEnabled(True)

    def _installer_failed(self, message: str) -> None:
        self.app_progress.hide()
        self.btn_install_app.setEnabled(True)
        QMessageBox.warning(self, "No se pudo descargar la actualización", message)

    # -- motor ------------------------------------------------------------------
    def update_engine(self) -> None:
        self.btn_engine.setEnabled(False)
        self.engine_progress.show()
        self.engine_progress.setRange(0, 0)
        self.engine_status.setText("Buscando la última versión del motor…")
        worker = _start(TaskWorker(check_and_install_engine, with_progress=True))
        worker.signals.progress.connect(
            lambda d, t: self._progress(self.engine_progress, self.engine_status, d, t))
        worker.signals.finished.connect(self._engine_done)
        worker.signals.failed.connect(self._engine_failed)
        self._workers.append(worker)

    def _engine_done(self, version) -> None:
        self.engine_progress.hide()
        self.btn_engine.setEnabled(True)
        if not version:
            self.engine_status.setText(
                f"Versión: <b>{updater.current_engine_version()}</b> — ✅ El motor está al día.")
            return
        self.engine_status.setText(f"✅ Motor actualizado a <b>{version}</b>. Se usará al reiniciar.")
        if QMessageBox.question(self, "Motor actualizado",
                                f"El motor se actualizó a la versión {version}.\n"
                                "¿Reiniciar DescarGO ahora para usarlo?") == QMessageBox.Yes:
            restart_app()

    def _engine_failed(self, message: str) -> None:
        self.engine_progress.hide()
        self.btn_engine.setEnabled(True)
        self.engine_status.setText(f"No se pudo actualizar: {message}")

    # -- comunes ----------------------------------------------------------------
    @staticmethod
    def _progress(bar: QProgressBar, label: QLabel, done: int, total: int) -> None:
        if total:
            bar.setRange(0, 1000)
            bar.setValue(int(done / total * 1000))
            label.setText(f"Descargando… {human_size(done)} de {human_size(total)}")
        else:
            bar.setRange(0, 0)
            label.setText(f"Descargando… {human_size(done)}")

    def done(self, result: int) -> None:  # noqa: A003 - guarda las preferencias al cerrar
        self.settings.check_app_updates = self.cb_app.isChecked()
        self.settings.auto_update_engine = self.cb_engine.isChecked()
        self.settings.save()
        super().done(result)


def check_and_install_engine(progress=None) -> str | None:
    """Devuelve la versión instalada, o None si ya estaba al día."""
    update = updater.check_engine_update()
    if update is None:
        return None
    return updater.install_engine(update, progress)
