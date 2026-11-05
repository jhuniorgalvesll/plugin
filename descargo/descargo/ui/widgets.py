"""Componentes reutilizables de la interfaz."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QProgressBar, QPushButton,
                               QSizePolicy, QVBoxLayout, QWidget)

from ..core.downloader import (STATUS_BLOCKED, STATUS_CANCELLED, STATUS_DONE, STATUS_ERROR,
                               STATUS_PAUSED, STATUS_SUSPICIOUS, STATUS_THREAT, JobResult)
from ..core.models import DownloadRequest
from ..utils import ASSETS_DIR, human_duration, human_size, human_speed
from .theme import accent

LOGO_PATH = ASSETS_DIR / "descargo.svg"


def logo_pixmap(size: int) -> QPixmap:
    pixmap = QPixmap(QSize(size, size) * 2)
    pixmap.fill(Qt.transparent)
    renderer = QSvgRenderer(str(LOGO_PATH))
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    pixmap.setDevicePixelRatio(2)
    return pixmap


def app_icon() -> QIcon:
    icon = QIcon()
    for s in (16, 24, 32, 48, 64, 128, 256):
        icon.addPixmap(logo_pixmap(s))
    return icon


def brand_label(font_pt: int = 20) -> QLabel:
    label = QLabel(
        f'<span style="font-size:{font_pt}pt; font-weight:700;">Descar</span>'
        f'<span style="font-size:{font_pt}pt; font-weight:800; color:{accent()};">GO</span>'
    )
    label.setTextFormat(Qt.RichText)
    return label


def repolish(widget: QWidget) -> None:
    widget.style().unpolish(widget)
    widget.style().polish(widget)


class ElidedLabel(QLabel):
    """Etiqueta que recorta con «…» los textos largos."""

    def __init__(self, text: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        self._full = text
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.setToolTip(text)
        self._update()

    def setFullText(self, text: str) -> None:
        self._full = text
        self.setToolTip(text)
        self._update()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._update()

    def _update(self) -> None:
        metrics = self.fontMetrics()
        super().setText(metrics.elidedText(self._full, Qt.ElideRight, max(40, self.width())))


class DownloadItem(QFrame):
    """Tarjeta de una descarga en la cola."""

    pause_requested = Signal(str)
    resume_requested = Signal(str)
    cancel_requested = Signal(str)
    remove_requested = Signal(str)
    open_folder_requested = Signal(str)
    release_requested = Signal(str)
    report_requested = Signal(str)

    def __init__(self, request: DownloadRequest, parent: QWidget | None = None):
        super().__init__(parent)
        self.request = request
        self.job_id = request.job_id
        self.result: JobResult | None = None
        self.finished = False
        self.setObjectName("ItemCard")

        icon = QLabel("🎵" if request.kind == "audio" else "🎬")
        icon.setStyleSheet("font-size: 20pt;")
        icon.setFixedWidth(42)
        icon.setAlignment(Qt.AlignCenter)

        self.title = ElidedLabel(request.title)
        self.title.setStyleSheet("font-weight: 600; font-size: 10.5pt;")
        meta = QLabel(f"{request.platform}  ·  {request.quality_label}")
        meta.setProperty("muted", True)

        self.progress = QProgressBar()
        self.progress.setRange(0, 1000)
        self.progress.setValue(0)
        self.progress.setFixedHeight(8)
        self.progress.setTextVisible(False)

        self.status = QLabel("En cola…")
        self.status.setProperty("muted", True)

        self.btn_pause = self._button("⏸ Pausar", self.pause_requested)
        self.btn_resume = self._button("▶ Reanudar", self.resume_requested)
        self.btn_cancel = self._button("✕ Cancelar", self.cancel_requested, danger=True)
        self.btn_open = self._button("📂 Abrir carpeta", self.open_folder_requested)
        self.btn_release = self._button("Entregar de todos modos", self.release_requested)
        self.btn_report = self._button("🛡 Informe", self.report_requested)
        self.btn_remove = self._button("Quitar", self.remove_requested)
        for b in (self.btn_resume, self.btn_open, self.btn_release, self.btn_report, self.btn_remove):
            b.hide()

        text_col = QVBoxLayout()
        text_col.setSpacing(4)
        text_col.addWidget(self.title)
        text_col.addWidget(meta)

        top = QHBoxLayout()
        top.setSpacing(12)
        top.addWidget(icon)
        top.addLayout(text_col, 1)

        bottom = QHBoxLayout()
        bottom.setSpacing(6)
        bottom.addWidget(self.status, 1)
        for b in (self.btn_report, self.btn_release, self.btn_open, self.btn_pause,
                  self.btn_resume, self.btn_cancel, self.btn_remove):
            bottom.addWidget(b)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)
        layout.addLayout(top)
        layout.addWidget(self.progress)
        layout.addLayout(bottom)

    def _button(self, text: str, signal: Signal, danger: bool = False) -> QPushButton:
        btn = QPushButton(text)
        btn.setObjectName("Small")
        if danger:
            btn.setProperty("class", "danger")
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(lambda: signal.emit(self.job_id))
        return btn

    def _set_state(self, state: str) -> None:
        self.progress.setProperty("state", state)
        repolish(self.progress)

    # -- actualizaciones desde el motor --------------------------------------
    def update_progress(self, data: dict) -> None:
        phase = data.get("phase")
        if phase == "starting":
            self.status.setText("Preparando descarga…")
            self.progress.setRange(0, 0)
        elif phase == "download":
            percent = data.get("percent")
            part = "audio" if data.get("part") == "audio" and self.request.kind == "video" else ""
            if percent is None:
                self.progress.setRange(0, 0)
            else:
                self.progress.setRange(0, 1000)
                self.progress.setValue(int(percent * 10))
            self._set_state("")
            bits = []
            if percent is not None:
                bits.append(f"{percent:.0f}%")
            if part:
                bits.append("pista de audio")
            total = data.get("total")
            bits.append(f"{human_size(data.get('downloaded'))} de {human_size(total)}" if total
                        else human_size(data.get("downloaded")))
            if data.get("speed"):
                bits.append(human_speed(data["speed"]))
            if data.get("eta") is not None:
                bits.append(f"quedan {human_duration(data['eta'])}")
            self.status.setText("Descargando  ·  " + "  ·  ".join(bits))
        elif phase == "waiting":
            self.status.setText(f"Esperando {data.get('seconds', 0):.0f} s (pausa entre elementos)…")
        elif phase == "processing":
            self.progress.setRange(0, 0)
            self.status.setText("Procesando (uniendo video y audio / convirtiendo)…")
        elif phase == "scanning":
            self.progress.setRange(0, 0)
            self._set_state("scan")
            self.status.setText(f"🛡 Analizando seguridad ({data.get('index')}/{data.get('count')})…")
            self.btn_pause.hide()

    def set_queued(self) -> None:
        self.finished = False
        self.result = None
        self.progress.setRange(0, 1000)
        self._set_state("")
        self.status.setText("En cola…")
        self.btn_pause.show()
        self.btn_cancel.show()
        for b in (self.btn_resume, self.btn_open, self.btn_release, self.btn_report, self.btn_remove):
            b.hide()

    def set_result(self, result: JobResult) -> None:
        self.result = result
        self.progress.setRange(0, 1000)
        self.btn_pause.hide()
        status = result.status
        if status == STATUS_PAUSED:
            self.btn_resume.show()
            self.btn_cancel.show()
            self.status.setText("En pausa")
            self._set_state("warn")
            return

        self.finished = True
        self.btn_cancel.hide()
        self.btn_remove.show()
        self.progress.setValue(1000)
        if result.reports:
            self.btn_report.show()

        if status == STATUS_DONE:
            self._set_state("ok")
            size = f"  ·  {human_size(result.total_size)}" if result.total_size else ""
            self.status.setText(f"✅ Seguro  ·  Descargado{size}")
            self.btn_open.show()
        elif status == STATUS_SUSPICIOUS:
            self._set_state("warn")
            self.status.setText("⚠️ " + result.message)
            self.btn_release.show()
        elif status == STATUS_THREAT:
            self._set_state("fail")
            self.status.setText("❌ " + result.message)
        elif status == STATUS_BLOCKED:
            self._set_state("fail")
            self.status.setText("🚫 " + result.message.splitlines()[0])
            self.status.setToolTip(result.message)
        elif status == STATUS_CANCELLED:
            self.progress.setValue(0)
            self.status.setText("Cancelado")
        elif status == STATUS_ERROR:
            self._set_state("fail")
            first = result.message.splitlines()[0] if result.message else "Error"
            self.status.setText("Error: " + first)
            self.status.setToolTip(result.message)
            self.btn_resume.setText("↻ Reintentar")
            self.btn_resume.show()
            self.finished = True

    def set_released(self, files: list[str]) -> None:
        self.btn_release.hide()
        self.btn_open.show()
        self._set_state("ok")
        self.status.setText(f"Entregado manualmente ({len(files)} archivo/s)")


class AnalyzingItem(QFrame):
    """Tarjeta temporal mientras se analiza un enlace."""

    def __init__(self, url: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("ItemCard")
        icon = QLabel("🔍")
        icon.setStyleSheet("font-size: 18pt;")
        icon.setFixedWidth(42)
        icon.setAlignment(Qt.AlignCenter)
        title = QLabel("Analizando enlace y calidades disponibles…")
        title.setStyleSheet("font-weight: 600;")
        link = ElidedLabel(url)
        link.setProperty("muted", True)
        bar = QProgressBar()
        bar.setRange(0, 0)
        bar.setFixedHeight(6)
        col = QVBoxLayout()
        col.addWidget(title)
        col.addWidget(link)
        col.addWidget(bar)
        row = QHBoxLayout(self)
        row.setContentsMargins(14, 12, 14, 12)
        row.addWidget(icon)
        row.addLayout(col, 1)
