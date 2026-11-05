"""Análisis de seguridad de cada archivo descargado.

Capas (en orden):
  1. Verificación real del tipo de archivo (firma interna + ffprobe).
  2. Reglas de bloqueo (ejecutables, dobles extensiones, trucos Unicode).
  3. Comprobación de contenido de subtítulos (solo texto, sin scripts).
  4. Antivirus del sistema (Microsoft Defender / ClamAV).
  5. VirusTotal, opcional: solo se envía la huella SHA-256, nunca el archivo.

Las capas 1–3 siempre están activas.
"""

from __future__ import annotations

import glob
import hashlib
import json
import os
import shutil
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from ..utils import IS_WINDOWS, find_ffprobe, subprocess_flags

VIDEO_EXTS = {"mp4", "mkv", "webm", "mov", "m4v", "avi", "flv", "3gp", "ts", "mpg", "mpeg"}
AUDIO_EXTS = {"mp3", "m4a", "aac", "opus", "ogg", "oga", "flac", "wav", "weba", "mka"}
SUBTITLE_EXTS = {"srt", "vtt", "ass", "ssa", "lrc"}
MEDIA_EXTS = VIDEO_EXTS | AUDIO_EXTS
ALLOWED_EXTS = MEDIA_EXTS | SUBTITLE_EXTS

DANGEROUS_EXTS = {
    "exe", "com", "bat", "cmd", "scr", "pif", "msi", "msp", "dll", "cpl", "sys",
    "vbs", "vbe", "js", "jse", "wsf", "wsh", "hta", "ps1", "psm1", "lnk", "reg",
    "jar", "apk", "app", "dmg", "pkg", "sh", "bash", "run", "bin", "elf", "deb",
    "rpm", "appimage", "iso", "img", "vhd", "zip", "rar", "7z", "gz", "tar",
    "html", "htm", "svg", "pdf", "doc", "docm", "xls", "xlsm", "ppt", "pptm",
}

# Caracteres invisibles que permiten disfrazar extensiones (p. ej. "video‮4pm.exe").
BIDI_CHARS = {"\u202a", "\u202b", "\u202c", "\u202d", "\u202e", "\u2066", "\u2067",
              "\u2068", "\u2069", "\u200e", "\u200f"}

MAX_SUBTITLE_BYTES = 20 * 1024 * 1024

OK, WARN, FAIL, SKIP = "ok", "warn", "fail", "skip"
CLEAN, SUSPICIOUS, THREAT = "clean", "suspicious", "threat"

VERDICT_LABELS = {
    CLEAN: "✅ Seguro",
    SUSPICIOUS: "⚠️ Sospechoso",
    THREAT: "❌ Amenaza",
}


@dataclass
class CheckResult:
    name: str
    status: str
    detail: str = ""


