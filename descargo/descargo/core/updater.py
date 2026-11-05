"""Actualizaciones: motor de descarga (yt-dlp) y la propia aplicación.

Motor: se descarga la última versión oficial de yt-dlp desde PyPI, se verifica
su huella SHA-256 publicada y se extrae en la carpeta de datos. Al iniciar,
DescarGO usa esa copia si es más nueva que la incluida en el instalador.

Aplicación: se consultan las versiones publicadas en GitHub Releases
(etiquetas «descargo-vX.Y.Z»). El instalador se descarga y se verifica con su
archivo .sha256 antes de ejecutarse.
"""

from __future__ import annotations

import hashlib
import importlib.abc
import importlib.machinery
import json
import re
import shutil
import sys
import tempfile
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .. import APP_VERSION
from ..utils import app_data_dir

PYPI_URL = "https://pypi.org/pypi/yt-dlp/json"
GITHUB_REPO = "jhuniorgalvesll/plugin"
RELEASES_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases?per_page=30"
RELEASES_PAGE = f"https://github.com/{GITHUB_REPO}/releases"
TAG_PREFIX = "descargo-v"
USER_AGENT = f"DescarGO/{APP_VERSION}"

ProgressCb = Callable[[int, int], None]


class UpdateError(Exception):
    pass


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def parse_version(text: str) -> tuple[int, ...]:
    """'2026.10.26' → (2026, 10, 26); 'v1.2.0' → (1, 2, 0). Ignora sufijos."""
    nums = re.findall(r"\d+", (text or "").split("+")[0])
    return tuple(int(n) for n in nums[:4]) or (0,)


def is_newer(candidate: str, current: str) -> bool:
    return parse_version(candidate) > parse_version(current)


def _get_json(url: str, timeout: int = 20) -> object:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT,
                                               "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as exc:  # red, HTTP, JSON
        raise UpdateError(f"No se pudo consultar {url.split('/')[2]}: {exc}") from exc


def _download(url: str, dest: Path, expected_sha256: str | None,
              progress: ProgressCb | None = None, timeout: int = 60) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    digest = hashlib.sha256()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp, open(dest, "wb") as fh:
            total = int(resp.headers.get("Content-Length") or 0)
            done = 0
            while chunk := resp.read(256 * 1024):
                fh.write(chunk)
                digest.update(chunk)
                done += len(chunk)
                if progress:
                    progress(done, total)
    except Exception as exc:
        dest.unlink(missing_ok=True)
        raise UpdateError(f"La descarga falló: {exc}") from exc
    if expected_sha256 and digest.hexdigest().lower() != expected_sha256.lower():
        dest.unlink(missing_ok=True)
        raise UpdateError("La huella SHA-256 no coincide: el archivo fue rechazado por seguridad.")


# ---------------------------------------------------------------------------
# Motor de descarga (yt-dlp)
# ---------------------------------------------------------------------------

