"""Ejecución de una descarga: cuarentena → análisis de seguridad → carpeta final.

No depende de Qt; la interfaz lo usa a través de callbacks.
"""

from __future__ import annotations

import copy
import shutil
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from ..utils import quarantine_dir, safe_folder_name, unique_path
from . import policy
from .analyzer import friendly_error
from .formats import build_ydl_options
from .models import DownloadRequest
from .security import (CLEAN, MEDIA_EXTS, SUSPICIOUS, THREAT, ScanReport,
                       SecurityScanner, worst_verdict)

# Archivos temporales del motor que nunca se entregan al usuario.
_TEMP_SUFFIXES = (".part", ".ytdl", ".temp", ".tmp")
# Miniaturas sueltas (la portada ya va incrustada): se descartan, nunca se entregan.
_IMAGE_SUFFIXES = (".jpg", ".jpeg", ".png", ".webp", ".gif")

STATUS_DONE = "done"
STATUS_SUSPICIOUS = "suspicious"
STATUS_THREAT = "threat"
STATUS_PAUSED = "paused"
STATUS_CANCELLED = "cancelled"
STATUS_ERROR = "error"
STATUS_BLOCKED = "blocked"


class _Stop(Exception):
    pass


@dataclass
class JobResult:
    status: str
    files: list[str] = field(default_factory=list)          # entregados al usuario
    held_files: list[str] = field(default_factory=list)     # retenidos en cuarentena
    reports: list[ScanReport] = field(default_factory=list)
    message: str = ""
    total_size: int = 0

    @property
    def verdict(self) -> str:
        return worst_verdict([r.verdict for r in self.reports]) if self.reports else CLEAN


@dataclass
class JobSettings:
    ffmpeg_dir: str | None = None
    cookies_browser: str = ""
    rate_limit_kb: int = 0
    subfolder_per_platform: bool = True
    antivirus_enabled: bool = True
    virustotal_key: str = ""
    threat_action: str = "delete"
    start_delay: float = 0.0  # pausa antes de empezar (elementos de una lista)
    embed_thumbnail: bool = True  # portada incrustada en MP3/M4A/MP4…


ProgressCb = Callable[[dict], None]


