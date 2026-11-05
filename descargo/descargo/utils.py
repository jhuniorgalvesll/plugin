"""Utilidades generales: rutas, formatos legibles, subprocesos."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = PACKAGE_DIR / "assets"
BUNDLED_BIN_DIR = PACKAGE_DIR / "bin"

IS_WINDOWS = sys.platform.startswith("win")
IS_MAC = sys.platform == "darwin"

_URL_RE = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)


def extract_urls(text: str) -> list[str]:
    """Devuelve los enlaces http(s) encontrados en un texto, sin duplicados."""
    seen: list[str] = []
    for match in _URL_RE.findall(text or ""):
        url = match.rstrip(").,;]")
        if url not in seen:
            seen.append(url)
    return seen


def human_size(num: float | int | None) -> str:
    if not num or num <= 0:
        return "—"
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(num)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            if unit in ("B", "KB"):
                return f"{value:.0f} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024
    return "—"


def human_speed(bps: float | None) -> str:
    if not bps:
        return ""
    return f"{human_size(bps)}/s"


def human_duration(seconds: float | int | None) -> str:
    if seconds is None:
        return "—"
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def app_data_dir() -> Path:
    """Carpeta de datos de la aplicación (ajustes, historial, cuarentena)."""
    if IS_WINDOWS:
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
        path = base / "DescarGO"
    elif IS_MAC:
        path = Path.home() / "Library" / "Application Support" / "DescarGO"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
        path = base / "descargo"
    path.mkdir(parents=True, exist_ok=True)
    return path


def quarantine_dir() -> Path:
    path = app_data_dir() / "cuarentena"
    path.mkdir(parents=True, exist_ok=True)
    return path


def default_download_dir() -> Path:
    home = Path.home()
    for candidate in ("Videos", "Vídeos", "Downloads", "Descargas"):
        if (home / candidate).is_dir():
            return home / candidate / "DescarGO"
    return home / "DescarGO"


def find_ffmpeg_dir() -> str | None:
    """Carpeta que contiene ffmpeg: primero la incluida con la app, luego el PATH."""
    exe = "ffmpeg.exe" if IS_WINDOWS else "ffmpeg"
    if (BUNDLED_BIN_DIR / exe).is_file():
        return str(BUNDLED_BIN_DIR)
    found = shutil.which("ffmpeg")
    return str(Path(found).parent) if found else None


def find_ffprobe() -> str | None:
    exe = "ffprobe.exe" if IS_WINDOWS else "ffprobe"
    if (BUNDLED_BIN_DIR / exe).is_file():
        return str(BUNDLED_BIN_DIR / exe)
    return shutil.which("ffprobe")


def subprocess_flags() -> dict:
    """Evita que aparezcan ventanas de consola en Windows."""
    if IS_WINDOWS:
        return {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)}
    return {}


def unique_path(path: Path) -> Path:
    """Si el archivo ya existe, agrega (1), (2)… al nombre."""
    if not path.exists():
        return path
    counter = 1
    while True:
        candidate = path.with_name(f"{path.stem} ({counter}){path.suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


_INVALID_FS_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def safe_folder_name(name: str) -> str:
    cleaned = _INVALID_FS_CHARS.sub("_", name or "").strip(" .")
    return cleaned or "Otros"
