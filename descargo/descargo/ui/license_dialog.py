"""Ventanas de licencia: activar (usuarios) y generar (solo el autor)."""

from __future__ import annotations

from datetime import date, timedelta

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import (QComboBox, QDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
                               QMessageBox, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget)

from .. import APP_NAME, AUTHOR_HANDLE, AUTHOR_INSTAGRAM, YAPE_NUMBER_DISPLAY
from ..core.licensing import (FREE_DAILY_LIMIT, LicenseError, LicenseManager, create_license,
                              machine_code)


def _label(text: str, muted: bool = False) -> QLabel:
    lbl = QLabel(text)
    lbl.setWordWrap(True)
    lbl.setTextFormat(Qt.RichText)
    lbl.setOpenExternalLinks(True)
    if muted:
        lbl.setProperty("muted", True)
    return lbl


class LicenseDialog(QDialog):
    def __init__(self, manager: LicenseManager, parent: QWidget | None = None, limit_reached: bool = False):
        super().__init__(parent)
        self.manager = manager
        self.setWindowTitle(f"Licencia — {APP_NAME}")
        self.setFixedWidth(560)
        root = QVBoxLayout(self)
        root.setContentsMargins(26, 22, 26, 20)
        root.setSpacing(14)

        title = QLabel("🔑  Licencia de DescarGO")
        title.setObjectName("DialogTitle")
        root.addWidget(title)

        if limit_reached:
            warn = QFrame()
            warn.setObjectName("NoticeCard")
            w_lay = QVBoxLayout(warn)
            w_lay.setContentsMargins(14, 10, 14, 10)
            w_lay.addWidget(_label(
                f"⏳ <b>Llegaste al límite gratuito de {FREE_DAILY_LIMIT} descargas de hoy.</b><br>"
                "Mañana se renueva, o activa una licencia para descargar sin límites."))
            root.addWidget(warn)

        # Estado actual
        self.status = _label("")
        root.addWidget(self.status)

        # Código de equipo
        code_card = QFrame()
        code_card.setObjectName("Card")
        c_lay = QVBoxLayout(code_card)
        c_lay.setContentsMargins(16, 14, 16, 14)
        c_lay.addWidget(_label("Tu <b>código de equipo</b> (envíalo para recibir tu licencia):", muted=True))
        row = QHBoxLayout()
        code = QLabel(machine_code())
        code.setStyleSheet("font-size: 17pt; font-weight: 800; letter-spacing: 1px;")
        code.setTextInteractionFlags(Qt.TextSelectableByMouse)
        row.addWidget(code, 1)
        self.btn_copy = QPushButton("📋 Copiar")
        self.btn_copy.clicked.connect(self._copy_code)
        row.addWidget(self.btn_copy)
        c_lay.addLayout(row)
        root.addWidget(code_card)

        # Cómo comprar
        self.how = _label(
            "<b>¿Cómo obtener tu licencia?</b><br>"
            f"1. Yapea al <b>{YAPE_NUMBER_DISPLAY}</b>.<br>"
            f'2. Envía la captura del pago y tu código de equipo por Instagram a '
            f'<a href="{AUTHOR_INSTAGRAM}">{AUTHOR_HANDLE}</a>.<br>'
            "3. Recibirás tu licencia: pégala abajo y presiona «Activar».", muted=True)
        root.addWidget(self.how)

        # Activar
        self.key_input = QPlainTextEdit()
        self.key_input.setPlaceholderText("Pega aquí tu licencia (empieza con DGO1-)…")
        self.key_input.setFixedHeight(80)
        root.addWidget(self.key_input)

        buttons = QHBoxLayout()
        insta = QPushButton(f"📷  Escribir a {AUTHOR_HANDLE}")
        insta.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(AUTHOR_INSTAGRAM)))
        buttons.addWidget(insta)
        buttons.addStretch(1)
        self.btn_remove = QPushButton("Quitar licencia")
        self.btn_remove.setObjectName("Ghost")
        self.btn_remove.clicked.connect(self._deactivate)
        buttons.addWidget(self.btn_remove)
        close = QPushButton("Cerrar")
        close.clicked.connect(self.accept)
        buttons.addWidget(close)
        self.btn_activate = QPushButton("Activar")
        self.btn_activate.setObjectName("Primary")
        self.btn_activate.clicked.connect(self._activate)
        buttons.addWidget(self.btn_activate)
        root.addLayout(buttons)
        self._refresh()

    def _refresh(self) -> None:
        m = self.manager
        if m.is_author:
            self.status.setText("👑 <b>Modo autor</b> — este computador tiene tu llave de licencias.<br>"
                                "Descargas ilimitadas y acceso al generador de licencias.")
            for w in (self.key_input, self.how, self.btn_activate, self.btn_remove):
                w.hide()
            return
        if m.licensed:
            self.status.setText(f"✅ <b>Licencia activa</b> — {m.license.summary}<br>"
                                "Descargas ilimitadas. ¡Gracias por tu apoyo! 💜")
            self.key_input.hide()
            self.how.hide()
            self.btn_activate.hide()
            self.btn_remove.show()
        else:
            left = m.remaining_today()
            self.status.setText(f"Plan gratuito: <b>{left} de {FREE_DAILY_LIMIT}</b> descargas disponibles hoy.")
            self.key_input.show()
            self.how.show()
            self.btn_activate.show()
            self.btn_remove.hide()

    def _copy_code(self) -> None:
        QGuiApplication.clipboard().setText(machine_code())
        self.btn_copy.setText("✔ Copiado")
        QTimer.singleShot(2000, lambda: self.btn_copy.setText("📋 Copiar"))

    def _activate(self) -> None:
        try:
            lic = self.manager.activate(self.key_input.toPlainText())
        except LicenseError as exc:
            QMessageBox.warning(self, "No se pudo activar", str(exc))
            return
        QMessageBox.information(self, "Licencia activada", f"¡Listo, {lic.name}! Ya puedes descargar sin límites.")
        self._refresh()

    def _deactivate(self) -> None:
        if QMessageBox.question(self, "Quitar licencia",
                                "¿Quitar la licencia de este equipo? Podrás volver a activarla "
                                "pegando la misma clave.") == QMessageBox.Yes:
            self.manager.deactivate()
            self._refresh()


