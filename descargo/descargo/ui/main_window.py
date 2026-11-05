"""Ventana principal de DescarGO."""

from __future__ import annotations

import uuid
from pathlib import Path

from PySide6.QtCore import Qt, QThreadPool, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QGuiApplication, QKeySequence, QShortcut
from PySide6.QtWidgets import (QAbstractItemView, QButtonGroup, QFrame, QHBoxLayout, QHeaderView, QLabel,
                               QLineEdit, QMainWindow, QMessageBox, QPushButton, QScrollArea,
                               QStackedWidget, QTableWidget, QTableWidgetItem, QVBoxLayout,
                               QWidget)

from .. import APP_NAME, APP_TAGLINE, APP_VERSION, COPYRIGHT_YEAR
from ..config import Settings
from ..core import policy
from ..core.downloader import (STATUS_CANCELLED, STATUS_DONE, STATUS_PAUSED, DownloadJob,
                               JobResult, JobSettings, release_from_quarantine)
from ..core.library import Library
from ..core.models import DownloadRequest, MediaInfo
from ..core.security import VERDICT_LABELS
from ..utils import extract_urls, find_ffmpeg_dir, human_size
from .dialogs import AboutDialog, CoffeeDialog, SettingsDialog
from .options_dialog import OptionsDialog
from .widgets import AnalyzingItem, DownloadItem, brand_label, logo_pixmap
from .workers import AnalyzeWorker, DownloadWorker

_STATUS_TEXT = {
    "done": "Completado", "suspicious": "En cuarentena", "threat": "Amenaza",
    "error": "Error", "blocked": "Bloqueado", "cancelled": "Cancelado",
}


