"""Licencias de DescarGO.

- Sin licencia activa (gratis o vencida): descargas ilimitadas en calidad estándar
  (video hasta STANDARD_MAX_RES p, audio hasta STANDARD_MAX_KBPS kbps).
- Con licencia: alta calidad (HD, Full HD, 4K, 60fps, HDR, audio 320 kbps, FLAC, original).

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
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

from ..utils import IS_MAC, IS_WINDOWS, app_data_dir, subprocess_flags

STANDARD_MAX_RES = 480        # lado corto del video (480p; en verticales 480x854)
STANDARD_MAX_KBPS = 128       # audio
PREMIUM_AUDIO_FORMATS = {"original", "flac", "wav"}
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
    lid: str = ""         # identificador único (para anulación)

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


def _new_license_id() -> str:
    import secrets
    return secrets.token_hex(6)  # identificador único de la licencia (para poder anularla)


def _payload_bytes(name: str, machine: str, expires: str | None, issued: str, lid: str = "") -> bytes:
    data = {"v": 1, "n": name, "m": machine, "e": expires, "i": issued}
    if lid:
        data["id"] = lid
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")


def sign_blob(private_key_pem: str, data: bytes) -> str:
    """Firma cualquier dato con la llave del administrador (Ed25519). Devuelve base64url."""
    from Cryptodome.PublicKey import ECC
    from Cryptodome.Signature import eddsa
    return _b64e(eddsa.new(ECC.import_key(private_key_pem), "rfc8032").sign(data))


def verify_blob(data: bytes, signature_b64: str) -> bool:
    """Comprueba que un dato lo firmó el administrador (con la llave pública incluida)."""
    from Cryptodome.PublicKey import ECC
    from Cryptodome.Signature import eddsa
    try:
        eddsa.new(ECC.import_key(PUBLIC_KEY_PEM), "rfc8032").verify(data, _b64d(signature_b64))
        return True
    except (ValueError, TypeError):
        return False


def create_license(private_key_pem: str, name: str, machine: str, expires: str | None = None,
                   lid: str | None = None) -> str:
    """Solo para el autor: firma una licencia para un código de equipo."""
    from Cryptodome.PublicKey import ECC
    from Cryptodome.Signature import eddsa

    machine = machine.strip().upper()
    if len(machine.replace("-", "")) != 16:
        raise LicenseError("El código de equipo no es válido (debe verse como 7F3A-91C2-0BDE-44A8).")
    if expires:
        datetime.strptime(expires, "%Y-%m-%d")
    lid = lid or _new_license_id()
    payload = _payload_bytes(name.strip() or "Usuario", machine, expires or None,
                             date.today().isoformat(), lid)
    key = ECC.import_key(private_key_pem)
    signature = eddsa.new(key, "rfc8032").sign(payload)
    return LICENSE_PREFIX + _b64e(payload) + "." + _b64e(signature)


def verify_license(text: str, machine: str | None = None, allow_expired: bool = False) -> License:
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
                  expires=data.get("e"), issued=str(data.get("i", "")), key=text,
                  lid=str(data.get("id", "")))
    if lic.machine != (machine or machine_code()):
        raise LicenseError("Esta licencia pertenece a otro equipo.")
    if lic.expired and not allow_expired:
        raise LicenseError(f"La licencia venció el {lic.expires}.")
    return lic


def apply_standard_quality(req) -> bool:
    """Limita una descarga a calidad estándar. Devuelve True si cambió algo."""
    changed = req.quality_cap != STANDARD_MAX_RES
    req.quality_cap = STANDARD_MAX_RES
    if req.kind == "audio":
        if req.audio_format in PREMIUM_AUDIO_FORMATS:
            req.audio_format, changed = "mp3", True
        if req.audio_bitrate > STANDARD_MAX_KBPS:
            req.audio_bitrate, changed = STANDARD_MAX_KBPS, True
    else:
        req.video_hdr = None
        req.video_fps60 = None
    return changed


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
        self._revoked: set[str] = self._load_revoked()
        self.load()

    # -- licencia -------------------------------------------------------------
    def load(self) -> None:
        self.license = None
        if self._license_file.is_file():
            try:  # se conserva aunque esté vencida, para avisar al usuario
                self.license = verify_license(self._license_file.read_text(encoding="utf-8"),
                                              allow_expired=True)
            except LicenseError:
                self.license = None

    # -- anulación (revocación a distancia) -----------------------------------
    def _load_revoked(self) -> set[str]:
        path = self.folder / "revocadas_local.json"
        try:
            return set(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            return set()

    def apply_revoked_ids(self, revoked_ids: "set[str] | None") -> bool:
        """Guarda la última lista de anulaciones descargada. True si la licencia activa quedó anulada."""
        if revoked_ids is None:  # sin conexión: se mantiene lo último que sabíamos
            return self.is_revoked
        self._revoked = set(revoked_ids)
        try:
            (self.folder / "revocadas_local.json").write_text(
                json.dumps(sorted(self._revoked)), encoding="utf-8")
        except OSError:
            pass
        return self.is_revoked

    @property
    def is_revoked(self) -> bool:
        return (self.license is not None and bool(self.license.lid)
                and self.license.lid in self._revoked)

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
        """Alta calidad habilitada (autor o licencia vigente y no anulada)."""
        if self.is_author:
            return True
        return self.license is not None and not self.license.expired and not self.is_revoked

    @property
    def expired_license(self) -> License | None:
        if self.license is not None and self.license.expired and not self.is_author:
            return self.license
        return None

    def enforce(self, req) -> bool:
        """Aplica el plan a una descarga. True si se redujo la calidad."""
        if self.licensed:
            req.quality_cap = None
            return False
        return apply_standard_quality(req)

    # -- generador (solo autor) ---------------------------------------------------
    def private_key(self) -> str | None:
        path = self.folder / PRIVATE_KEY_FILENAME
        return path.read_text(encoding="utf-8") if path.is_file() else None

    def install_author_key(self, source: Path | str) -> bool:
        """Copia la llave del autor a la carpeta de datos, solo si es la llave REAL."""
        try:
            return self.install_author_key_text(Path(source).read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError):
            return False

    def install_author_key_text(self, pem: str) -> bool:
        """Igual que install_author_key, pero con el texto de la llave pegado."""
        pem = (pem or "").strip()
        if "PRIVATE KEY" not in pem:
            return False
        # tolera que se pegue en una sola línea o con espacios extra
        begin, end = "-----BEGIN " + "PRIVATE KEY-----", "-----END " + "PRIVATE KEY-----"
        body = "".join(pem.replace(begin, "").replace(end, "").split())
        pem = begin + "\n" + body + "\n" + end + "\n"
        try:
            from Cryptodome.PublicKey import ECC
            if ECC.import_key(pem).public_key() != ECC.import_key(PUBLIC_KEY_PEM):
                return False
        except (OSError, ValueError, TypeError, IndexError, UnicodeDecodeError):
            return False
        (self.folder / PRIVATE_KEY_FILENAME).write_text(pem, encoding="utf-8")
        self._author = None
        return self.is_author

    # -- registro de licencias emitidas (solo autor) ------------------------------
    def log_issued(self, name: str, machine: str, expires: str | None, key: str,
                   amount: float = 0.0, note: str = "", lid: str = "") -> None:
        entry = {"fecha": datetime.now().isoformat(timespec="seconds"), "nombre": name,
                 "equipo": machine, "vence": expires, "licencia": key,
                 "monto": round(float(amount or 0), 2), "nota": note, "id": lid}
        with open(self.folder / "licencias_emitidas.jsonl", "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # -- anulación de clientes (solo administrador) -------------------------------
    def revoked_set(self) -> set[str]:
        try:
            return set(json.loads((self.folder / "anuladas_admin.json").read_text(encoding="utf-8")))
        except (OSError, ValueError):
            return set()

    def set_revoked(self, revoked_ids: set[str]) -> None:
        (self.folder / "anuladas_admin.json").write_text(
            json.dumps(sorted(revoked_ids)), encoding="utf-8")

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


@dataclass
class Client:
    name: str
    machine: str
    expires: str | None      # de la licencia más reciente
    last_key: str
    total_paid: float
    licenses: int
    last_issued: str
    ids: list[str] = field(default_factory=list)   # todas las licencias de este equipo
    revoked: bool = False

    def status(self, today: date | None = None) -> tuple[str, int | None]:
        if self.revoked:
            return "revoked", None
        """(«active» | «expiring» | «expired» | «permanent», días restantes)."""
        if not self.expires:
            return "permanent", None
        today = today or date.today()
        days = (date.fromisoformat(self.expires) - today).days
        if days < 0:
            return "expired", days
        if days <= 15:
            return "expiring", days
        return "active", days


def summarize_clients(entries: list[dict], revoked_ids: set[str] | None = None) -> list[Client]:
    """Agrupa las licencias emitidas por código de equipo (la más reciente manda)."""
    revoked_ids = revoked_ids or set()
    clients: dict[str, Client] = {}
    for e in sorted(entries, key=lambda x: str(x.get("fecha", ""))):
        machine = str(e.get("equipo", "")).upper()
        if not machine:
            continue
        lid = str(e.get("id", ""))
        c = clients.get(machine)
        paid = float(e.get("monto") or 0)
        if c is None:
            c = Client(str(e.get("nombre", "")), machine, e.get("vence"),
                       str(e.get("licencia", "")), paid, 1, str(e.get("fecha", "")))
            clients[machine] = c
        else:
            c.name = str(e.get("nombre") or c.name)
            c.expires = e.get("vence")
            c.last_key = str(e.get("licencia", ""))
            c.total_paid += paid
            c.licenses += 1
            c.last_issued = str(e.get("fecha", ""))
        if lid:
            c.ids.append(lid)
    for c in clients.values():
        c.revoked = bool(c.ids) and all(i in revoked_ids for i in c.ids)
    return sorted(clients.values(), key=lambda c: c.last_issued, reverse=True)


def add_months(start: date, months: int) -> date:
    """Suma meses de calendario (31-ene + 1 mes = 28/29-feb)."""
    import calendar
    month = start.month - 1 + months
    year = start.year + month // 12
    month = month % 12 + 1
    day = min(start.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)
