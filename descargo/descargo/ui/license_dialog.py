"""Ventanas de licencia: activar (usuarios) y generar (solo el autor)."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import QDate, Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QDateEdit, QDialog, QFileDialog,
                               QFormLayout, QFrame, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
                               QMessageBox, QPlainTextEdit, QPushButton, QTableWidget,
                               QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget)

from .. import APP_NAME, AUTHOR_HANDLE, AUTHOR_INSTAGRAM, YAPE_NUMBER_DISPLAY
from ..core.licensing import (FREE_DAILY_LIMIT, LicenseError, LicenseManager, add_months,
                              create_license, machine_code)


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

        self.btn_author = QPushButton("👑  Soy el autor: cargar mi llave de licencias…")
        self.btn_author.setObjectName("Ghost")
        self.btn_author.clicked.connect(self._load_author_key)
        root.addWidget(self.btn_author, 0, Qt.AlignLeft)

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
            for w in (self.key_input, self.how, self.btn_activate, self.btn_remove, self.btn_author):
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

    def _load_author_key(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Selecciona tu llave de licencias", "",
                                              "Llave de licencias (*.key);;Todos los archivos (*)")
        if not path:
            return
        if self.manager.install_author_key(path):
            QMessageBox.information(self, "Modo autor activado",
                                    "👑 ¡Listo! Este computador ahora es el del autor:\n"
                                    "descargas ilimitadas y menú «Generar licencias» en la barra lateral.")
            self._refresh()
        else:
            QMessageBox.warning(self, "Llave no válida",
                                "Ese archivo no es la llave de licencias de DescarGO.")

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
    """Menú del autor: crear licencias y ver las emitidas. Solo con la llave real."""

    def __init__(self, manager: LicenseManager, parent: QWidget | None = None):
        super().__init__(parent)
        self.manager = manager
        self.private_key = manager.private_key() or ""
        self.setWindowTitle("Generador de licencias — Autor")
        self.setMinimumWidth(640)
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 20)
        root.setSpacing(12)
        title = QLabel("🛠  Generador de licencias")
        title.setObjectName("DialogTitle")
        root.addWidget(title)
        root.addWidget(_label("👑 Modo autor: solo tu computador ve este menú porque tiene tu llave real.",
                              muted=True))
        tabs = QTabWidget()
        tabs.addTab(self._new_tab(), "➕  Nueva licencia")
        tabs.addTab(self._history_tab(), "📋  Licencias emitidas")
        tabs.currentChanged.connect(lambda i: i == 1 and self._load_history())
        root.addWidget(tabs, 1)
        close = QPushButton("Cerrar")
        close.clicked.connect(self.accept)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(close)
        root.addLayout(row)

    # -- nueva licencia ----------------------------------------------------------
    def _new_tab(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        form.setContentsMargins(6, 16, 6, 6)
        form.setVerticalSpacing(10)
        self.name = QLineEdit()
        self.name.setPlaceholderText("Ej.: María Quispe")
        form.addRow("Nombre del cliente", self.name)
        self.machine = QLineEdit()
        self.machine.setPlaceholderText("Ej.: D5FF-BDC4-9F8A-8595")
        form.addRow("Código de equipo", self.machine)

        self.duration = QComboBox()
        self.duration.addItem("Permanente (no vence)", ("perm", 0))
        for m in range(1, 13):
            self.duration.addItem(f"{m} mes" + ("es" if m > 1 else ""), ("months", m))
        self.duration.addItem("2 años", ("months", 24))
        self.duration.addItem("Fecha personalizada…", ("date", 0))
        self.duration.setCurrentIndex(5)  # 5 meses
        form.addRow("Duración", self.duration)
        self.custom_date = QDateEdit(QDate.currentDate().addMonths(5))
        self.custom_date.setCalendarPopup(True)
        self.custom_date.setDisplayFormat("dd/MM/yyyy")
        self.custom_date.setMinimumDate(QDate.currentDate().addDays(1))
        form.addRow("Vence el", self.custom_date)
        self.expiry_label = _label("", muted=True)
        form.addRow("", self.expiry_label)

        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setFixedHeight(90)
        self.output.setPlaceholderText("Aquí aparecerá la licencia para enviar al cliente.")
        form.addRow("Licencia", self.output)
        row = QHBoxLayout()
        row.addStretch(1)
        self.btn_copy = QPushButton("📋 Copiar licencia")
        self.btn_copy.setEnabled(False)
        self.btn_copy.clicked.connect(self._copy)
        gen = QPushButton("Generar licencia")
        gen.setObjectName("Primary")
        gen.clicked.connect(self._generate)
        row.addWidget(self.btn_copy)
        row.addWidget(gen)
        form.addRow("", row)

        self.duration.currentIndexChanged.connect(self._update_expiry)
        self.custom_date.dateChanged.connect(self._update_expiry)
        self._update_expiry()
        return page

    def _expiry(self) -> date | None:
        kind, months = self.duration.currentData()
        if kind == "perm":
            return None
        if kind == "months":
            return add_months(date.today(), months)
        return self.custom_date.date().toPython()

    def _update_expiry(self) -> None:
        kind, _ = self.duration.currentData()
        self.custom_date.setEnabled(kind == "date")
        exp = self._expiry()
        self.expiry_label.setText("Sin vencimiento." if exp is None
                                  else f"La licencia vencerá el <b>{exp.strftime('%d/%m/%Y')}</b>.")

    def _generate(self) -> None:
        exp = self._expiry()
        expires = exp.isoformat() if exp else None
        name = self.name.text().strip() or "Usuario"
        try:
            key = create_license(self.private_key, name, self.machine.text(), expires)
        except Exception as exc:
            QMessageBox.warning(self, "No se pudo generar", str(exc))
            return
        self.output.setPlainText(key)
        self.btn_copy.setEnabled(True)
        self.manager.log_issued(name, self.machine.text().strip().upper(), expires, key)

    def _copy(self) -> None:
        QGuiApplication.clipboard().setText(self.output.toPlainText())
        self.btn_copy.setText("✔ Copiada")
        QTimer.singleShot(2000, lambda: self.btn_copy.setText("📋 Copiar licencia"))

    # -- historial ---------------------------------------------------------------
    def _history_tab(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 12, 0, 0)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Fecha", "Cliente", "Código de equipo", "Vence"])
        self.table.verticalHeader().hide()
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setAlternatingRowColors(True)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        lay.addWidget(self.table, 1)
        row = QHBoxLayout()
        row.addWidget(_label("Selecciona una fila para copiar de nuevo su licencia.", muted=True), 1)
        again = QPushButton("📋 Copiar licencia seleccionada")
        again.clicked.connect(self._copy_selected)
        row.addWidget(again)
        lay.addLayout(row)
        return page

    def _load_history(self) -> None:
        items = self.manager.issued()
        self.table.setRowCount(len(items))
        today = date.today().isoformat()
        for r, it in enumerate(items):
            vence = it.get("vence")
            status = "Permanente" if not vence else (f"{vence} (vencida)" if vence < today else vence)
            for c, value in enumerate([str(it.get("fecha", ""))[:16].replace("T", " "),
                                       it.get("nombre", ""), it.get("equipo", ""), status]):
                cell = QTableWidgetItem(value)
                cell.setData(Qt.UserRole, it.get("licencia", ""))
                self.table.setItem(r, c, cell)

    def _copy_selected(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        QGuiApplication.clipboard().setText(self.table.item(row, 0).data(Qt.UserRole))
        QMessageBox.information(self, "Copiada", "La licencia se copió al portapapeles.")
