"""Análisis de enlaces: lee qué calidades existen realmente antes de descargar."""

from __future__ import annotations

from typing import Any

from . import policy
from .formats import QuietLogger
from .models import MediaInfo, PlaylistEntry, VideoOption

PLATFORM_NAMES = {
    "youtube": "YouTube", "youtubetab": "YouTube", "youtubeshorts": "YouTube",
    "facebook": "Facebook", "facebookreel": "Facebook Reels", "facebookplugins": "Facebook",
    "instagram": "Instagram", "instagramstory": "Instagram", "instagramuser": "Instagram",
    "tiktok": "TikTok", "tiktokuser": "TikTok", "vmtiktok": "TikTok",
    "twitter": "X (Twitter)", "vimeo": "Vimeo", "dailymotion": "Dailymotion",
    "twitch:vod": "Twitch", "twitch:clips": "Twitch", "reddit": "Reddit",
    "soundcloud": "SoundCloud", "bilibili": "Bilibili", "generic": "Web",
}

_FRIENDLY_ERRORS = [
    (("unsupported url",), "No se encontró ningún video o audio en esta página."),
    (("sign in to confirm", "not a bot"),
     "La plataforma pide verificar que no eres un robot.\n"
     "Activa «Usar sesión del navegador» en Ajustes → Red e inténtalo de nuevo."),
    (("private video", "this video is private", "is private"),
     "El video es privado. Solo puedes descargarlo si tu cuenta tiene acceso a él "
     "(activa «Usar sesión del navegador» en Ajustes)."),
    (("login required", "log in", "requires authentication", "cookies", "rate-limit reached"),
     "Esta plataforma pide iniciar sesión para ver el contenido.\n"
     "Activa «Usar sesión del navegador» en Ajustes → Red."),
    (("not available in your country", "geo restrict", "geo-restrict"),
     "El contenido no está disponible en tu país."),
    (("video unavailable", "has been removed", "no longer available", "http error 404", "404"),
     "El contenido no existe o fue eliminado."),
    (("http error 429", "too many requests"),
     "La plataforma recibió demasiadas solicitudes. Espera unos minutos e inténtalo otra vez."),
    (("unable to download webpage", "name or service not known", "getaddrinfo",
      "timed out", "connection"),
     "No se pudo conectar. Revisa tu conexión a internet."),
]


class AnalysisError(Exception):
    pass


def friendly_error(message: str) -> str:
    blocked = policy.blocked_reason_from_error(message)
    if blocked:
        return blocked
    low = (message or "").lower()
    for hints, friendly in _FRIENDLY_ERRORS:
        if any(h in low for h in hints):
            return friendly
    clean = (message or "Error desconocido").replace("ERROR: ", "").strip()
    return f"No se pudo procesar el enlace.\nDetalle: {clean[:300]}"


def platform_name(info: dict) -> str:
    key = (info.get("extractor_key") or info.get("ie_key") or info.get("extractor") or "").lower()
    if key in PLATFORM_NAMES:
        return PLATFORM_NAMES[key]
    for prefix, name in PLATFORM_NAMES.items():
        if key.startswith(prefix) and prefix != "generic":
            return name
    return info.get("extractor_key") or "Web"


def _size(fmt: dict, duration: float | None) -> int | None:
    size = fmt.get("filesize") or fmt.get("filesize_approx")
    if not size and duration and fmt.get("tbr"):
        size = fmt["tbr"] * 1000 / 8 * duration
    return int(size) if size else None


def _has_video(fmt: dict) -> bool:
    return fmt.get("vcodec") != "none" and bool(fmt.get("height"))


def _has_audio_only(fmt: dict) -> bool:
    return fmt.get("vcodec") == "none" and fmt.get("acodec") not in (None, "none")


