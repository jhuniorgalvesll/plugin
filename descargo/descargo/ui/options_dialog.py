"""Ventana de opciones: elegir video o audio, calidad, formato y carpeta."""

from __future__ import annotations

from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QDialog, QFileDialog,
                               QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
                               QListWidget, QListWidgetItem, QPushButton, QRadioButton,
                               QScrollArea, QStackedWidget, QVBoxLayout, QWidget)

from ..config import Settings
from ..core.models import (AUDIO_BITRATES, AUDIO_FORMATS, AUDIO_FORMATS_WITH_BITRATE,
                           PLAYLIST_HEIGHT_PRESETS, VIDEO_CONTAINERS, DownloadRequest,
                           MediaInfo, resolution_name)
from ..utils import human_duration, human_size
from .widgets import ElidedLabel

_LANG_NAMES = {
    "es": "Español", "en": "Inglés", "pt": "Portugués", "fr": "Francés", "it": "Italiano",
    "de": "Alemán", "ja": "Japonés", "ko": "Coreano", "zh": "Chino", "ru": "Ruso",
    "qu": "Quechua", "ar": "Árabe", "hi": "Hindi",
}


def lang_label(code: str) -> str:
    base = code.split("-")[0]
    name = _LANG_NAMES.get(base, code)
    if code.endswith("-orig"):
        return f"{name} (automático, original)"
    if code != base:
        return f"{name} ({code})"
    return name