class DownloadJob:
    def __init__(self, request: DownloadRequest, settings: JobSettings,
                 on_progress: ProgressCb | None = None,
                 scanner: SecurityScanner | None = None):
        self.request = request
        self.settings = settings
        self.on_progress = on_progress or (lambda _d: None)
        self.scanner = scanner
        self._stop_mode: str | None = None  # "pause" | "cancel"
        self._lock = threading.Lock()
        self._last_emit = 0.0
        self.workdir = quarantine_dir() / request.job_id

    # -- control -----------------------------------------------------------
    def pause(self) -> None:
        with self._lock:
            self._stop_mode = self._stop_mode or "pause"

    def cancel(self) -> None:
        with self._lock:
            self._stop_mode = "cancel"

    @property
    def stop_requested(self) -> str | None:
        with self._lock:
            return self._stop_mode

    # -- hooks de yt-dlp ---------------------------------------------------
    def _progress_hook(self, d: dict) -> None:
        if self.stop_requested:
            import yt_dlp
            raise yt_dlp.utils.DownloadCancelled("detenido por el usuario")
        status = d.get("status")
        now = time.monotonic()
        if status == "downloading" and now - self._last_emit < 0.25:
            return
        self._last_emit = now
        info = d.get("info_dict") or {}
        part = "audio" if info.get("vcodec") == "none" else "video"
        total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
        done = d.get("downloaded_bytes") or 0
        self.on_progress({
            "phase": "download" if status == "downloading" else "downloaded",
            "part": part,
            "percent": (done / total * 100) if total else None,
            "downloaded": done,
            "total": total,
            "speed": d.get("speed"),
            "eta": d.get("eta"),
        })

    def _pp_hook(self, d: dict) -> None:
        if d.get("status") == "started":
            self.on_progress({"phase": "processing", "name": d.get("postprocessor", "")})

    # -- ejecución -----------------------------------------------------------
    def run(self) -> JobResult:
        req = self.request
        try:
            policy.check_url(req.url)
        except policy.BlockedContentError as exc:
            return JobResult(STATUS_BLOCKED, message=str(exc))
        if self.settings.start_delay > 0:
            self.on_progress({"phase": "waiting", "seconds": self.settings.start_delay})
            deadline = time.monotonic() + self.settings.start_delay
            while time.monotonic() < deadline and not self.stop_requested:
                time.sleep(0.2)
        if self.stop_requested:
            return self._stopped()

        self.workdir.mkdir(parents=True, exist_ok=True)
        self.on_progress({"phase": "starting"})
        import yt_dlp

        cover = self.settings.embed_thumbnail
        prefetched = self.request.prefetched_info
        while True:
            try:
                self._download(cover, prefetched)
            except policy.BlockedContentError as exc:
                self.cleanup()
                return JobResult(STATUS_BLOCKED, message=str(exc))
            except yt_dlp.utils.DownloadCancelled:
                return self._stopped()
            except Exception as exc:
                if self.stop_requested:
                    return self._stopped()
                if prefetched is not None:
                    # los datos del análisis pudieron caducar: se consultan de nuevo
                    prefetched = None
                    self.request.prefetched_info = None
                    self.cleanup()
                    self.workdir.mkdir(parents=True, exist_ok=True)
                    continue
                if cover:
                    # la portada nunca debe arruinar una descarga: se repite una vez sin ella
                    # (formato sin soporte de carátula, miniatura rota o inaccesible…)
                    cover = False
                    self.cleanup()
                    self.workdir.mkdir(parents=True, exist_ok=True)
                    continue
                return self._handle_failure(friendly_error(str(exc)))
            break

        if self.stop_requested:
            return self._stopped()
        return self._scan_and_deliver()

    def _download(self, cover: bool, prefetched: dict | None = None) -> None:
        import yt_dlp
        opts = build_ydl_options(
            self.request, str(self.workdir),
            ffmpeg_dir=self.settings.ffmpeg_dir,
            cookies_browser=self.settings.cookies_browser,
            rate_limit_kb=self.settings.rate_limit_kb,
            embed_thumbnail=cover,
            progress_hook=self._progress_hook,
            postprocessor_hook=self._pp_hook,
        )
        with yt_dlp.YoutubeDL(opts) as ydl:
            if prefetched is not None:
                info = copy.deepcopy(prefetched)  # sin repetir el análisis: más rápido
            else:
                info = ydl.extract_info(self.request.url, download=False)
            policy.check_info(ydl.sanitize_info(info) or {})
            if self.stop_requested:
                raise yt_dlp.utils.DownloadCancelled("detenido")
            ydl.process_ie_result(info, download=True)

    def _handle_failure(self, message: str) -> JobResult:
        """Si la descarga falla, igual se analiza lo que llegó: nunca queda un archivo sin revisar."""
        files = self._collect_files()
        if files:
            scanned = self._scan_and_deliver()
            if scanned.status == STATUS_THREAT:
                return scanned
            # no es amenaza pero la descarga quedó incompleta: no se entrega nada a medias
            for f in scanned.files:
                Path(f).unlink(missing_ok=True)
        self.cleanup()
        return JobResult(STATUS_ERROR, message=message)

    def _stopped(self) -> JobResult:
        if self.stop_requested == "cancel":
            self.cleanup()
            return JobResult(STATUS_CANCELLED)
        return JobResult(STATUS_PAUSED)

    def _collect_files(self) -> list[Path]:
        files = []
        for p in sorted(self.workdir.iterdir()) if self.workdir.exists() else []:
            if not p.is_file() or p.name.endswith(_TEMP_SUFFIXES):
                continue
            if p.suffix.lower() in _IMAGE_SUFFIXES:
                p.unlink(missing_ok=True)
                continue
            files.append(p)
        return files

    def _destination_dir(self) -> Path:
        base = Path(self.request.dest_dir).expanduser()
        if self.settings.subfolder_per_platform:
            base = base / safe_folder_name(self.request.platform)
        base.mkdir(parents=True, exist_ok=True)
        return base

    def _scan_and_deliver(self) -> JobResult:
        files = self._collect_files()
        if not any(p.suffix.lower().lstrip(".") in MEDIA_EXTS for p in files):
            # puede haber restos no multimedia: se analizan igual para registrar la amenaza
            if not files:
                return JobResult(STATUS_ERROR, message="La descarga terminó sin generar ningún archivo.")

        scanner = self.scanner or SecurityScanner(
            antivirus_enabled=self.settings.antivirus_enabled,
            virustotal_key=self.settings.virustotal_key,
        )
        result = JobResult(STATUS_DONE)
        for index, path in enumerate(files, 1):
            self.on_progress({"phase": "scanning", "index": index, "count": len(files),
                              "name": path.name})
            report = scanner.scan(path)
            result.reports.append(report)

        dest = None
        threats_dir = quarantine_dir() / "_amenazas"
        for path, report in zip(files, result.reports):
            if report.verdict == CLEAN:
                dest = dest or self._destination_dir()
                target = unique_path(dest / path.name)
                shutil.move(str(path), str(target))
                result.files.append(str(target))
                result.total_size += target.stat().st_size
            elif report.verdict == THREAT:
                if self.settings.threat_action == "quarantine" and path.exists():
                    threats_dir.mkdir(parents=True, exist_ok=True)
                    target = unique_path(threats_dir / path.name)
                    shutil.move(str(path), str(target))
                    result.held_files.append(str(target))
                elif path.exists():
                    path.unlink()
            else:  # sospechoso: queda en cuarentena hasta que el usuario decida
                result.held_files.append(str(path))

        verdict = result.verdict
        if verdict == THREAT:
            result.status = STATUS_THREAT
            result.message = ("Se detectó una amenaza. "
                              + ("El archivo quedó aislado en cuarentena."
                                 if self.settings.threat_action == "quarantine"
                                 else "El archivo fue eliminado."))
        elif verdict == SUSPICIOUS:
            result.status = STATUS_SUSPICIOUS
            result.message = "El análisis no fue concluyente. El archivo quedó en cuarentena."
        elif not any(Path(f).suffix.lower().lstrip(".") in MEDIA_EXTS for f in result.files):
            result.status = STATUS_ERROR
            result.message = "La descarga no produjo ningún archivo de video o audio."
        if not result.held_files:
            self.cleanup()
        return result

    def cleanup(self) -> None:
        shutil.rmtree(self.workdir, ignore_errors=True)


def release_from_quarantine(held_files: list[str], request: DownloadRequest,
                            subfolder_per_platform: bool) -> list[str]:
    """El usuario decide entregar un archivo sospechoso (nunca una amenaza)."""
    base = Path(request.dest_dir).expanduser()
    if subfolder_per_platform:
        base = base / safe_folder_name(request.platform)
    base.mkdir(parents=True, exist_ok=True)
    moved = []
    for f in held_files:
        src = Path(f)
        if src.exists():
            target = unique_path(base / src.name)
            shutil.move(str(src), str(target))
            moved.append(str(target))
    workdir = quarantine_dir() / request.job_id
    if workdir.exists() and not any(workdir.iterdir()):
        workdir.rmdir()
    return moved