class MainWindow(QMainWindow):
    def __init__(self, settings: Settings, library: Library):
        super().__init__()
        self.settings = settings
        self.library = library
        self.setWindowTitle(f"{APP_NAME} — {APP_TAGLINE}")
        self.resize(1040, 720)
        self.setMinimumSize(820, 560)

        self.download_pool = QThreadPool(self)
        self.download_pool.setMaxThreadCount(settings.max_concurrent)
        self.analyze_pool = QThreadPool(self)
        self.analyze_pool.setMaxThreadCount(3)

        self.items: dict[str, DownloadItem] = {}
        self.workers: dict[str, DownloadWorker] = {}
        self.analyzing: dict[str, tuple[AnalyzeWorker, AnalyzingItem]] = {}
        self._last_clip = ""

        central = QWidget()
        central.setObjectName("Central")
        self.setCentralWidget(central)
        outer = QHBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self._sidebar())

        content = QWidget()
        root = QVBoxLayout(content)
        root.setContentsMargins(26, 22, 26, 12)
        root.setSpacing(16)
        self.page_title = QLabel("Descargas")
        self.page_title.setObjectName("PageTitle")
        root.addWidget(self.page_title)
        root.addWidget(self._url_card())

        self.pages = QStackedWidget()
        self.pages.addWidget(self._downloads_tab())
        self.pages.addWidget(self._history_tab())
        root.addWidget(self.pages, 1)
        outer.addWidget(content, 1)
        self.show_page(0)

        status = self.statusBar()
        status.addPermanentWidget(QLabel(f"{APP_NAME} v{APP_VERSION}"))
        self._show_ready_message()

        QGuiApplication.clipboard().dataChanged.connect(self._clipboard_changed)
        QShortcut(QKeySequence.Paste, self, activated=self._paste_shortcut)

    # -- construcción ----------------------------------------------------------
    def _sidebar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("Sidebar")
        bar.setFixedWidth(220)
        lay = QVBoxLayout(bar)
        lay.setContentsMargins(16, 20, 16, 16)
        lay.setSpacing(4)

        brand = QHBoxLayout()
        brand.setSpacing(10)
        logo = QLabel()
        logo.setPixmap(logo_pixmap(38))
        brand.addWidget(logo)
        brand.addWidget(brand_label(17))
        brand.addStretch(1)
        lay.addLayout(brand)
        tag = QLabel("Descarga y listo")
        tag.setObjectName("BrandTagline")
        tag.setContentsMargins(4, 2, 0, 18)
        lay.addWidget(tag)

        self.nav_group = QButtonGroup(self)
        self.nav_downloads = self._nav_button("⬇   Descargas", checkable=True)
        self.nav_history = self._nav_button("🕘   Historial", checkable=True)
        self.nav_group.addButton(self.nav_downloads, 0)
        self.nav_group.addButton(self.nav_history, 1)
        self.nav_group.idClicked.connect(self.show_page)
        nav_settings = self._nav_button("⚙   Ajustes")
        nav_settings.clicked.connect(self.open_settings)
        nav_about = self._nav_button("ⓘ   Acerca de")
        nav_about.clicked.connect(lambda: AboutDialog(self).exec())
        for b in (self.nav_downloads, self.nav_history, nav_settings, nav_about):
            lay.addWidget(b)
        lay.addStretch(1)

        shield = QLabel("🛡  Cada descarga se analiza contra virus y malware")
        shield.setObjectName("SidebarNote")
        shield.setWordWrap(True)
        lay.addWidget(shield)
        lay.addSpacing(10)
        coffee = QPushButton("☕  Invítame un café")
        coffee.setObjectName("Coffee")
        coffee.setCursor(Qt.PointingHandCursor)
        coffee.clicked.connect(lambda: CoffeeDialog(self).exec())
        lay.addWidget(coffee)
        lay.addSpacing(8)
        rights = QLabel(f"© {COPYRIGHT_YEAR} lliuya.pe\nTodos los derechos reservados")
        rights.setObjectName("SidebarNote")
        rights.setAlignment(Qt.AlignCenter)
        lay.addWidget(rights)
        return bar

    def _nav_button(self, text: str, checkable: bool = False) -> QPushButton:
        btn = QPushButton(text)
        btn.setObjectName("NavButton")
        btn.setCheckable(checkable)
        btn.setCursor(Qt.PointingHandCursor)
        return btn

    def show_page(self, index: int) -> None:
        self.pages.setCurrentIndex(index)
        (self.nav_downloads if index == 0 else self.nav_history).setChecked(True)
        self.page_title.setText("Descargas" if index == 0 else "Historial")
        if index == 1:
            self.refresh_history()

    def _url_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("Card")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(10)
        row = QHBoxLayout()
        row.setSpacing(10)
        self.url_input = QLineEdit()
        self.url_input.setObjectName("UrlInput")
        self.url_input.setPlaceholderText("Pega aquí el enlace del video, playlist o perfil (uno o varios)…")
        self.url_input.setClearButtonEnabled(True)
        self.url_input.returnPressed.connect(self.start_from_input)
        paste = QPushButton("📋  Pegar")
        paste.setCursor(Qt.PointingHandCursor)
        paste.clicked.connect(self.paste_and_start)
        self.btn_download = QPushButton("⬇  Descargar")
        self.btn_download.setObjectName("Primary")
        self.btn_download.setCursor(Qt.PointingHandCursor)
        self.btn_download.clicked.connect(self.start_from_input)
        row.addWidget(self.url_input, 1)
        row.addWidget(paste)
        row.addWidget(self.btn_download)
        lay.addLayout(row)
        chips = QHBoxLayout()
        chips.setSpacing(6)
        for name in ("YouTube", "Facebook", "Reels", "Instagram", "TikTok", "Vimeo", "X",
                     "Twitch", "+1.800 sitios"):
            chip = QLabel(name)
            chip.setObjectName("Badge")
            chips.addWidget(chip)
        chips.addStretch(1)
        lay.addLayout(chips)
        return card

    def _downloads_tab(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 4, 0, 0)
        lay.setSpacing(10)
        tools = QHBoxLayout()
        self.lbl_counts = QLabel("")
        self.lbl_counts.setProperty("muted", True)
        tools.addWidget(self.lbl_counts, 1)
        clear = QPushButton("Limpiar terminadas")
        clear.setObjectName("Small")
        clear.clicked.connect(self.clear_finished)
        open_dir = QPushButton("📂  Abrir carpeta de descargas")
        open_dir.setObjectName("Small")
        open_dir.clicked.connect(lambda: self._open_folder(Path(self.settings.download_dir)))
        tools.addWidget(clear)
        tools.addWidget(open_dir)
        lay.addLayout(tools)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        holder = QWidget()
        self.list_layout = QVBoxLayout(holder)
        self.list_layout.setContentsMargins(0, 0, 6, 0)
        self.list_layout.setSpacing(10)
        self.empty_state = QLabel(
            "Aún no hay descargas.\n\nCopia el enlace de un video o playlist y presiona «Pegar».\n"
            "Podrás elegir entre video o solo audio y la calidad antes de descargar.")
        self.empty_state.setObjectName("EmptyState")
        self.empty_state.setAlignment(Qt.AlignCenter)
        self.list_layout.addWidget(self.empty_state, 1)
        self.list_layout.addStretch(1)
        scroll.setWidget(holder)
        lay.addWidget(scroll, 1)
        return page

    def _history_tab(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 10, 0, 0)
        lay.setSpacing(10)
        row = QHBoxLayout()
        self.history_search = QLineEdit()
        self.history_search.setPlaceholderText("🔎  Buscar por título, plataforma o enlace…")
        self.history_search.textChanged.connect(lambda _t: self.refresh_history())
        row.addWidget(self.history_search, 1)
        clear = QPushButton("Borrar historial")
        clear.setObjectName("Small")
        clear.clicked.connect(self._clear_history)
        row.addWidget(clear)
        lay.addLayout(row)
        self.history = QTableWidget(0, 7)
        self.history.setHorizontalHeaderLabels(
            ["Fecha", "Título", "Plataforma", "Calidad", "Tamaño", "Seguridad", "Estado"])
        self.history.verticalHeader().hide()
        self.history.setAlternatingRowColors(True)
        self.history.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.history.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.history.setShowGrid(False)
        header = self.history.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        self.history.doubleClicked.connect(self._history_open)
        lay.addWidget(self.history, 1)
        hint = QLabel("Doble clic para abrir la carpeta del archivo.")
        hint.setProperty("muted", True)
        lay.addWidget(hint)
        return page

    # -- entrada de enlaces ------------------------------------------------------
    def _show_ready_message(self) -> None:
        if not find_ffmpeg_dir():
            self.statusBar().showMessage(
                "⚠ No se encontró FFmpeg: las descargas en alta calidad y las conversiones de audio no funcionarán.")
        else:
            self.statusBar().showMessage("Listo para descargar.", 4000)

    def paste_and_start(self) -> None:
        text = QGuiApplication.clipboard().text()
        if not extract_urls(text):
            self.statusBar().showMessage("El portapapeles no contiene ningún enlace.", 4000)
            return
        self.url_input.setText(text.strip().replace("\n", " "))
        self.start_from_input()

    def _paste_shortcut(self) -> None:
        if self.url_input.hasFocus():
            self.url_input.paste()
        else:
            self.paste_and_start()

    def start_from_input(self) -> None:
        urls = extract_urls(self.url_input.text())
        if not urls:
            self.statusBar().showMessage("Escribe o pega un enlace que empiece con http:// o https://", 5000)
            return
        self.url_input.clear()
        for url in urls:
            self.analyze_url(url)

    def _clipboard_changed(self) -> None:
        if not self.settings.clipboard_watch:
            return
        urls = extract_urls(QGuiApplication.clipboard().text())
        if not urls or urls[0] == self._last_clip:
            return
        self._last_clip = urls[0]
        if not self.url_input.text().strip():
            self.url_input.setText(" ".join(urls))
            self.statusBar().showMessage("🔗 Enlace detectado en el portapapeles. Presiona «Descargar».", 6000)

    def analyze_url(self, url: str) -> None:
        if policy.is_paid_url(url):
            self._warn_blocked(policy.PAID_MESSAGE)
            return
        token = uuid.uuid4().hex
        card = AnalyzingItem(url)
        self._insert_card(card)
        worker = AnalyzeWorker(token, url, self.settings.cookies_browser)
        worker.setAutoDelete(False)
        worker.signals.finished.connect(self._analysis_done)
        worker.signals.failed.connect(self._analysis_failed)
        self.analyzing[token] = (worker, card)
        self.analyze_pool.start(worker)

    def _pop_analysis(self, token: str) -> None:
        worker, card = self.analyzing.pop(token, (None, None))
        if card is not None:
            card.setParent(None)
            card.deleteLater()
        self._update_counts()

    def _analysis_failed(self, token: str, message: str, blocked: bool) -> None:
        self._pop_analysis(token)
        if blocked:
            self._warn_blocked(message)
        else:
            QMessageBox.warning(self, "No se pudo analizar el enlace", message)

    def _warn_blocked(self, message: str) -> None:
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Warning)
        box.setWindowTitle("Contenido no permitido")
        box.setText("🚫  " + message)
        box.exec()

    def _analysis_done(self, token: str, info: MediaInfo) -> None:
        self._pop_analysis(token)
        last = self.settings.last_choice
        if self.settings.quick_mode and last and not info.is_playlist:
            req = DownloadRequest.from_choice(
                last, url=info.url, title=info.title, platform=info.platform,
                dest_dir=self.settings.download_dir, thumbnail=info.thumbnail)
            if req.kind == "video":
                req.subtitles = [s for s in req.subtitles if s in info.subtitles]
            self.enqueue([req])
            return
        dialog = OptionsDialog(info, self.settings, self)
        if dialog.exec():
            self.enqueue(dialog.requests, batch=info.is_playlist)

    # -- cola de descargas -------------------------------------------------------
    def enqueue(self, requests: list[DownloadRequest], batch: bool = False) -> None:
        added = 0
        for index, req in enumerate(requests):
            previous = self.library.find_completed(req.url, req.quality_key)
            if previous and not batch:
                answer = QMessageBox.question(
                    self, "Ya lo descargaste",
                    f"«{req.title}» ya se descargó con esta misma calidad:\n{previous.filepath}\n\n"
                    "¿Quieres descargarlo de nuevo?")
                if answer != QMessageBox.Yes:
                    continue
            elif previous and batch:
                continue  # en listas se omiten los ya descargados (descarga incremental)
            item = DownloadItem(req)
            item.pause_requested.connect(self.pause_job)
            item.resume_requested.connect(self.resume_job)
            item.cancel_requested.connect(self.cancel_job)
            item.remove_requested.connect(self.remove_item)
            item.open_folder_requested.connect(self.open_item_folder)
            item.release_requested.connect(self.release_item)
            item.report_requested.connect(self.show_report)
            self.items[req.job_id] = item
            self._insert_card(item)
            delay = self.settings.sleep_between if batch and added > 0 else 0
            self._start_worker(req, delay)
            added += 1
        skipped = len(requests) - added
        if batch and skipped:
            self.statusBar().showMessage(
                f"{added} en cola · {skipped} omitidos porque ya estaban descargados.", 8000)
        self.show_page(0)
        self._update_counts()

    def _job_settings(self, delay: float = 0) -> JobSettings:
        s = self.settings
        return JobSettings(
            ffmpeg_dir=find_ffmpeg_dir(),
            cookies_browser=s.cookies_browser,
            rate_limit_kb=s.rate_limit_kb,
            subfolder_per_platform=s.subfolder_per_platform,
            antivirus_enabled=s.antivirus_enabled,
            virustotal_key=s.virustotal_key if s.virustotal_enabled else "",
            threat_action=s.threat_action,
            start_delay=delay,
        )

    def _start_worker(self, req: DownloadRequest, delay: float = 0) -> None:
        job = DownloadJob(req, self._job_settings(delay))
        worker = DownloadWorker(job)
        worker.setAutoDelete(False)
        worker.signals.progress.connect(self._job_progress)
        worker.signals.finished.connect(self._job_finished)
        self.workers[req.job_id] = worker
        self.items[req.job_id].set_queued()
        self.download_pool.start(worker)

    def _insert_card(self, card: QWidget) -> None:
        self.empty_state.hide()
        self.list_layout.insertWidget(0, card)

    def _job_progress(self, job_id: str, data: dict) -> None:
        item = self.items.get(job_id)
        if item:
            item.update_progress(data)

    def _job_finished(self, job_id: str, result: JobResult) -> None:
        self.workers.pop(job_id, None)
        item = self.items.get(job_id)
        if not item:
            return
        item.set_result(result)
        req = item.request
        if result.status not in (STATUS_PAUSED, STATUS_CANCELLED):
            filepath = result.files[0] if result.files else (result.held_files[0] if result.held_files else "")
            self.library.add(
                job_id=job_id, url=req.url, title=req.title, platform=req.platform, kind=req.kind,
                quality=req.quality_label, quality_key=req.quality_key, filepath=filepath,
                size=result.total_size, status=result.status,
                verdict=result.verdict if result.reports else "")
        if result.status == STATUS_DONE:
            self.statusBar().showMessage(f"✅ «{req.title}» descargado y verificado.", 6000)
        self._update_counts()

    def pause_job(self, job_id: str) -> None:
        worker = self.workers.get(job_id)
        if worker:
            worker.job.pause()
            self.items[job_id].status.setText("Pausando…")

    def resume_job(self, job_id: str) -> None:
        item = self.items.get(job_id)
        if item and job_id not in self.workers:
            self._start_worker(item.request)

    def cancel_job(self, job_id: str) -> None:
        worker = self.workers.get(job_id)
        item = self.items.get(job_id)
        if worker:
            worker.job.cancel()
            if item:
                item.status.setText("Cancelando…")
        elif item:  # en pausa: limpiar archivos parciales
            DownloadJob(item.request, self._job_settings()).cleanup()
            item.set_result(JobResult(STATUS_CANCELLED))

    def remove_item(self, job_id: str) -> None:
        if job_id in self.workers:
            return
        item = self.items.pop(job_id, None)
        if item:
            item.setParent(None)
            item.deleteLater()
        self._update_counts()

    def clear_finished(self) -> None:
        for job_id in [j for j, it in self.items.items() if it.finished and j not in self.workers]:
            self.remove_item(job_id)

    def open_item_folder(self, job_id: str) -> None:
        item = self.items.get(job_id)
        if item and item.result and item.result.files:
            self._open_folder(Path(item.result.files[0]).parent)

    def release_item(self, job_id: str) -> None:
        item = self.items.get(job_id)
        if not item or not item.result:
            return
        answer = QMessageBox.warning(
            self, "Entregar archivo sospechoso",
            "El análisis de seguridad no fue concluyente para este archivo.\n\n"
            "¿Seguro que quieres moverlo a tu carpeta de descargas?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if answer != QMessageBox.Yes:
            return
        moved = release_from_quarantine(item.result.held_files, item.request,
                                        self.settings.subfolder_per_platform)
        item.result.files = moved
        item.result.held_files = []
        item.set_released(moved)

    def show_report(self, job_id: str) -> None:
        item = self.items.get(job_id)
        if not item or not item.result or not item.result.reports:
            return
        text = "\n\n".join(r.summary() for r in item.result.reports)
        box = QMessageBox(self)
        box.setWindowTitle("Informe de seguridad")
        box.setText(f"🛡  Resultado: {VERDICT_LABELS[item.result.verdict]}")
        box.setDetailedText(text)
        box.setInformativeText("\n".join(
            f"{Path(r.path).name}: {VERDICT_LABELS[r.verdict]}" for r in item.result.reports))
        box.exec()

    def _update_counts(self) -> None:
        active = len(self.workers)
        total = len(self.items)
        done = sum(1 for it in self.items.values() if it.result and it.result.status == STATUS_DONE)
        analyzing = len(self.analyzing)
        bits = [f"{total} en la lista", f"{active} activas", f"{done} completadas"]
        if analyzing:
            bits.append(f"{analyzing} analizando")
        self.lbl_counts.setText("  ·  ".join(bits))
        self.empty_state.setVisible(total == 0 and analyzing == 0)

    # -- historial -------------------------------------------------------------
    def refresh_history(self) -> None:
        rows = self.library.search(self.history_search.text())
        self.history.setRowCount(len(rows))
        for r, row in enumerate(rows):
            values = [
                row.created_at.replace("T", " ")[:16], row.title, row.platform, row.quality,
                human_size(row.size), VERDICT_LABELS.get(row.verdict, "—"),
                _STATUS_TEXT.get(row.status, row.status),
            ]
            for c, value in enumerate(values):
                cell = QTableWidgetItem(value)
                if c == 1:
                    cell.setToolTip(f"{row.title}\n{row.url}\n{row.filepath}")
                    cell.setData(Qt.UserRole, row.filepath)
                self.history.setItem(r, c, cell)

    def _history_open(self, index) -> None:
        cell = self.history.item(index.row(), 1)
        path = Path(cell.data(Qt.UserRole) or "") if cell else None
        if path and path.exists():
            self._open_folder(path.parent)
        else:
            self.statusBar().showMessage("El archivo ya no existe en su ubicación original.", 5000)

    def _clear_history(self) -> None:
        if QMessageBox.question(self, "Borrar historial",
                                "¿Borrar todo el historial? Tus archivos descargados no se eliminan.") == QMessageBox.Yes:
            self.library.clear()
            self.refresh_history()

    # -- varios ------------------------------------------------------------------
    def _open_folder(self, folder: Path) -> None:
        folder.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def open_settings(self) -> None:
        if SettingsDialog(self.settings, self).exec():
            self.download_pool.setMaxThreadCount(self.settings.max_concurrent)
            self.statusBar().showMessage("Ajustes guardados.", 3000)

    def closeEvent(self, event) -> None:  # noqa: N802
        if self.workers:
            answer = QMessageBox.question(
                self, "Descargas en curso",
                f"Hay {len(self.workers)} descarga(s) en curso. ¿Salir de todos modos?\n"
                "Las descargas sin terminar se cancelarán.")
            if answer != QMessageBox.Yes:
                event.ignore()
                return
            for worker in list(self.workers.values()):
                worker.job.cancel()
            self.download_pool.waitForDone(5000)
        self.analyze_pool.clear()
        self.library.close()
        event.accept()