class OptionsDialog(QDialog):
    def __init__(self, info: MediaInfo, settings: Settings, parent: QWidget | None = None):
        super().__init__(parent)
        self.info = info
        self.settings = settings
        self.requests: list[DownloadRequest] = []
        self.setWindowTitle("Opciones de descarga — DescarGO")
        self.setMinimumWidth(640)
        self.resize(700, 860 if not info.is_playlist else 900)
        self._net = QNetworkAccessManager(self)
        last = settings.last_choice or {}

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 18)
        root.setSpacing(14)
        root.addWidget(self._header())

        # Video / Audio
        kind_row = QHBoxLayout()
        self.rb_video = QRadioButton("🎬  Video")
        self.rb_audio = QRadioButton("🎵  Solo audio")
        for rb in (self.rb_video, self.rb_audio):
            rb.setObjectName("Choice")
            rb.setCursor(Qt.PointingHandCursor)
            kind_row.addWidget(rb, 1)
        self._kind_group = QButtonGroup(self)
        self._kind_group.addButton(self.rb_video)
        self._kind_group.addButton(self.rb_audio)
        root.addLayout(kind_row)

        self.stack = QStackedWidget()
        self.stack.addWidget(self._video_page(last))
        self.stack.addWidget(self._audio_page(last))
        root.addWidget(self.stack, 1)

        if info.is_playlist:
            root.addWidget(self._playlist_box())

        root.addLayout(self._destination_row())

        self.cb_remember = QCheckBox("Recordar mi elección (modo rápido: descargar con un clic)")
        self.cb_remember.setChecked(settings.quick_mode)
        root.addWidget(self.cb_remember)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton("Cancelar")
        cancel.clicked.connect(self.reject)
        self.btn_ok = QPushButton("⬇  Descargar")
        self.btn_ok.setObjectName("Primary")
        self.btn_ok.setDefault(True)
        self.btn_ok.clicked.connect(self._accept)
        buttons.addWidget(cancel)
        buttons.addWidget(self.btn_ok)
        root.addLayout(buttons)

        self.rb_video.toggled.connect(lambda on: self.stack.setCurrentIndex(0 if on else 1))
        if last.get("kind") == "audio":
            self.rb_audio.setChecked(True)
            self.stack.setCurrentIndex(1)
        else:
            self.rb_video.setChecked(True)

    # -- secciones -----------------------------------------------------------
    def _header(self) -> QWidget:
        card = QFrame()
        card.setObjectName("Card")
        row = QHBoxLayout(card)
        row.setContentsMargins(12, 12, 12, 12)
        row.setSpacing(14)
        self.thumb = QLabel("🎞")
        self.thumb.setFixedSize(160, 90)
        self.thumb.setAlignment(Qt.AlignCenter)
        self.thumb.setStyleSheet("background:#1E2338; border-radius:8px; font-size:24pt;")
        row.addWidget(self.thumb)
        col = QVBoxLayout()
        title = ElidedLabel(self.info.title)
        title.setStyleSheet("font-size: 12pt; font-weight: 700;")
        col.addWidget(title)
        bits = [self.info.platform]
        if self.info.uploader:
            bits.append(self.info.uploader)
        if self.info.is_playlist:
            bits.append(f"{len(self.info.entries)} elementos")
        elif self.info.duration:
            bits.append(human_duration(self.info.duration))
        meta = ElidedLabel("  ·  ".join(bits))
        meta.setProperty("muted", True)
        col.addWidget(meta)
        badge = QLabel("Lista / perfil" if self.info.is_playlist else "Contenido público")
        badge.setObjectName("Badge")
        col.addWidget(badge, 0, Qt.AlignLeft)
        col.addStretch(1)
        row.addLayout(col, 1)
        if self.info.thumbnail:
            reply = self._net.get(QNetworkRequest(QUrl(self.info.thumbnail)))
            reply.finished.connect(lambda r=reply: self._thumb_loaded(r))
        return card

    def _thumb_loaded(self, reply: QNetworkReply) -> None:
        if reply.error() == QNetworkReply.NoError:
            pix = QPixmap()
            if pix.loadFromData(reply.readAll()):
                self.thumb.setPixmap(pix.scaled(self.thumb.size(), Qt.KeepAspectRatioByExpanding,
                                                Qt.SmoothTransformation))
                self.thumb.setText("")
        reply.deleteLater()

    def _video_page(self, last: dict) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)
        label = QLabel("Calidad")
        label.setObjectName("SectionTitle")
        lay.addWidget(label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumHeight(250 if not self.info.is_playlist else 150)
        holder = QWidget()
        grid = QVBoxLayout(holder)
        grid.setContentsMargins(0, 0, 6, 0)
        grid.setSpacing(6)
        self._quality_group = QButtonGroup(self)
        self._quality_values: dict[int, tuple[int | None, bool | None, bool | None]] = {}

        choices: list[tuple[str, str, tuple]] = []
        if self.info.is_playlist or not self.info.video_options:
            for h in PLAYLIST_HEIGHT_PRESETS:
                name = "Máxima calidad disponible" if h is None else f"{resolution_name(h)} · hasta {h}p"
                choices.append((name, "", (h, None, None)))
        else:
            for opt in self.info.video_options:
                size = f"~ {human_size(opt.est_size)}" if opt.est_size else ""
                choices.append((opt.label, size, (opt.height, opt.hfr, opt.hdr)))

        wanted = last.get("video_height")
        selected_index = 0
        best_gap = None
        for idx, (name, size, value) in enumerate(choices):
            rb = QRadioButton(f"{name}" + (f"      {size}" if size else ""))
            rb.setObjectName("QualityOption")
            rb.setCursor(Qt.PointingHandCursor)
            self._quality_group.addButton(rb, idx)
            self._quality_values[idx] = value
            grid.addWidget(rb)
            h = value[0]
            if isinstance(wanted, int) and h:
                gap = abs(h - wanted)
                if best_gap is None or gap < best_gap:
                    best_gap, selected_index = gap, idx
        grid.addStretch(1)
        if self._quality_group.button(selected_index):
            self._quality_group.button(selected_index).setChecked(True)
        scroll.setWidget(holder)
        lay.addWidget(scroll, 1)

        form = QGridLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(8)
        form.addWidget(QLabel("Formato"), 0, 0)
        self.cmb_container = QComboBox()
        for key, text in VIDEO_CONTAINERS.items():
            self.cmb_container.addItem(text, key)
        idx = self.cmb_container.findData(last.get("container", "mp4"))
        self.cmb_container.setCurrentIndex(max(0, idx))
        form.addWidget(self.cmb_container, 0, 1)
        lay.addLayout(form)

        # Subtítulos
        langs = self.info.subtitles if not self.info.is_playlist else ["es", "en"]
        self.subs_list = QListWidget()
        self.subs_list.setMaximumHeight(100)
        wanted_subs = set(last.get("subtitles") or [])
        for code in langs:
            item = QListWidgetItem(lang_label(code))
            item.setData(Qt.UserRole, code)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if code in wanted_subs else Qt.Unchecked)
            self.subs_list.addItem(item)
        self.cb_embed = QCheckBox("Integrar subtítulos dentro del video")
        self.cb_embed.setChecked(bool(last.get("embed_subtitles")))
        sub_title = QLabel("Subtítulos" + ("" if langs else " — este video no tiene subtítulos"))
        sub_title.setObjectName("SectionTitle")
        lay.addWidget(sub_title)
        if langs:
            lay.addWidget(self.subs_list)
            lay.addWidget(self.cb_embed)
        else:
            self.subs_list.hide()
            self.cb_embed.hide()
        return page

    def _audio_page(self, last: dict) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)
        title = QLabel("Audio")
        title.setObjectName("SectionTitle")
        lay.addWidget(title)

        form = QGridLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)
        form.addWidget(QLabel("Formato"), 0, 0)
        self.cmb_audio_fmt = QComboBox()
        for key, text in AUDIO_FORMATS.items():
            self.cmb_audio_fmt.addItem(text, key)
        self.cmb_audio_fmt.setCurrentIndex(max(0, self.cmb_audio_fmt.findData(last.get("audio_format", "original"))))
        form.addWidget(self.cmb_audio_fmt, 0, 1)

        form.addWidget(QLabel("Calidad"), 1, 0)
        self.cmb_bitrate = QComboBox()
        for br in AUDIO_BITRATES:
            self.cmb_bitrate.addItem(f"{br} kbps", br)
        self.cmb_bitrate.setCurrentIndex(max(0, self.cmb_bitrate.findData(last.get("audio_bitrate", 192))))
        form.addWidget(self.cmb_bitrate, 1, 1)
        form.setColumnStretch(1, 1)
        lay.addLayout(form)

        source = ""
        if self.info.audio_abr:
            source = f"El audio de origen tiene aproximadamente {self.info.audio_abr:.0f} kbps"
            if self.info.audio_size:
                source += f" (~ {human_size(self.info.audio_size)})"
            source += ". "
        notice = QFrame()
        notice.setObjectName("NoticeCard")
        n_lay = QVBoxLayout(notice)
        n_lay.setContentsMargins(14, 12, 14, 12)
        text = QLabel(
            "ℹ️  " + source
            + "«Original» guarda la pista tal como existe, sin pérdida extra. "
              "Convertir a una calidad mayor (por ejemplo 320 kbps o FLAC) no mejora el sonido; "
              "solo aumenta el tamaño del archivo."
        )
        text.setWordWrap(True)
        n_lay.addWidget(text)
        lay.addWidget(notice)
        lay.addStretch(1)

        self.cmb_audio_fmt.currentIndexChanged.connect(self._update_bitrate_state)
        self._update_bitrate_state()
        return page

    def _update_bitrate_state(self) -> None:
        self.cmb_bitrate.setEnabled(self.cmb_audio_fmt.currentData() in AUDIO_FORMATS_WITH_BITRATE)

    def _playlist_box(self) -> QWidget:
        box = QFrame()
        box.setObjectName("Card")
        lay = QVBoxLayout(box)
        lay.setContentsMargins(12, 10, 12, 10)
        head = QHBoxLayout()
        title = QLabel(f"Elementos de la lista ({len(self.info.entries)})")
        title.setObjectName("SectionTitle")
        head.addWidget(title, 1)
        all_btn = QPushButton("Marcar todos")
        none_btn = QPushButton("Ninguno")
        for b in (all_btn, none_btn):
            b.setObjectName("Small")
            head.addWidget(b)
        lay.addLayout(head)
        self.entries_list = QListWidget()
        self.entries_list.setMinimumHeight(150)
        for entry in self.info.entries:
            dur = f"  ({human_duration(entry.duration)})" if entry.duration else ""
            item = QListWidgetItem(entry.title + dur)
            item.setData(Qt.UserRole, entry)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked)
            self.entries_list.addItem(item)
        lay.addWidget(self.entries_list)
        all_btn.clicked.connect(lambda: self._check_all(True))
        none_btn.clicked.connect(lambda: self._check_all(False))
        return box

    def _check_all(self, checked: bool) -> None:
        for i in range(self.entries_list.count()):
            self.entries_list.item(i).setCheckState(Qt.Checked if checked else Qt.Unchecked)

    def _destination_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addWidget(QLabel("Guardar en"))
        self.ed_dest = QLineEdit(self.settings.download_dir)
        row.addWidget(self.ed_dest, 1)
        browse = QPushButton("Cambiar…")
        browse.clicked.connect(self._browse)
        row.addWidget(browse)
        return row

    def _browse(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Elegir carpeta de descargas", self.ed_dest.text())
        if folder:
            self.ed_dest.setText(folder)

    # -- resultado -------------------------------------------------------------
    def _template(self) -> DownloadRequest:
        req = DownloadRequest(url="", title="", platform=self.info.platform,
                              dest_dir=self.ed_dest.text().strip() or self.settings.download_dir)
        if self.rb_audio.isChecked():
            req.kind = "audio"
            req.audio_format = self.cmb_audio_fmt.currentData()
            req.audio_bitrate = self.cmb_bitrate.currentData()
        else:
            req.kind = "video"
            height, fps60, hdr = self._quality_values.get(self._quality_group.checkedId(), (None, None, None))
            req.video_height, req.video_fps60, req.video_hdr = height, fps60, hdr
            req.container = self.cmb_container.currentData()
            req.subtitles = [self.subs_list.item(i).data(Qt.UserRole)
                             for i in range(self.subs_list.count())
                             if self.subs_list.item(i).checkState() == Qt.Checked]
            req.embed_subtitles = self.cb_embed.isChecked() and bool(req.subtitles)
        return req

    def _accept(self) -> None:
        template = self._template()
        if self.info.is_playlist:
            for i in range(self.entries_list.count()):
                item = self.entries_list.item(i)
                if item.checkState() != Qt.Checked:
                    continue
                entry = item.data(Qt.UserRole)
                self.requests.append(DownloadRequest.from_choice(
                    template.choice_dict(), url=entry.url, title=entry.title,
                    platform=self.info.platform, dest_dir=template.dest_dir))
            if not self.requests:
                self.btn_ok.setText("Marca al menos un elemento")
                return
        else:
            template.url = self.info.url
            template.title = self.info.title
            template.thumbnail = self.info.thumbnail
            self.requests.append(template)

        self.settings.last_choice = template.choice_dict()
        self.settings.quick_mode = self.cb_remember.isChecked()
        self.settings.download_dir = template.dest_dir
        self.settings.save()
        self.accept()