class LicenseGeneratorDialog(QDialog):
    """Solo aparece si la llave privada del autor está en la carpeta de datos."""

    DURATIONS = [("Permanente", None), ("1 mes", 31), ("3 meses", 92), ("6 meses", 183), ("1 año", 366)]

    def __init__(self, private_key: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.private_key = private_key
        self.setWindowTitle("Generador de licencias — solo autor")
        self.setFixedWidth(560)
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 20)
        root.setSpacing(10)
        title = QLabel("🛠  Generador de licencias")
        title.setObjectName("DialogTitle")
        root.addWidget(title)
        root.addWidget(_label("Solo visible en tu computador porque tiene tu llave privada. "
                              "Nunca compartas ese archivo.", muted=True))
        root.addWidget(QLabel("Nombre del cliente"))
        self.name = QLineEdit()
        self.name.setPlaceholderText("Ej.: María Quispe")
        root.addWidget(self.name)
        root.addWidget(QLabel("Código de equipo del cliente"))
        self.machine = QLineEdit()
        self.machine.setPlaceholderText("Ej.: 7F3A-91C2-0BDE-44A8")
        root.addWidget(self.machine)
        root.addWidget(QLabel("Duración"))
        self.duration = QComboBox()
        for text, days in self.DURATIONS:
            self.duration.addItem(text, days)
        root.addWidget(self.duration)
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setFixedHeight(90)
        self.output.setPlaceholderText("Aquí aparecerá la licencia para enviar al cliente.")
        root.addWidget(self.output)
        row = QHBoxLayout()
        row.addStretch(1)
        self.btn_copy = QPushButton("📋 Copiar licencia")
        self.btn_copy.clicked.connect(lambda: QGuiApplication.clipboard().setText(self.output.toPlainText()))
        gen = QPushButton("Generar")
        gen.setObjectName("Primary")
        gen.clicked.connect(self._generate)
        close = QPushButton("Cerrar")
        close.clicked.connect(self.accept)
        row.addWidget(close)
        row.addWidget(self.btn_copy)
        row.addWidget(gen)
        root.addLayout(row)

    def _generate(self) -> None:
        days = self.duration.currentData()
        expires = (date.today() + timedelta(days=days)).isoformat() if days else None
        try:
            key = create_license(self.private_key, self.name.text(), self.machine.text(), expires)
        except Exception as exc:
            QMessageBox.warning(self, "No se pudo generar", str(exc))
            return
        self.output.setPlainText(key)
