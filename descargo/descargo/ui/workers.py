"""Tareas en segundo plano (análisis y descargas) para no congelar la interfaz."""

from __future__ import annotations

from PySide6.QtCore import QObject, QRunnable, Signal

from ..core import analyzer, policy
from ..core.downloader import DownloadJob, JobResult, STATUS_ERROR


class AnalyzeSignals(QObject):
    finished = Signal(str, object)   # token, MediaInfo
    failed = Signal(str, str, bool)  # token, mensaje, bloqueado


class AnalyzeWorker(QRunnable):
    def __init__(self, token: str, url: str, cookies_browser: str = ""):
        super().__init__()
        self.token = token
        self.url = url
        self.cookies_browser = cookies_browser
        self.signals = AnalyzeSignals()

    def run(self) -> None:
        try:
            info = analyzer.analyze(self.url, cookies_browser=self.cookies_browser)
        except policy.BlockedContentError as exc:
            self.signals.failed.emit(self.token, str(exc), True)
        except analyzer.AnalysisError as exc:
            self.signals.failed.emit(self.token, str(exc), False)
        except Exception as exc:  # nunca dejar caer el hilo
            self.signals.failed.emit(self.token, analyzer.friendly_error(str(exc)), False)
        else:
            self.signals.finished.emit(self.token, info)


class DownloadSignals(QObject):
    progress = Signal(str, dict)       # job_id, datos
    finished = Signal(str, object)     # job_id, JobResult


class DownloadWorker(QRunnable):
    def __init__(self, job: DownloadJob):
        super().__init__()
        self.job = job
        self.signals = DownloadSignals()
        job.on_progress = lambda data: self.signals.progress.emit(job.request.job_id, data)

    def run(self) -> None:
        try:
            result = self.job.run()
        except Exception as exc:
            result = JobResult(STATUS_ERROR, message=analyzer.friendly_error(str(exc)))
        self.signals.finished.emit(self.job.request.job_id, result)


class TaskSignals(QObject):
    finished = Signal(object)
    failed = Signal(str)
    progress = Signal(object, object)


class TaskWorker(QRunnable):
    """Ejecuta una función en segundo plano. Si acepta «progress», recibe un callback."""

    def __init__(self, fn, *args, with_progress: bool = False):
        super().__init__()
        self.fn = fn
        self.args = args
        self.with_progress = with_progress
        self.signals = TaskSignals()

    def run(self) -> None:
        try:
            if self.with_progress:
                result = self.fn(*self.args, progress=lambda d, t: self.signals.progress.emit(d, t))
            else:
                result = self.fn(*self.args)
        except Exception as exc:
            self.signals.failed.emit(str(exc))
        else:
            self.signals.finished.emit(result)
