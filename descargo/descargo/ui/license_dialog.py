"""Ventanas de licencia: activar (usuarios) y generar (solo el autor)."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import QDate, Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QDateEdit, QDialog, QDoubleSpinBox, QFileDialog,
                               QFormLayout, QFrame, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
                               QMessageBox, QPlainTextEdit, QPushButton, QTableWidget,
                               QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget)

from .. import APP_NAME, AUTHOR_HANDLE, AUTHOR_INSTAGRAM, YAPE_NUMBER_DISPLAY
from ..core.licensing import (STANDARD_MAX_KBPS, STANDARD_MAX_RES, LicenseError, LicenseManager, add_months, summarize_clients,
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
    def __init__(self, manager: LicenseManager, parent: QWidget | None = None):
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

        plans = QFrame()
        plans.setObjectName("NoticeCard")
        p_lay = QVBoxLayout(plans)
        p_lay.setContentsMargins(14, 10, 14, 10)
        p_lay.addWidget(_label(
            f"<b>Sin licencia:</b> descargas ilimitadas en calidad estándar "
            f"(video hasta {STANDARD_MAX_RES}p, audio hasta {STANDARD_MAX_KBPS} kbps).<br>"
            "<b>Con licencia:</b> alta calidad — HD, Full HD, 2K, 4K, 60fps, HDR, "
            "audio 320 kbps, FLAC y audio original."))
        root.addWidget(plans)

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

        self.btn_author = QPushButton("👑  Soy el administrador: cargar mi llave de licencias…")
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
            self.status.setText("👑 <b>Administrador</b> — este computador tiene tu llave de licencias.<br>"
                                "Todo ilimitado (cantidad y calidad, sin vencimiento) y panel «Administrar licencias».")
            for w in (self.key_input, self.how, self.btn_activate, self.btn_remove, self.btn_author):
                w.hide()
            return
        if m.licensed:
            self.status.setText(f"✅ <b>Licencia activa</b> — {m.license.summary}<br>"
                                "Alta calidad desbloqueada (HD, 4K, audio 320 kbps). ¡Gracias por tu apoyo! 💜")
            self.key_input.hide()
            self.how.hide()
            self.btn_activate.hide()
            self.btn_remove.show()
        else:
            if m.expired_license:
                self.status.setText(f"⚠️ <b>Tu licencia venció el {m.expired_license.expires}.</b> "
                                    "Estás descargando en calidad estándar. Pega una licencia nueva "
                                    "para recuperar la alta calidad.")
            else:
                self.status.setText("Plan gratuito: <b>calidad estándar</b>, sin límite de descargas.")
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
            QMessageBox.information(self, "Administrador activado",
                                    "👑 ¡Listo! Este computador ahora es el del administrador:\n"
                                    "todo ilimitado y menú «Administrar licencias» en la barra lateral.")
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
        QMessageBox.information(self, "Licencia activada", f"¡Listo, {lic.name}! Ya puedes descargar en alta calidad.")
        self._refresh()

    def _deactivate(self) -> None:
        if QMessageBox.question(self, "Quitar licencia",
                                "¿Quitar la licencia de este equipo? Podrás volver a activarla "
                                "pegando la misma clave.") == QMessageBox.Yes:
            self.manager.deactivate()
            self._refresh()


class LicenseGeneratorDialog(QDialog):
    """Panel del administrador: clientes, nuevas licencias, renovaciones e historial.

    Solo se abre en el computador que tiene la llave real de licencias.
    """

    STATUS_TEXT = {"permanent": "♾️ Permanente", "active": "✅ Activa",
                   "expiring": "⚠️ Vence pronto", "expired": "❌ Vencida"}

    def __init__(self, manager: LicenseManager, parent: QWidget | None = None):
        super().__init__(parent)
        self.manager = manager
        self.private_key = manager.private_key() or ""
        self.setWindowTitle("Panel de administrador — DescarGO")
        self.setMinimumSize(800, 720)
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 20)
        root.setSpacing(12)
        title = QLabel("👑  Panel de administrador")
        title.setObjectName("DialogTitle")
        root.addWidget(title)
        self.summary = _label("", muted=True)
        root.addWidget(self.summary)
        self.tabs = QTabWidget()
        self.tabs.addTab(self._clients_tab(), "👥  Clientes")
        self.tabs.addTab(self._new_tab(), "➕  Nueva licencia / Renovar")
        self.tabs.addTab(self._history_tab(), "📋  Historial")
        self.tabs.currentChanged.connect(self._tab_changed)
        root.addWidget(self.tabs, 1)
        close = QPushButton("Cerrar")
        close.clicked.connect(self.accept)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(close)
        root.addLayout(row)
        self._load_clients()

    def _tab_changed(self, index: int) -> None:
        if index == 0:
            self._load_clients()
        elif index == 2:
            self._load_history()

    # -- clientes ------------------------------------------------------------------
    def _clients_tab(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 12, 0, 0)
        top = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("🔎  Buscar cliente o código de equipo…")
        self.search.textChanged.connect(lambda _t: self._load_clients())
        top.addWidget(self.search, 1)
        new = QPushButton("➕  Nueva licencia")
        new.setObjectName("Primary")
        new.clicked.connect(lambda: self._open_new())
        top.addWidget(new)
        lay.addLayout(top)

        self.clients = QTableWidget(0, 6)
        self.clients.setHorizontalHeaderLabels(
            ["Cliente", "Código de equipo", "Estado", "Vence", "Pagado", "Licencias"])
        self.clients.verticalHeader().hide()
        self.clients.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.clients.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.clients.setSelectionMode(QAbstractItemView.SingleSelection)
        self.clients.setAlternatingRowColors(True)
        header = self.clients.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        self.clients.doubleClicked.connect(lambda _i: self._renew_selected())
        lay.addWidget(self.clients, 1)

        actions = QHBoxLayout()
        actions.addWidget(_label("Doble clic en un cliente para renovar su licencia.", muted=True), 1)
        copy = QPushButton("📋  Copiar su licencia")
        copy.clicked.connect(self._copy_client_license)
        renew = QPushButton("🔄  Renovar")
        renew.clicked.connect(self._renew_selected)
        actions.addWidget(copy)
        actions.addWidget(renew)
        lay.addLayout(actions)
        return page

    def _all_clients(self):
        return summarize_clients(self.manager.issued())

    def _load_clients(self) -> None:
        clients = self._all_clients()
        counts = {"permanent": 0, "active": 0, "expiring": 0, "expired": 0}
        for c in clients:
            counts[c.status()[0]] += 1
        total = sum(c.total_paid for c in clients)
        self.summary.setText(
            f"<b>{len(clients)}</b> clientes · ✅ {counts['active'] + counts['permanent']} activos · "
            f"⚠️ {counts['expiring']} por vencer · ❌ {counts['expired']} vencidos · "
            f"💰 Ingresos registrados: <b>S/ {total:,.2f}</b>  ·  Tú: 👑 administrador ilimitado")
        text = self.search.text().strip().lower() if hasattr(self, "search") else ""
        shown = [c for c in clients if not text or text in c.name.lower() or text in c.machine.lower()]
        self.clients.setRowCount(len(shown))
        for r, c in enumerate(shown):
            state, days = c.status()
            label = self.STATUS_TEXT[state]
            if state == "expiring":
                label += f" ({days} días)"
            vence = "—" if not c.expires else date.fromisoformat(c.expires).strftime("%d/%m/%Y")
            values = [c.name, c.machine, label, vence, f"S/ {c.total_paid:,.2f}", str(c.licenses)]
            for col, value in enumerate(values):
                cell = QTableWidgetItem(value)
                cell.setData(Qt.UserRole, c)
                self.clients.setItem(r, col, cell)

    def _selected_client(self):
        row = self.clients.currentRow()
        if row < 0:
            QMessageBox.information(self, "Selecciona un cliente", "Primero selecciona un cliente de la lista.")
            return None
        return self.clients.item(row, 0).data(Qt.UserRole)

    def _renew_selected(self) -> None:
        client = self._selected_client()
        if client:
            self._open_new(client.name, client.machine, renewing=True)

    def _copy_client_license(self) -> None:
        client = self._selected_client()
        if client:
            QGuiApplication.clipboard().setText(client.last_key)
            QMessageBox.information(self, "Copiada", f"Se copió la licencia de {client.name}.")

    # -- nueva licencia / renovar -----------------------------------------------------
    def _new_tab(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        form.setContentsMargins(6, 16, 6, 6)
        form.setVerticalSpacing(10)
        self.mode_label = _label("", muted=True)
        form.addRow("", self.mode_label)
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
        self.amount = QDoubleSpinBox()
        self.amount.setPrefix("S/ ")
        self.amount.setRange(0, 100000)
        self.amount.setDecimals(2)
        form.addRow("Monto pagado", self.amount)
        self.note = QLineEdit()
        self.note.setPlaceholderText("Opcional: n.º de operación Yape, comentario…")
        form.addRow("Nota", self.note)

        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setFixedHeight(80)
        self.output.setPlaceholderText("Aquí aparecerá la licencia para enviar al cliente.")
        form.addRow("Licencia", self.output)
        row = QHBoxLayout()
        row.addStretch(1)
        self.btn_msg = QPushButton("💬 Copiar mensaje para el cliente")
        self.btn_msg.setEnabled(False)
        self.btn_msg.clicked.connect(self._copy_message)
        self.btn_copy = QPushButton("📋 Copiar licencia")
        self.btn_copy.setEnabled(False)
        self.btn_copy.clicked.connect(self._copy)
        gen = QPushButton("Generar licencia")
        gen.setObjectName("Primary")
        gen.clicked.connect(self._generate)
        row.addWidget(self.btn_msg)
        row.addWidget(self.btn_copy)
        row.addWidget(gen)
        form.addRow("", row)

        self.duration.currentIndexChanged.connect(self._update_expiry)
        self.custom_date.dateChanged.connect(self._update_expiry)
        self._update_expiry()
        self._set_mode(False)
        return page

    def _set_mode(self, renewing: bool) -> None:
        self.mode_label.setText("🔄 <b>Renovación</b>: la nueva licencia reemplaza a la anterior al activarla."
                                if renewing else "➕ <b>Nueva licencia</b> para un cliente.")

    def _open_new(self, name: str = "", machine: str = "", renewing: bool = False) -> None:
        self.name.setText(name)
        self.machine.setText(machine)
        self.output.clear()
        self.btn_copy.setEnabled(False)
        self.btn_msg.setEnabled(False)
        self.amount.setValue(0)
        self.note.clear()
        self._set_mode(renewing)
        self.tabs.setCurrentIndex(1)
        (self.amount if renewing else self.name).setFocus()

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
        self.btn_msg.setEnabled(True)
        self.manager.log_issued(name, self.machine.text().strip().upper(), expires, key,
                                self.amount.value(), self.note.text().strip())
        self._load_clients()

    def _copy(self) -> None:
        QGuiApplication.clipboard().setText(self.output.toPlainText())
        self.btn_copy.setText("✔ Copiada")
        QTimer.singleShot(2000, lambda: self.btn_copy.setText("📋 Copiar licencia"))

    def _copy_message(self) -> None:
        exp = self._expiry()
        until = f"válida hasta el {exp.strftime('%d/%m/%Y')}" if exp else "permanente"
        message = (f"¡Hola {self.name.text().strip() or ''}! Gracias por tu compra 💜\n"
                   f"Tu licencia de DescarGO ({until}):\n\n{self.output.toPlainText()}\n\n"
                   "Para activarla: abre DescarGO → «Obtener licencia» → pega la licencia → «Activar».\n"
                   f"{AUTHOR_HANDLE}")
        QGuiApplication.clipboard().setText(message)
        self.btn_msg.setText("✔ Mensaje copiado")
        QTimer.singleShot(2000, lambda: self.btn_msg.setText("💬 Copiar mensaje para el cliente"))

    # -- historial ---------------------------------------------------------------------
    def _history_tab(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 12, 0, 0)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Fecha", "Cliente", "Código de equipo", "Vence", "Monto", "Nota"])
        self.table.verticalHeader().hide()
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setAlternatingRowColors(True)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        lay.addWidget(self.table, 1)
        row = QHBoxLayout()
        row.addWidget(_label("Todas las licencias que generaste, de la más reciente a la más antigua.",
                             muted=True), 1)
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
            monto = f"S/ {float(it.get('monto') or 0):,.2f}"
            for c, value in enumerate([str(it.get("fecha", ""))[:16].replace("T", " "),
                                       it.get("nombre", ""), it.get("equipo", ""), status, monto,
                                       it.get("nota", "")]):
                cell = QTableWidgetItem(str(value))
                cell.setData(Qt.UserRole, it.get("licencia", ""))
                self.table.setItem(r, c, cell)

    def _copy_selected(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        QGuiApplication.clipboard().setText(self.table.item(row, 0).data(Qt.UserRole))
        QMessageBox.information(self, "Copiada", "La licencia se copió al portapapeles.")