@dataclass
class ScanReport:
    path: str
    verdict: str = CLEAN
    checks: list[CheckResult] = field(default_factory=list)
    sha256: str = ""

    def add(self, name: str, status: str, detail: str = "") -> None:
        self.checks.append(CheckResult(name, status, detail))

    def summary(self) -> str:
        icons = {OK: "✔", WARN: "!", FAIL: "✖", SKIP: "–"}
        lines = [f"Archivo: {Path(self.path).name}", f"Resultado: {VERDICT_LABELS[self.verdict]}"]
        if self.sha256:
            lines.append(f"SHA-256: {self.sha256}")
        lines.append("")
        for c in self.checks:
            lines.append(f" {icons.get(c.status, '?')} {c.name}: {c.detail}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Capa 1: tipo real del archivo
# ---------------------------------------------------------------------------

def sniff(header: bytes) -> tuple[str, str]:
    """Identifica el tipo real por su firma interna. Devuelve (categoría, etiqueta)."""
    h = header
    # Ejecutables y binarios peligrosos
    if h.startswith(b"MZ"):
        return "executable", "programa de Windows (.exe/.dll)"
    if h.startswith(b"\x7fELF"):
        return "executable", "programa de Linux (ELF)"
    if h[:4] in (b"\xcf\xfa\xed\xfe", b"\xce\xfa\xed\xfe", b"\xfe\xed\xfa\xce",
                 b"\xfe\xed\xfa\xcf", b"\xca\xfe\xba\xbe"):
        return "executable", "programa de macOS (Mach-O)"
    if h.startswith(b"#!"):
        return "executable", "script ejecutable"
    if h.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
        return "executable", "documento/instalador OLE (MSI, DOC con macros)"
    if h.startswith(b"MSCF"):
        return "archive", "archivo CAB"
    if h.startswith(b"PK\x03\x04") or h.startswith(b"PK\x05\x06"):
        return "archive", "archivo comprimido ZIP"
    if h.startswith(b"Rar!"):
        return "archive", "archivo comprimido RAR"
    if h.startswith(b"7z\xbc\xaf\x27\x1c"):
        return "archive", "archivo comprimido 7z"
    if h.startswith(b"\x1f\x8b"):
        return "archive", "archivo comprimido GZIP"
    if h.startswith(b"%PDF"):
        return "document", "documento PDF"

    # Multimedia
    if h[4:8] in (b"ftyp", b"moov", b"mdat", b"free", b"wide", b"skip"):
        return "media", "MP4/MOV/M4A"
    if h.startswith(b"\x1a\x45\xdf\xa3"):
        return "media", "Matroska/WebM"
    if h.startswith(b"ID3"):
        return "media", "MP3"
    if h.startswith(b"OggS"):
        return "media", "Ogg"
    if h.startswith(b"fLaC"):
        return "media", "FLAC"
    if h.startswith(b"RIFF") and h[8:12] in (b"WAVE", b"AVI "):
        return "media", "WAV/AVI"
    if h.startswith(b"FLV"):
        return "media", "FLV"
    if h.startswith(b"\x00\x00\x01\xba") or h.startswith(b"\x00\x00\x01\xb3"):
        return "media", "MPEG"
    if len(h) > 188 and h[0] == 0x47 and h[188] == 0x47:
        return "media", "MPEG-TS"
    if len(h) >= 2 and h[0] == 0xFF and (h[1] & 0xE0) == 0xE0:
        return "media", "MPEG audio / AAC"
    if h.startswith(b"#EXTM3U"):
        return "playlist", "lista M3U (no es un video)"

    text = h.lstrip(b"\xef\xbb\xbf \t\r\n").lower()
    if text.startswith((b"<!doctype", b"<html", b"<script", b"<svg", b"<?xml", b"<head", b"<body")):
        return "script", "página web/script (posible señuelo)"
    return "unknown", "tipo desconocido"


def _ffprobe_streams(path: Path) -> tuple[str, str]:
    ffprobe = find_ffprobe()
    if not ffprobe:
        return SKIP, "ffprobe no está disponible"
    try:
        proc = subprocess.run(
            [ffprobe, "-v", "error", "-show_entries", "stream=codec_type",
             "-of", "json", str(path)],
            capture_output=True, text=True, timeout=120, **subprocess_flags(),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return WARN, f"no se pudo ejecutar ffprobe ({exc})"
    if proc.returncode != 0:
        return FAIL, "el archivo no es un video/audio válido"
    try:
        streams = json.loads(proc.stdout or "{}").get("streams", [])
    except ValueError:
        streams = []
    kinds = sorted({s.get("codec_type") for s in streams} & {"video", "audio"})
    if not kinds:
        return FAIL, "no contiene pistas de video ni de audio"
    names = {"video": "video", "audio": "audio"}
    return OK, "pistas válidas: " + " + ".join(names[k] for k in kinds)


# ---------------------------------------------------------------------------
# Capa 4: antivirus del sistema
# ---------------------------------------------------------------------------

class AntivirusEngine:
    name = "Antivirus"

    def scan(self, path: Path) -> tuple[str, str]:  # (OK|FAIL|WARN, detalle)
        raise NotImplementedError


class DefenderEngine(AntivirusEngine):
    name = "Microsoft Defender"

    def __init__(self, exe: str):
        self.exe = exe

    @classmethod
    def locate(cls) -> "DefenderEngine | None":
        if not IS_WINDOWS:
            return None
        candidates = []
        program_data = os.environ.get("ProgramData", r"C:\ProgramData")
        platform = sorted(glob.glob(os.path.join(program_data, "Microsoft", "Windows Defender",
                                                 "Platform", "*", "MpCmdRun.exe")))
        candidates.extend(reversed(platform))  # versión más reciente primero
        program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
        candidates.append(os.path.join(program_files, "Windows Defender", "MpCmdRun.exe"))
        for exe in candidates:
            if os.path.isfile(exe):
                return cls(exe)
        return None

    def scan(self, path: Path) -> tuple[str, str]:
        try:
            proc = subprocess.run(
                [self.exe, "-Scan", "-ScanType", "3", "-File", str(path), "-DisableRemediation"],
                capture_output=True, text=True, timeout=600, **subprocess_flags(),
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return WARN, f"no se pudo completar el análisis ({exc})"
        if proc.returncode == 0:
            return OK, "sin amenazas"
        if proc.returncode == 2:
            threat = next((ln.strip() for ln in proc.stdout.splitlines() if "Threat" in ln), "")
            return FAIL, f"amenaza detectada {threat}".strip()
        return WARN, f"el antivirus devolvió el código {proc.returncode}"


class ClamAVEngine(AntivirusEngine):
    name = "ClamAV"

    def __init__(self, exe: str):
        self.exe = exe

    @classmethod
    def locate(cls) -> "ClamAVEngine | None":
        for binary in ("clamdscan", "clamscan"):
            exe = shutil.which(binary)
            if exe:
                return cls(exe)
        return None

    def scan(self, path: Path) -> tuple[str, str]:
        args = [self.exe, "--no-summary"]
        if Path(self.exe).stem == "clamdscan":
            args.append("--fdpass")
        try:
            proc = subprocess.run(args + [str(path)], capture_output=True, text=True,
                                  timeout=900, **subprocess_flags())
        except (OSError, subprocess.TimeoutExpired) as exc:
            return WARN, f"no se pudo completar el análisis ({exc})"
        if proc.returncode == 0:
            return OK, "sin amenazas"
        if proc.returncode == 1:
            found = proc.stdout.strip().split(":")[-1].replace("FOUND", "").strip()
            return FAIL, f"amenaza detectada: {found}"
        return WARN, "error del antivirus: " + (proc.stderr or proc.stdout).strip()[:200]


def detect_antivirus() -> AntivirusEngine | None:
    return DefenderEngine.locate() or ClamAVEngine.locate()


# ---------------------------------------------------------------------------
# Capa 5: VirusTotal (opcional)
# ---------------------------------------------------------------------------

def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def virustotal_lookup(sha256: str, api_key: str, timeout: int = 20) -> tuple[str, str]:
    req = urllib.request.Request(
        f"https://www.virustotal.com/api/v3/files/{sha256}",
        headers={"x-apikey": api_key, "accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return OK, "archivo nuevo, sin reportes previos de amenazas"
        if exc.code in (401, 403):
            return WARN, "clave API inválida"
        if exc.code == 429:
            return WARN, "límite de consultas alcanzado (intenta más tarde)"
        return WARN, f"error HTTP {exc.code}"
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        return WARN, f"sin conexión con VirusTotal ({exc})"
    stats = data.get("data", {}).get("attributes", {}).get("last_analysis_stats", {})
    malicious = int(stats.get("malicious", 0))
    suspicious = int(stats.get("suspicious", 0))
    total = sum(int(v) for v in stats.values() if isinstance(v, int)) or "?"
    if malicious >= 2:
        return FAIL, f"{malicious}/{total} motores lo marcan como malicioso"
    if malicious == 1 or suspicious >= 3:
        return WARN, f"{malicious} malicioso, {suspicious} sospechoso de {total} motores"
    return OK, f"0/{total} motores detectan amenazas"


# ---------------------------------------------------------------------------
# Escáner principal
# ---------------------------------------------------------------------------

class SecurityScanner:
    def __init__(self, *, antivirus_enabled: bool = True, virustotal_key: str = "",
                 engine: AntivirusEngine | None = None, use_ffprobe: bool = True):
        self.antivirus_enabled = antivirus_enabled
        self.virustotal_key = virustotal_key.strip()
        self.engine = engine if engine is not None else (detect_antivirus() if antivirus_enabled else None)
        self.use_ffprobe = use_ffprobe

    def scan(self, path: Path | str) -> ScanReport:
        path = Path(path)
        report = ScanReport(path=str(path))
        name = path.name
        ext = path.suffix.lower().lstrip(".")

        # Capa 2 — reglas sobre el nombre (antes de leer nada)
        if any(ch in name for ch in BIDI_CHARS):
            report.add("Nombre del archivo", FAIL, "usa caracteres invisibles para disfrazar la extensión")
            return self._finish(report, THREAT)
        if ext in DANGEROUS_EXTS or ext not in ALLOWED_EXTS:
            report.add("Extensión", FAIL, f".{ext or '(sin extensión)'} no es un formato multimedia permitido")
            return self._finish(report, THREAT)
        parts = name.lower().split(".")
        if len(parts) >= 3 and parts[-2] in DANGEROUS_EXTS and parts[-2] not in ("com",):
            report.add("Extensión", FAIL, f"doble extensión sospechosa (.{parts[-2]}.{ext})")
            return self._finish(report, THREAT)
        report.add("Extensión", OK, f".{ext} permitido")

        try:
            with open(path, "rb") as fh:
                header = fh.read(512)
            size = path.stat().st_size
        except FileNotFoundError:
            report.add("Archivo", FAIL, "el archivo desapareció (posiblemente lo eliminó el antivirus del sistema)")
            return self._finish(report, THREAT)
        except OSError as exc:
            report.add("Archivo", FAIL, f"no se pudo leer ({exc})")
            return self._finish(report, SUSPICIOUS)

        if size == 0:
            report.add("Archivo", FAIL, "el archivo está vacío")
            return self._finish(report, SUSPICIOUS)

        # Capa 1 — tipo real por firma interna
        category, label = sniff(header)
        if ext in SUBTITLE_EXTS:
            if category in ("executable", "archive", "document", "script"):
                report.add("Tipo real", FAIL, f"dice ser subtítulo pero es {label}")
                return self._finish(report, THREAT)
            # Capa 3 — contenido de subtítulos
            status, detail = self._check_subtitle(path, size)
            report.add("Contenido de subtítulos", status, detail)
            if status == FAIL:
                return self._finish(report, THREAT)
        else:
            if category != "media":
                report.add("Tipo real", FAIL, f"dice ser .{ext} pero es {label}")
                return self._finish(report, THREAT)
            report.add("Tipo real", OK, label)
            if self.use_ffprobe:
                status, detail = _ffprobe_streams(path)
                report.add("Validación multimedia (ffprobe)", status, detail)
                if status == FAIL:
                    return self._finish(report, THREAT)

        verdict = CLEAN

        # Capa 4 — antivirus del sistema
        if not self.antivirus_enabled:
            report.add("Antivirus", SKIP, "desactivado en Ajustes")
        elif self.engine is None:
            report.add("Antivirus", SKIP, "no se encontró antivirus instalado (Defender/ClamAV)")
        else:
            status, detail = self.engine.scan(path)
            if status == OK and not path.exists():
                status, detail = FAIL, "el antivirus del sistema eliminó el archivo"
            report.add(self.engine.name, status, detail)
            if status == FAIL:
                return self._finish(report, THREAT)
            if status == WARN:
                verdict = SUSPICIOUS

        # Capa 5 — VirusTotal (solo la huella)
        if self.virustotal_key:
            try:
                report.sha256 = sha256_of(path)
            except OSError as exc:
                report.add("VirusTotal", WARN, f"no se pudo calcular la huella ({exc})")
            else:
                status, detail = virustotal_lookup(report.sha256, self.virustotal_key)
                report.add("VirusTotal", status, detail)
                if status == FAIL:
                    return self._finish(report, THREAT)
                if status == WARN and "motores" in detail:
                    verdict = SUSPICIOUS

        return self._finish(report, verdict)

    @staticmethod
    def _check_subtitle(path: Path, size: int) -> tuple[str, str]:
        if size > MAX_SUBTITLE_BYTES:
            return FAIL, "tamaño anormal para un subtítulo"
        raw = path.read_bytes()
        if b"\x00" in raw:
            return FAIL, "contiene datos binarios"
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("latin-1")
        low = text.lower()
        if "<script" in low or "javascript:" in low or "<iframe" in low:
            return FAIL, "contiene código (script) incrustado"
        return OK, "texto plano válido"

    @staticmethod
    def _finish(report: ScanReport, verdict: str) -> ScanReport:
        report.verdict = verdict
        return report


def worst_verdict(verdicts: list[str]) -> str:
    if THREAT in verdicts:
        return THREAT
    if SUSPICIOUS in verdicts:
        return SUSPICIOUS
    return CLEAN