def engine_dir() -> Path:
    path = app_data_dir() / "motor"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _engine_state() -> dict:
    try:
        return json.loads((engine_dir() / "estado.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def bundled_engine_version() -> str:
    try:
        from importlib.metadata import version
        return version("yt-dlp")
    except Exception:
        return "0"


class _EngineFinder(importlib.abc.MetaPathFinder):
    """Hace que «import yt_dlp» use la copia actualizada antes que la incluida."""

    def __init__(self, root: Path):
        self.root = str(root)

    def find_spec(self, name, path=None, target=None):
        if name == "yt_dlp":
            return importlib.machinery.PathFinder.find_spec(name, [self.root])
        if name.startswith("yt_dlp.") and path:
            return importlib.machinery.PathFinder.find_spec(name, path)
        return None


_active_engine: dict = {"version": None, "source": "incluido"}


def activate_engine() -> None:
    """Llamar al iniciar, antes de importar yt_dlp."""
    state = _engine_state()
    folder = engine_dir() / str(state.get("folder", ""))
    version = str(state.get("version", ""))
    if not version or not (folder / "yt_dlp" / "__init__.py").is_file():
        return
    if not is_newer(version, bundled_engine_version()):
        return  # la app trae una versión igual o más nueva
    if "yt_dlp" in sys.modules:
        return
    sys.meta_path.insert(0, _EngineFinder(folder))
    _active_engine.update(version=version, source="actualizado")


def current_engine_version() -> str:
    try:
        import yt_dlp.version
        return yt_dlp.version.__version__
    except Exception:
        return bundled_engine_version()


def engine_source() -> str:
    return _active_engine["source"]


@dataclass
class EngineUpdate:
    version: str
    url: str
    sha256: str


def check_engine_update() -> EngineUpdate | None:
    data = _get_json(PYPI_URL)
    info = data.get("info", {}) if isinstance(data, dict) else {}
    latest = str(info.get("version", ""))
    installed = _engine_state().get("version") or "0"
    current = max(current_engine_version(), installed, key=parse_version)
    if not latest or not is_newer(latest, current):
        return None
    for f in data.get("urls", []):
        if f.get("packagetype") == "bdist_wheel" and f.get("filename", "").endswith("py3-none-any.whl"):
            return EngineUpdate(latest, f["url"], f.get("digests", {}).get("sha256", ""))
    raise UpdateError("No se encontró el paquete oficial del motor.")


def install_engine(update: EngineUpdate, progress: ProgressCb | None = None) -> str:
    if not update.sha256:
        raise UpdateError("El paquete no publica su huella SHA-256; no se instalará.")
    root = engine_dir()
    with tempfile.TemporaryDirectory(dir=root) as tmp:
        wheel = Path(tmp) / "motor.whl"
        _download(update.url, wheel, update.sha256, progress)
        target = root / f"yt-dlp-{update.version}"
        staging = Path(tmp) / "extraido"
        with zipfile.ZipFile(wheel) as zf:
            for member in zf.infolist():
                name = member.filename
                if not name.startswith("yt_dlp/") or ".." in Path(name).parts or name.startswith("/"):
                    continue  # solo el paquete, sin rutas peligrosas
                zf.extract(member, staging)
        if not (staging / "yt_dlp" / "__init__.py").is_file():
            raise UpdateError("El paquete del motor está incompleto.")
        shutil.rmtree(target, ignore_errors=True)
        shutil.move(str(staging), str(target))
    previous = _engine_state().get("folder")
    (root / "estado.json").write_text(json.dumps(
        {"version": update.version, "folder": target.name, "sha256": update.sha256}), encoding="utf-8")
    if previous and previous != target.name and previous != _active_folder():
        shutil.rmtree(root / previous, ignore_errors=True)
    return update.version


def _active_folder() -> str | None:
    for finder in sys.meta_path:
        if isinstance(finder, _EngineFinder):
            return Path(finder.root).name
    return None


# ---------------------------------------------------------------------------
# Aplicación (GitHub Releases)
# ---------------------------------------------------------------------------

@dataclass
class AppUpdate:
    version: str
    notes: str
    page_url: str
    installer_url: str
    installer_name: str
    sha256_url: str


def check_app_update(current: str = APP_VERSION) -> AppUpdate | None:
    releases = _get_json(RELEASES_URL)
    best: AppUpdate | None = None
    for rel in releases if isinstance(releases, list) else []:
        tag = str(rel.get("tag_name", ""))
        if rel.get("draft") or rel.get("prerelease") or not tag.startswith(TAG_PREFIX):
            continue
        version = tag[len(TAG_PREFIX):]
        if not is_newer(version, current) or (best and not is_newer(version, best.version)):
            continue
        assets = {a.get("name", ""): a.get("browser_download_url", "") for a in rel.get("assets", [])}
        exe = next((n for n in assets if n.lower().endswith(".exe") and "setup" in n.lower()), "")
        best = AppUpdate(
            version=version,
            notes=str(rel.get("body") or "").strip(),
            page_url=str(rel.get("html_url") or RELEASES_PAGE),
            installer_url=assets.get(exe, ""),
            installer_name=exe,
            sha256_url=assets.get(exe + ".sha256", ""),
        )
    return best


def download_installer(update: AppUpdate, progress: ProgressCb | None = None) -> Path:
    if not update.installer_url or not update.sha256_url:
        raise UpdateError("Esta versión no tiene instalador verificable; descárgala desde la página.")
    req = urllib.request.Request(update.sha256_url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            expected = resp.read().decode("utf-8", "replace").split()[0].strip()
    except Exception as exc:
        raise UpdateError(f"No se pudo obtener la huella del instalador: {exc}") from exc
    if not re.fullmatch(r"[0-9a-fA-F]{64}", expected):
        raise UpdateError("La huella del instalador no es válida.")
    folder = app_data_dir() / "actualizaciones"
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / Path(update.installer_name).name
    _download(update.installer_url, dest, expected, progress, timeout=120)
    return dest
