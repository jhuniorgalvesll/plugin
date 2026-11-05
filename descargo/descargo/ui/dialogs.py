"""Ventanas secundarias: Ajustes, Acerca de, Invítame un café, Términos de uso."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog, QFileDialog, QFormLayout,
                               QFrame, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit,
                               QPushButton, QRadioButton, QSpinBox, QTabWidget, QVBoxLayout,
                               QWidget)

from .. import (APP_NAME, APP_TAGLINE, APP_VERSION, COPYRIGHT_OWNER, COPYRIGHT_TEXT,
                COPYRIGHT_WEBSITE, YAPE_NUMBER, YAPE_NUMBER_DISPLAY)
from ..config import COOKIE_BROWSERS, Settings
from ..core.security import detect_antivirus
from ..utils import find_ffmpeg_dir
from .theme import THEMES, build_stylesheet
from .widgets import brand_label, logo_pixmap


def _wrap(text: str, muted: bool = False) -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    label.setTextFormat(Qt.RichText)
    label.setOpenExternalLinks(True)
    if muted:
        label.setProperty("muted", True)
    return label


# ---------------------------------------------------------------------------
# Invítame un café (Yape)
# ---------------------------------------------------------------------------

class CoffeeDialog(QDialog):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Invítame un café — DescarGO")
        self.setFixedWidth(440)
        root = QVBoxLayout(self)
        root.setContentsMargins(26, 24, 26, 22)
        root.setSpacing(16)

        title = QLabel("☕  Invítame un café")
        title.setObjectName("DialogTitle")
        root.addWidget(title)
        root.addWidget(_wrap(
            f"{APP_NAME} es gratis y sin límites. Si te es útil, puedes apoyar su desarrollo "
            f"con un café vía <b>Yape</b>. ¡Cualquier monto ayuda y se agradece muchísimo!", muted=True))

        card = QFrame()
        card.setObjectName("YapeCard")
        c_lay = QVBoxLayout(card)
        c_lay.setContentsMargins(22, 20, 22, 20)
        c_lay.setSpacing(6)
        lbl = QLabel("Yapea al número")
        lbl.setStyleSheet("color: rgba(255,255,255,0.85); font-size: 10pt;")
        number = QLabel(YAPE_NUMBER_DISPLAY)
        number.setStyleSheet("color: white; font-size: 26pt; font-weight: 800; letter-spacing: 2px;")
        number.setTextInteractionFlags(Qt.TextSelectableByMouse)
        owner = QLabel(f"Apoyo al desarrollo de {APP_NAME} · {COPYRIGHT_OWNER}")
        owner.setStyleSheet("color: rgba(255,255,255,0.85); font-size: 9pt;")
        for w in (lbl, number, owner):
            w.setAlignment(Qt.AlignCenter)
            c_lay.addWidget(w)
        root.addWidget(card)

        steps = _wrap(
            "1. Abre tu app <b>Yape</b>.<br>"
            "2. Toca <b>Yapear</b> e ingresa el número de arriba.<br>"
            "3. Elige el monto que quieras y confirma. ¡Gracias! 💜", muted=True)
        root.addWidget(steps)

        row = QHBoxLayout()
        self.btn_copy = QPushButton("📋  Copiar número")
        self.btn_copy.setObjectName("Coffee")
        self.btn_copy.setCursor(Qt.PointingHandCursor)
        self.btn_copy.clicked.connect(self._copy)
        close = QPushButton("Cerrar")
        close.clicked.connect(self.accept)
        row.addWidget(self.btn_copy, 1)
        row.addWidget(close)
        root.addLayout(row)

    def _copy(self) -> None:
        QGuiApplication.clipboard().setText(YAPE_NUMBER)
        self.btn_copy.setText("✔  ¡Número copiado!")
        QTimer.singleShot(2000, lambda: self.btn_copy.setText("📋  Copiar número"))


# ---------------------------------------------------------------------------
# Acerca de
# ---------------------------------------------------------------------------

class AboutDialog(QDialog):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle(f"Acerca de {APP_NAME}")
        self.setFixedWidth(500)
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 26, 28, 22)
        root.setSpacing(12)

        head = QHBoxLayout()
        logo = QLabel()
        logo.setPixmap(logo_pixmap(72))
        head.addWidget(logo)
        col = QVBoxLayout()
        col.addWidget(brand_label(24))
        ver = QLabel(f"Versión {APP_VERSION}  ·  {APP_TAGLINE}")
        ver.setProperty("muted", True)
        col.addWidget(ver)
        head.addLayout(col, 1)
        root.addLayout(head)

        root.addWidget(_wrap(
            "Descargador de video y audio para escritorio: YouTube, Facebook, Reels, Instagram, "
            "TikTok y más de 1.800 sitios con contenido público y gratuito. Cada archivo pasa por "
            "un análisis de seguridad antes de llegar a tu carpeta."))

        rights = QFrame()
        rights.setObjectName("Card")
        r_lay = QVBoxLayout(rights)
        r_lay.setContentsMargins(16, 14, 16, 14)
        r_lay.addWidget(_wrap(f"<b>{COPYRIGHT_TEXT}</b>"))
        r_lay.addWidget(_wrap(
            f'Desarrollado por <a href="{COPYRIGHT_WEBSITE}">{COPYRIGHT_OWNER}</a>. '
            "Queda prohibida la reproducción, distribución o modificación de este software "
            "sin autorización del titular.", muted=True))
        root.addWidget(rights)

        root.addWidget(_wrap(
            "<b>Uso responsable.</b> Descarga solo contenido propio, con licencia libre o con "
            "permiso de su autor. DescarGO no descarga contenido de pago ni evade protecciones "
            "DRM. El usuario es responsable del uso que haga de los archivos descargados.", muted=True))

        root.addWidget(_wrap(
            "<b>Componentes de terceros:</b> yt-dlp (Unlicense), FFmpeg (LGPL), Qt / PySide6 (LGPL). "
            "Cada componente conserva su propia licencia.", muted=True))

        row = QHBoxLayout()
        coffee = QPushButton("☕  Invítame un café")
        coffee.setObjectName("Coffee")
        coffee.clicked.connect(lambda: CoffeeDialog(self).exec())
        web = QPushButton("🌐  lliuya.pe")
        web.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(COPYRIGHT_WEBSITE)))
        close = QPushButton("Cerrar")
        close.clicked.connect(self.accept)
        row.addWidget(coffee)
        row.addWidget(web)
        row.addStretch(1)
        row.addWidget(close)
        root.addLayout(row)


# ---------------------------------------------------------------------------
# Términos de uso (primer inicio)
# ---------------------------------------------------------------------------

TERMS_TEXT = f"""Bienvenido a {APP_NAME}.

