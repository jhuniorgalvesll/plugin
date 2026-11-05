"""Política de uso responsable: bloqueo de páginas de pago y contenido con DRM.

DescarGO solo descarga contenido público y gratuito. Este módulo se aplica
siempre, antes y después de analizar un enlace, y no se puede desactivar.
"""

from __future__ import annotations

from urllib.parse import urlparse

PAID_MESSAGE = (
    "Este contenido es de pago o está protegido.\n"
    "DescarGO solo descarga contenido de acceso público y gratuito."
)
DRM_MESSAGE = (
    "Este contenido está protegido con DRM (cifrado anticopia).\n"
    "DescarGO no evade protecciones de ningún tipo."
)
PREMIUM_MESSAGE = (
    "Este contenido es exclusivo para miembros, suscriptores o clientes de pago.\n"
    "DescarGO solo descarga contenido de acceso público y gratuito."
)

# Servicios de streaming, música, cursos y contenido por suscripción.
PAID_DOMAINS: frozenset[str] = frozenset({
    # Streaming de video por suscripción
    "netflix.com", "disneyplus.com", "starplus.com", "primevideo.com",
    "hbomax.com", "max.com", "hbo.com", "paramountplus.com", "peacocktv.com",
    "hulu.com", "tv.apple.com", "crunchyroll.com", "funimation.com",
    "mubi.com", "dazn.com", "filmin.es", "atresplayer.com", "movistarplus.es",
    "skyshowtime.com", "britbox.com", "curiositystream.com", "plus.espn.com",
    "fubo.tv", "sling.com", "directvgo.com", "clarovideo.com",
    # Música por suscripción
    "spotify.com", "music.apple.com", "tidal.com", "deezer.com",
    "music.amazon.com", "qobuz.com",
    # Cursos y formación de pago
    "udemy.com", "domestika.org", "platzi.com", "skillshare.com",
    "masterclass.com", "coursera.org", "pluralsight.com", "crehana.com",
    "linkedin.com/learning", "lynda.com", "egghead.io", "frontendmasters.com",
    # Contenido para suscriptores / creadores de pago
    "onlyfans.com", "fansly.com", "patreon.com", "subscribestar.com",
    "ko-fi.com", "buymeacoffee.com", "gumroad.com", "vimeo.com/ondemand",
})

# Disponibilidades de yt-dlp que indican contenido de pago.
PAID_AVAILABILITY = {"premium_only", "subscriber_only"}

_DRM_HINTS = ("drm", "widevine", "playready", "fairplay")
_PAID_HINTS = (
    "members-only", "members only", "join this channel", "only available to members",
    "requires a subscription", "premium members", "purchase", "rent this",
    "this video requires payment", "paid content",
)


class BlockedContentError(Exception):
    """El contenido no está permitido por la política de DescarGO."""


def _split(url: str) -> tuple[str, str]:
    try:
        parsed = urlparse(url.strip())
    except ValueError:
        return "", ""
    host = (parsed.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    return host, (parsed.path or "/").lower()


def _matches(host: str, path: str, rule: str) -> bool:
    domain, _, rule_path = rule.partition("/")
    if host != domain and not host.endswith("." + domain):
        return False
    return not rule_path or path.startswith("/" + rule_path)


def is_paid_url(url: str) -> bool:
    host, path = _split(url)
    if not host:
        return False
    if any(_matches(host, path, rule) for rule in PAID_DOMAINS):
        return True
    # Amazon Prime Video desde cualquier dominio de Amazon (amazon.com, .es, .com.mx…)
    if (host.startswith("amazon.") or ".amazon." in host) and path.startswith("/gp/video"):
        return True
    return False


def check_url(url: str) -> None:
    """Lanza BlockedContentError si el enlace es de una página de pago."""
    if is_paid_url(url):
        raise BlockedContentError(PAID_MESSAGE)


def check_info(info: dict) -> None:
    """Revisa la información extraída del video (después del análisis)."""
    for key in ("webpage_url", "original_url", "url"):
        value = info.get(key)
        if isinstance(value, str) and value.startswith("http"):
            check_url(value)
    if info.get("availability") in PAID_AVAILABILITY:
        raise BlockedContentError(PREMIUM_MESSAGE)
    if info.get("_has_drm"):
        raise BlockedContentError(DRM_MESSAGE)
    formats = info.get("formats") or []
    if formats and all(f.get("has_drm") for f in formats):
        raise BlockedContentError(DRM_MESSAGE)


def blocked_reason_from_error(message: str) -> str | None:
    """Traduce errores del motor que indican DRM o contenido de pago."""
    low = (message or "").lower()
    if any(hint in low for hint in _DRM_HINTS):
        return DRM_MESSAGE
    if any(hint in low for hint in _PAID_HINTS):
        return PREMIUM_MESSAGE
    return None