def build_video_options(formats: list[dict], duration: float | None) -> tuple[list[VideoOption], float | None, int | None]:
    """Agrupa los formatos por resolución/fps/HDR y estima el tamaño final."""
    usable = [f for f in formats if not f.get("has_drm")]
    audio_only = [f for f in usable if _has_audio_only(f)]
    best_audio = max(audio_only, key=lambda f: (f.get("abr") or f.get("tbr") or 0), default=None)
    audio_abr = (best_audio.get("abr") or best_audio.get("tbr")) if best_audio else None
    audio_size = _size(best_audio, duration) if best_audio else None

    groups: dict[tuple[int, bool, bool], VideoOption] = {}
    for f in usable:
        if not _has_video(f):
            continue
        height = int(f["height"])
        width = f.get("width")
        label_res = min(height, int(width)) if width else height
        fps = int(round(f.get("fps") or 30))
        hdr = (f.get("dynamic_range") or "SDR").upper() != "SDR"
        size = _size(f, duration)
        if size and f.get("acodec") in (None, "none") and audio_size:
            size += audio_size
        key = (height, fps > 30, hdr)
        current = groups.get(key)
        if current is None:
            groups[key] = VideoOption(height=height, label_res=label_res, fps=fps, hdr=hdr, est_size=size)
        else:
            current.fps = max(current.fps, fps)
            if size and (not current.est_size or size > current.est_size):
                current.est_size = size

    if not audio_abr:
        combined = [f for f in usable if f.get("acodec") not in (None, "none") and f.get("abr")]
        if combined:
            audio_abr = max(f["abr"] for f in combined)

    options = sorted(groups.values(), key=lambda o: (o.label_res, o.height, o.hfr, o.hdr), reverse=True)
    return options, audio_abr, audio_size


def _subtitle_languages(info: dict) -> list[str]:
    manual = [k for k in (info.get("subtitles") or {}) if k != "live_chat"]
    auto = info.get("automatic_captions") or {}
    preferred = [k for k in auto if k in ("es", "en") or k.endswith("-orig")]
    langs: list[str] = []
    for lang in manual + preferred:
        if lang not in langs:
            langs.append(lang)
    return langs


def _ydl_params(cookies_browser: str = "") -> dict[str, Any]:
    params: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": "in_playlist",
        "noplaylist": False,
        "logger": QuietLogger(),
    }
    if cookies_browser:
        params["cookiesfrombrowser"] = (cookies_browser,)
    return params


def info_to_media(url: str, info: dict) -> MediaInfo:
    """Convierte la respuesta de yt-dlp en un MediaInfo (sin red, fácil de probar)."""
    policy.check_info(info)
    title = info.get("title") or info.get("id") or "Sin título"
    platform = platform_name(info)

    if info.get("_type") == "playlist":
        entries: list[PlaylistEntry] = []
        for entry in info.get("entries") or []:
            if not entry:
                continue
            link = entry.get("webpage_url") or entry.get("url") or ""
            if not str(link).startswith("http"):
                continue
            if policy.is_paid_url(link):
                continue
            entries.append(PlaylistEntry(url=link, title=entry.get("title") or link,
                                         duration=entry.get("duration")))
        if not entries:
            raise AnalysisError("La lista no contiene videos públicos disponibles.")
        return MediaInfo(url=url, title=title, platform=platform,
                         uploader=info.get("uploader") or info.get("channel") or "",
                         thumbnail=_thumbnail(info), is_playlist=True, entries=entries)

    duration = info.get("duration")
    formats = info.get("formats") or ([info] if info.get("url") else [])
    options, audio_abr, audio_size = build_video_options(formats, duration)
    return MediaInfo(
        url=info.get("webpage_url") or url,
        title=title,
        platform=platform,
        uploader=info.get("uploader") or info.get("channel") or info.get("creator") or "",
        duration=duration,
        thumbnail=_thumbnail(info),
        video_options=options,
        audio_abr=audio_abr,
        audio_size=audio_size,
        subtitles=_subtitle_languages(info),
    )


def _thumbnail(info: dict) -> str:
    if info.get("thumbnail"):
        return info["thumbnail"]
    thumbs = info.get("thumbnails") or []
    return thumbs[-1].get("url", "") if thumbs else ""


def analyze(url: str, *, cookies_browser: str = "") -> MediaInfo:
    """Analiza un enlace en red. Lanza BlockedContentError o AnalysisError."""
    policy.check_url(url)
    import yt_dlp  # import diferido: acelera el arranque de la app

    try:
        with yt_dlp.YoutubeDL(_ydl_params(cookies_browser)) as ydl:
            info = ydl.extract_info(url, download=False)
            info = ydl.sanitize_info(info)
    except policy.BlockedContentError:
        raise
    except Exception as exc:  # yt-dlp lanza muchos tipos distintos
        blocked = policy.blocked_reason_from_error(str(exc))
        if blocked:
            raise policy.BlockedContentError(blocked) from exc
        raise AnalysisError(friendly_error(str(exc))) from exc
    if not info:
        raise AnalysisError("No se encontró ningún video o audio en esta página.")
    return info_to_media(url, info)
