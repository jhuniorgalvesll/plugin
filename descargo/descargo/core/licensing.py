"""Licencias de DescarGO.

- Plan gratuito: FREE_DAILY_LIMIT descargas completadas por día.
- Con licencia: descargas ilimitadas.

Cada licencia está firmada digitalmente (Ed25519) con la llave privada del autor y
va ligada al «código de equipo» del comprador. La app solo contiene la llave
PÚBLICA, que sirve para verificar firmas pero no para crearlas: nadie puede
fabricar licencias sin la llave privada de lliuya.pe.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import platform
import subprocess
import uuid
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from ..utils import IS_MAC, IS_WINDOWS, app_data_dir, subprocess_flags

FREE_DAILY_LIMIT = 10
LICENSE_PREFIX = "DGO1-"

PUBLIC_KEY_PEM = """-----BEGIN PUBLIC KEY-----
MCowBQYDK2VwAyEABs9JxikA95wdtfdzw5Dp/YsWDB2MXOY9QNsKDKKrj60=
-----END PUBLIC KEY-----"""

# Si el autor coloca su llave privada aquí, la app muestra el generador de licencias.
PRIVATE_KEY_FILENAME = "descargo-licencias.key"


class LicenseError(Exception):
    pass


# ---------------------------------------------------------------------------
# Código de equipo
# ---------------------------------------------------------------------------

def _raw_machine_id() -> str:
    try:
        if IS_WINDOWS:
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography",
                                0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as key:
                return str(winreg.QueryValueEx(key, "MachineGuid")[0])
        if IS_MAC:
            out = subprocess.run(["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
                                 capture_output=True, text=True, timeout=5, **subprocess_flags()).stdout
            for line in out.splitlines():
                if "IOPlatformUUID" in line:
                    return line.split('"')[-2]
        for path in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
            if os.path.isfile(path):
                return Path(path).read_text().strip()
    except Exception:
        pass
    # Respaldo estable: se genera una vez y se guarda.
    fallback = app_data_dir() / "equipo.id"
    if not fallback.is_file():
        fallback.write_text(uuid.uuid4().hex, encoding="utf-8")
    return fallback.read_text(encoding="utf-8").strip() + platform.node()


def machine_code() -> str:
    """Código corto y legible que identifica este equipo, p. ej. «7F3A-91C2-0BDE-44A8»."""
    digest = hashlib.sha256(("descargo|" + _raw_machine_id()).encode("utf-8")).hexdigest().upper()
    return "-".join(digest[i:i + 4] for i in range(0, 16, 4))


# ---------------------------------------------------------------------------
# Formato de licencia
# ---------------------------------------------------------------------------

@dataclass
class License:
    name: str
    machine: str
    expires: str | None   # "AAAA-MM-DD" o None = permanente
    issued: str
    key: str = ""

    @property
    def expired(self) -> bool:
        return bool(self.expires) and date.today().isoformat() > self.expires

    @property
    def summary(self) -> str:
        until = f"válida hasta el {self.expires}" if self.expires else "permanente"
        return f"{self.name} · {until}"


def _b64e(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64d(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _payload_bytes(name: str, machine: str, expires: str | None, issued: str) -> bytes:
    data = {"v": 1, "n": name, "m": machine, "e": expires, "i": issued}
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")


def create_license(private_key_pem: str, name: str, machine: str, expires: str | None = None) -> str:
    """Solo para el autor: firma una licencia para un código de equipo."""
    from Cryptodome.PublicKey import ECC
    from Cryptodome.Signature import eddsa

    machine = machine.strip().upper()
    if len(machine.replace("-", "")) != 16:
        raise LicenseError("El código de equipo no es válido (debe verse como 7F3A-91C2-0BDE-44A8).")
    if expires:
        datetime.strptime(expires, "%Y-%m-%d")
    payload = _payload_bytes(name.strip() or "Usuario", machine, expires or None, date.today().isoformat())
    key = ECC.import_key(private_key_pem)
    signature = eddsa.new(key, "rfc8032").sign(payload)
    return LICENSE_PREFIX + _b64e(payload) + "." + _b64e(signature)


def verify_license(text: str, machine: str | None = None) -> License:
    """Comprueba firma, equipo y vencimiento. Lanza LicenseError si algo falla."""
    from Cryptodome.PublicKey import ECC
    from Cryptodome.Signature import eddsa

    text = "".join((text or "").split())  # tolera espacios y saltos de línea al pegar
    if not text.startswith(LICENSE_PREFIX) or "." not in text:
        raise LicenseError("La licencia no tiene el formato correcto.")
    try:
        body, sig = text[len(LICENSE_PREFIX):].split(".", 1)
        payload, signature = _b64d(body), _b64d(sig)
        eddsa.new(ECC.import_key(PUBLIC_KEY_PEM), "rfc8032").verify(payload, signature)
        data = json.loads(payload.decode("utf-8"))
    except (ValueError, TypeError, KeyError):
        raise LicenseError("La licencia no es válida (firma incorrecta).") from None
    lic = License(name=str(data.get("n", "")), machine=str(data.get("m", "")),
                  expires=data.get("e"), issued=str(data.get("i", "")), key=text)
    if lic.machine != (machine or machine_code()):
        raise LicenseError("Esta licencia pertenece a otro equipo.")
    if lic.expired:
        raise LicenseError(f"La licencia venció el {lic.expires}.")
    return lic


# ---------------------------------------------------------------------------
# Estado local: licencia activa y contador diario
# ---------------------------------------------------------------------------

class LicenseManager:
    def __init__(self, folder: Path | None = None):
        self.folder = folder or app_data_dir()
        self._license_file = self.folder / "licencia.txt"
        self._usage_file = self.folder / "uso.json"
        self.license: License | None = None
        self._author: bool | None = None
        self.load()

    # -- licencia -------------------------------------------------------------
    def load(self) -> None:
        self.license = None
        if self._license_file.is_file():
            try:
                self.license = verify_license(self._license_file.read_text(encoding="utf-8"))
            except LicenseError:
                self.license = None

    def activate(self, text: str) -> License:
        lic = verify_license(text)
        self._license_file.write_text(lic.key, encoding="utf-8")
        self.license = lic
        return lic

    def deactivate(self) -> None:
        self._license_file.unlink(missing_ok=True)
        self.license = None

    @property
    def is_author(self) -> bool:
        """El computador del autor: tiene la llave privada REAL (la que firma las licencias).

        Un archivo falso con el mismo nombre no sirve: se comprueba que corresponda a la
        llave pública incluida en la app.
        """
        if self._author is None:
            self._author = False
            pem = self.private_key()
            if pem:
                try:
                    from Cryptodome.PublicKey import ECC
                    mine = ECC.import_key(pem).public_key()
                    self._author = mine == ECC.import_key(PUBLIC_KEY_PEM)
                except (ValueError, TypeError, IndexError):
                    self._author = False
        return self._author

    @property
    def licensed(self) -> bool:
        if self.is_author:
            return True
        return self.license is not None and not self.license.expired

    # -- contador diario --------------------------------------------------------
    def _check(self, day: str, count: int) -> str:
        return hashlib.sha256(f"{machine_code()}|{day}|{count}|dgo".encode()).hexdigest()[:16]

    def used_today(self) -> int:
        today = date.today().isoformat()
        try:
            data = json.loads(self._usage_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return 0
        if data.get("d") != today:
            return 0
        count = int(data.get("c", 0))
        if data.get("h") != self._check(today, count):
            return FREE_DAILY_LIMIT  # archivo manipulado: se considera agotado por hoy
        return count

    def record_download(self) -> None:
        if self.licensed:
            return
        today = date.today().isoformat()
        count = self.used_today() + 1
        self._usage_file.write_text(json.dumps({"d": today, "c": count, "h": self._check(today, count)}),
                                    encoding="utf-8")

    def remaining_today(self) -> int | None:
        """None = ilimitado (con licencia)."""
        if self.licensed:
            return None
        return max(0, FREE_DAILY_LIMIT - self.used_today())

    # -- generador (solo autor) ---------------------------------------------------
    def private_key(self) -> str | None:
        path = self.folder / PRIVATE_KEY_FILENAME
        return path.read_text(encoding="utf-8") if path.is_file() else None

    def install_author_key(self, source: Path | str) -> bool:
        """Copia la llave del autor a la carpeta de datos, solo si es la llave REAL."""
        try:
            pem = Path(source).read_text(encoding="utf-8")
            from Cryptodome.PublicKey import ECC
            if ECC.import_key(pem).public_key() != ECC.import_key(PUBLIC_KEY_PEM):
                return False
        except (OSError, ValueError, TypeError, IndexError, UnicodeDecodeError):
            return False
        (self.folder / PRIVATE_KEY_FILENAME).write_text(pem, encoding="utf-8")
        self._author = None
        return self.is_author

    # -- registro de licencias emitidas (solo autor) ------------------------------
    def log_issued(self, name: str, machine: str, expires: str | None, key: str) -> None:
        entry = {"fecha": datetime.now().isoformat(timespec="seconds"), "nombre": name,
                 "equipo": machine, "vence": expires, "licencia": key}
        with open(self.folder / "licencias_emitidas.jsonl", "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def issued(self) -> list[dict]:
        path = self.folder / "licencias_emitidas.jsonl"
        if not path.is_file():
            return []
        items = []
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                items.append(json.loads(line))
            except ValueError:
                continue
        return list(reversed(items))


def add_months(start: date, months: int) -> date:
    """Suma meses de calendario (31-ene + 1 mes = 28/29-feb)."""
    import calendar
    month = start.month - 1 + months
    year = start.year + month // 12
    month = month % 12 + 1
    day = min(start.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)
