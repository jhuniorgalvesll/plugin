"""Ajustes del usuario, guardados en JSON dentro de la carpeta de datos."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

from .utils import app_data_dir, default_download_dir

COOKIE_BROWSERS = {
    "": "No usar (solo contenido público)",
    "chrome": "Google Chrome",
    "edge": "Microsoft Edge",
    "firefox": "Mozilla Firefox",
    "brave": "Brave",
    "opera": "Opera",
    "safari": "Safari",
}


@dataclass
class Settings:
    # General
    download_dir: str = field(default_factory=lambda: str(default_download_dir()))
    subfolder_per_platform: bool = True
    quick_mode: bool = False
    last_choice: dict = field(default_factory=dict)
    clipboard_watch: bool = True
    accepted_terms: bool = False

    # Red (respeto a las plataformas)
    max_concurrent: int = 3
    rate_limit_kb: int = 0  # 0 = sin límite de velocidad
    sleep_between: int = 2  # segundos entre elementos de una lista
    cookies_browser: str = ""

    # Seguridad (las capas 1–3 siempre están activas y no se configuran)
    antivirus_enabled: bool = True
    virustotal_enabled: bool = False
    virustotal_key: str = ""
    threat_action: str = "delete"  # "delete" | "quarantine"

    _path: Path | None = field(default=None, repr=False, compare=False)

    @classmethod
    def load(cls, path: Path | None = None) -> "Settings":
        path = path or app_data_dir() / "ajustes.json"
        settings = cls()
        if path.is_file():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                data = {}
            valid = {f.name: f for f in fields(cls) if not f.name.startswith("_")}
            for key, value in data.items():
                if key in valid:
                    default = getattr(settings, key)
                    if default is None or isinstance(value, type(default)):
                        setattr(settings, key, value)
        settings._path = path
        settings.normalize()
        return settings

    def normalize(self) -> None:
        self.max_concurrent = max(1, min(int(self.max_concurrent), 10))
        self.rate_limit_kb = max(0, int(self.rate_limit_kb))
        self.sleep_between = max(0, min(int(self.sleep_between), 60))
        if self.threat_action not in ("delete", "quarantine"):
            self.threat_action = "delete"
        if self.cookies_browser not in COOKIE_BROWSERS:
            self.cookies_browser = ""

    def save(self) -> None:
        self.normalize()
        path = self._path or app_data_dir() / "ajustes.json"
        data = {k: v for k, v in asdict(self).items() if not k.startswith("_")}
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)
