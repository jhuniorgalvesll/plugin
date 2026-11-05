"""Anulación de licencias a distancia.

El administrador puede anular una licencia (robada, no pagada o compartida) aunque
ya esté activada en el equipo del cliente. Funciona así:

1. El administrador marca la licencia como anulada en su panel. La app arma una
   «lista de anulaciones» firmada con su llave privada.
2. El administrador sube ese archivo (revocaciones.json) a su repositorio de GitHub.
3. Cada DescarGO descarga esa lista de vez en cuando (si hay internet), comprueba que
   la firmó el administrador y, si la licencia activa está en la lista, vuelve a
   calidad estándar.

La lista está firmada, así que nadie puede fabricar anulaciones ni «desanular» sin
la llave del administrador. Si no hay internet o la lista no existe, no se anula nada:
nunca se bloquea a un cliente que sí pagó por un problema de red.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import datetime

from .. import APP_VERSION
from .licensing import sign_blob, verify_blob
from .updater import GITHUB_REPO

REVOCATION_URL = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/revocaciones.json"
USER_AGENT = f"DescarGO/{APP_VERSION}"


def build_revocation_file(private_key_pem: str, revoked_ids: list[str]) -> str:
    """Arma el revocaciones.json firmado (lo usa el administrador)."""
    ids = sorted({i.strip() for i in revoked_ids if i.strip()})
    payload = json.dumps({"revocadas": ids, "fecha": datetime.now().isoformat(timespec="seconds")},
                         ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    signature = sign_blob(private_key_pem, payload.encode("utf-8"))
    return json.dumps({"datos": payload, "firma": signature}, ensure_ascii=False, indent=2)


def parse_revocation_file(text: str) -> set[str]:
    """Devuelve el conjunto de IDs anulados si la firma es válida; si no, conjunto vacío."""
    try:
        outer = json.loads(text)
        payload = outer["datos"]
        if not verify_blob(payload.encode("utf-8"), outer["firma"]):
            return set()
        return {str(i) for i in json.loads(payload).get("revocadas", [])}
    except (ValueError, TypeError, KeyError):
        return set()


def fetch_revoked_ids(timeout: int = 15) -> set[str] | None:
    """Descarga la lista de anulaciones. None = no se pudo (no se anula nada por precaución)."""
    req = urllib.request.Request(REVOCATION_URL, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return parse_revocation_file(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return set() if exc.code == 404 else None   # 404 = aún no hay lista: nada anulado
    except Exception:
        return None


def is_revoked(lid: str, revoked_ids: set[str] | None) -> bool:
    return bool(lid) and revoked_ids is not None and lid in revoked_ids