Antes de empezar, acepta estas condiciones de uso responsable:

1. Descargarás solo contenido propio, con licencia libre (por ejemplo Creative Commons) o con permiso de su autor.
2. {APP_NAME} solo funciona con contenido público y gratuito. No descarga contenido de pago, de suscripción ni protegido con DRM, y no evade ninguna protección.
3. Respetarás los términos de servicio de cada plataforma y los derechos de autor. No redistribuirás contenido ajeno sin autorización.
4. El inicio de sesión (opcional) usa únicamente tu propia sesión del navegador y nunca sale de tu computador.
5. Cada archivo se analiza con varias capas de seguridad. Ningún sistema detecta el 100 % de las amenazas; mantén tu antivirus actualizado.
6. Eres responsable del uso que hagas de los archivos descargados.

{COPYRIGHT_TEXT}
"""


class TermsDialog(QDialog):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle(f"Bienvenido a {APP_NAME}")
        self.setFixedSize(560, 520)
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 20)
        root.setSpacing(12)
        head = QHBoxLayout()
        logo = QLabel()
        logo.setPixmap(logo_pixmap(48))
        head.addWidget(logo)
        head.addWidget(brand_label(20))
        head.addStretch(1)
        root.addLayout(head)
        text = QPlainTextEdit(TERMS_TEXT)
        text.setReadOnly(True)
        root.addWidget(text, 1)
        self.cb = QCheckBox("He leído y acepto las condiciones de uso responsable")
        root.addWidget(self.cb)
        row = QHBoxLayout()
        row.addStretch(1)
        exit_btn = QPushButton("Salir")
        exit_btn.clicked.connect(self.reject)
        self.ok = QPushButton("Aceptar y continuar")
        self.ok.setObjectName("Primary")
        self.ok.setEnabled(False)
        self.ok.clicked.connect(self.accept)
        self.cb.toggled.connect(self.ok.setEnabled)
        row.addWidget(exit_btn)
        row.addWidget(self.ok)
        root.addLayout(row)


# ---------------------------------------------------------------------------
# Ajustes
# ---------------------------------------------------------------------------

class SettingsDialog(QDialog):
    def __init__(self, settings: Settings, parent: QWidget | None = None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Ajustes — DescarGO")
        self.setMinimumWidth(660)
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 18)
        root.setSpacing(12)
        title = QLabel("⚙  Ajustes")
        title.setObjectName("DialogTitle")
        root.addWidget(title)

        tabs = QTabWidget()
        tabs.addTab(self._general_tab(), "General")
        tabs.addTab(self._network_tab(), "Red")
        tabs.addTab(self._security_tab(), "🛡 Seguridad")
        root.addWidget(tabs, 1)

        row = QHBoxLayout()
        row.addStretch(1)
        cancel = QPushButton("Cancelar")
        cancel.clicked.connect(self.reject)
        save = QPushButton("Guardar")
        save.setObjectName("Primary")
        save.clicked.connect(self._save)
        row.addWidget(cancel)
        row.addWidget(save)
        root.addLayout(row)

    def _form_page(self) -> tuple[QWidget, QFormLayout]:
        page = QWidget()
        form = QFormLayout(page)
        form.setContentsMargins(6, 16, 6, 6)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(12)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        return page, form

    def _general_tab(self) -> QWidget:
        s = self.settings
        page, form = self._form_page()
        folder_row = QHBoxLayout()
        self.ed_folder = QLineEdit(s.download_dir)
        browse = QPushButton("Cambiar…")
        browse.clicked.connect(self._browse)
        folder_row.addWidget(self.ed_folder, 1)
        folder_row.addWidget(browse)
        form.addRow("Carpeta de descargas", folder_row)
        self.cb_subfolder = QCheckBox("Crear una subcarpeta por plataforma (YouTube, TikTok…)")
        self.cb_subfolder.setChecked(s.subfolder_per_platform)
        form.addRow("", self.cb_subfolder)
        self.cb_quick = QCheckBox("Modo rápido: usar mi última elección sin abrir la ventana de opciones")
        self.cb_quick.setChecked(s.quick_mode)
        form.addRow("", self.cb_quick)
        self.cmb_theme = QComboBox()
        for key, name in THEMES.items():
            self.cmb_theme.addItem(name, key)
        self.cmb_theme.setCurrentIndex(max(0, self.cmb_theme.findData(s.theme)))
        form.addRow("Apariencia", self.cmb_theme)
        self.cb_cover = QCheckBox("Guardar portada, título y artista dentro del archivo (MP3, M4A, MP4…)")
        self.cb_cover.setChecked(s.embed_thumbnail)
        form.addRow("", self.cb_cover)
        self.cb_notify = QCheckBox("Mostrar un aviso de Windows cuando termine una descarga")
        self.cb_notify.setChecked(s.notifications)
        form.addRow("", self.cb_notify)
        self.cb_clip = QCheckBox("Detectar enlaces copiados en el portapapeles")
        self.cb_clip.setChecked(s.clipboard_watch)
        form.addRow("", self.cb_clip)
        ffmpeg = find_ffmpeg_dir()
        form.addRow("FFmpeg", _wrap(("✔ Encontrado: " + ffmpeg) if ffmpeg else
                                    "✖ No encontrado — necesario para unir video y audio en alta calidad",
                                    muted=True))
        return page

    def _network_tab(self) -> QWidget:
        s = self.settings
        page, form = self._form_page()
        self.sp_concurrent = QSpinBox()
        self.sp_concurrent.setRange(1, 10)
        self.sp_concurrent.setValue(s.max_concurrent)
        form.addRow("Descargas simultáneas", self.sp_concurrent)
        self.sp_rate = QSpinBox()
        self.sp_rate.setRange(0, 1_000_000)
        self.sp_rate.setSingleStep(500)
        self.sp_rate.setSuffix(" KB/s")
        self.sp_rate.setSpecialValueText("Sin límite")
        self.sp_rate.setValue(s.rate_limit_kb)
        form.addRow("Límite de velocidad", self.sp_rate)
        self.sp_sleep = QSpinBox()
        self.sp_sleep.setRange(0, 60)
        self.sp_sleep.setSuffix(" s")
        self.sp_sleep.setValue(s.sleep_between)
        form.addRow("Pausa entre elementos de una lista", self.sp_sleep)
        self.cmb_browser = QComboBox()
        for key, name in COOKIE_BROWSERS.items():
            self.cmb_browser.addItem(name, key)
        self.cmb_browser.setCurrentIndex(max(0, self.cmb_browser.findData(s.cookies_browser)))
        form.addRow("Usar sesión del navegador", self.cmb_browser)
        form.addRow("", _wrap(
            "Úsalo solo si Instagram, Facebook o TikTok piden iniciar sesión. DescarGO lee tu sesión "
            "localmente para acceder a lo que <b>tú ya puedes ver</b>; nunca se envía a ningún "
            "servidor. Cierra el navegador antes de descargar si da error.", muted=True))
        form.addRow("", _wrap(
            "Las pausas y el límite de descargas simultáneas evitan saturar a las plataformas "
            "y que bloqueen tu conexión.", muted=True))
        return page

    def _security_tab(self) -> QWidget:
        s = self.settings
        page, form = self._form_page()
        form.addRow("Siempre activo", _wrap(
            "✔ Cuarentena: cada descarga llega primero a una carpeta aislada<br>"
            "✔ Verificación del tipo real del archivo (firma interna + FFmpeg)<br>"
            "✔ Bloqueo de ejecutables, dobles extensiones y nombres disfrazados<br>"
            "✔ Bloqueo de páginas de pago y contenido con DRM"))
        engine = detect_antivirus()
        self.cb_av = QCheckBox("Analizar con el antivirus del sistema")
        self.cb_av.setChecked(s.antivirus_enabled)
        form.addRow("Antivirus", self.cb_av)
        form.addRow("", _wrap(("Detectado: <b>" + engine.name + "</b>") if engine else
                              "No se detectó Microsoft Defender ni ClamAV en este equipo.", muted=True))
        self.cb_vt = QCheckBox("Consultar VirusTotal (más de 70 antivirus)")
        self.cb_vt.setChecked(s.virustotal_enabled)
        form.addRow("VirusTotal", self.cb_vt)
        self.ed_vt = QLineEdit(s.virustotal_key)
        self.ed_vt.setEchoMode(QLineEdit.Password)
        self.ed_vt.setPlaceholderText("Clave API gratuita de virustotal.com")
        form.addRow("Clave API", self.ed_vt)
        form.addRow("", _wrap(
            "Solo se envía la huella SHA-256 del archivo, nunca el archivo. "
            'Obtén tu clave gratis en <a '
            'href="https://www.virustotal.com/gui/join-us">virustotal.com</a>.', muted=True))
        self.rb_delete = QRadioButton("Eliminar el archivo")
        self.rb_quarantine = QRadioButton("Dejarlo aislado en cuarentena")
        (self.rb_quarantine if s.threat_action == "quarantine" else self.rb_delete).setChecked(True)
        threat = QVBoxLayout()
        threat.addWidget(self.rb_delete)
        threat.addWidget(self.rb_quarantine)
        form.addRow("Si se detecta una amenaza", threat)
        return page

    def _browse(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Elegir carpeta de descargas", self.ed_folder.text())
        if folder:
            self.ed_folder.setText(folder)

    def _save(self) -> None:
        s = self.settings
        s.download_dir = self.ed_folder.text().strip() or s.download_dir
        s.subfolder_per_platform = self.cb_subfolder.isChecked()
        s.quick_mode = self.cb_quick.isChecked()
        s.clipboard_watch = self.cb_clip.isChecked()
        s.max_concurrent = self.sp_concurrent.value()
        s.rate_limit_kb = self.sp_rate.value()
        s.sleep_between = self.sp_sleep.value()
        s.cookies_browser = self.cmb_browser.currentData()
        s.antivirus_enabled = self.cb_av.isChecked()
        s.virustotal_key = self.ed_vt.text().strip()
        s.virustotal_enabled = self.cb_vt.isChecked() and bool(s.virustotal_key)
        s.threat_action = "quarantine" if self.rb_quarantine.isChecked() else "delete"
        s.theme = self.cmb_theme.currentData()
        s.embed_thumbnail = self.cb_cover.isChecked()
        s.notifications = self.cb_notify.isChecked()
        s.save()
        QApplication.instance().setStyleSheet(build_stylesheet(s.theme))
        self.accept()


# ---------------------------------------------------------------------------
# Novedades (primera vez que se abre una versión nueva)
# ---------------------------------------------------------------------------

class WhatsNewDialog(QDialog):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        from ..changelog import notes_for
        self.setWindowTitle(f"Novedades de {APP_NAME} {APP_VERSION}")
        self.setFixedWidth(560)
        root = QVBoxLayout(self)
        root.setContentsMargins(26, 24, 26, 20)
        root.setSpacing(14)
        head = QHBoxLayout()
        logo = QLabel()
        logo.setPixmap(logo_pixmap(48))
        head.addWidget(logo)
        col = QVBoxLayout()
        title = QLabel(f"¡Novedades de la versión {APP_VERSION}!")
        title.setObjectName("DialogTitle")
        col.addWidget(title)
        sub = QLabel(APP_TAGLINE)
        sub.setProperty("muted", True)
        col.addWidget(sub)
        head.addLayout(col, 1)
        root.addLayout(head)
        for line in notes_for(APP_VERSION):
            card = QFrame()
            card.setObjectName("Card")
            lay = QVBoxLayout(card)
            lay.setContentsMargins(14, 10, 14, 10)
            lay.addWidget(_wrap(line))
            root.addWidget(card)
        row = QHBoxLayout()
        coffee = QPushButton("☕  Invítame un café")
        coffee.setObjectName("Coffee")
        coffee.clicked.connect(lambda: CoffeeDialog(self).exec())
        ok = QPushButton("¡Genial, empecemos!")
        ok.setObjectName("Primary")
        ok.clicked.connect(self.accept)
        row.addWidget(coffee)
        row.addStretch(1)
        row.addWidget(ok)
        root.addLayout(row)
