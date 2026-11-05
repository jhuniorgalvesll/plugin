"""Títulos reales para nombrar los archivos.

Algunas plataformas no tienen «título»: Instagram usa «Video by usuario», Facebook
mezcla visualizaciones y reacciones, TikTok y X repiten el nombre de la cuenta.
Aquí se recupera el texto original de la publicación para nombrar el archivo.
"""

from __future__ import annotations

import re

MAX_LEN = 100

# Títulos que la plataforma inventa y no dicen nada del contenido.
_GENERIC = [
    re.compile(r"^(video|post|reel|photo|story|clip|igtv)\s+(by|de)\s+\S+", re.I),  # Instagram
    re.compile(r"^(tiktok|facebook|instagram|twitter|x)\s+(video|post|reel)?\s*#?\d*$", re.I),
    re.compile(r"^(video|untitled|sin t[ií]tulo|watch|reel|post)$", re.I),
    re.compile(r"^[\d\s.,]+[kKmM]?\s*(views|visualizaciones|reproducciones)", re.I),  # Facebook
]
_FB_STATS = re.compile(
    r"^\s*[\d.,]+\s*[kKmM]?\s*(views|visualizaciones|reproducciones|reactions|reacciones|"
    r"comments|comentarios|shares|veces compartido)\b", re.I)
_HASHTAG_TAIL = re.compile(r"(\s*[#@][\w.áéíóúñÁÉÍÓÚÑ]+)+\s*$")
_URLS = re.compile(r"https?://\S+")
_SPACES = re.compile(r"\s+")


def _clean_line(text: str) -> str:
    text = _URLS.sub("", text or "")
    text = _HASHTAG_TAIL.sub("", text)
    text = _SPACES.sub(" ", text).strip(" -–—|·.:;,")
    return text


def _shorten(text: str, limit: int = MAX_LEN) -> str:
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0]
    return (cut if len(cut) > limit * 0.6 else text[:limit]).rstrip(" ,.;:-") + "…"


def _caption(description: str) -> str:
    for line in (description or "").splitlines():
        cleaned = _clean_line(line)
        if len(cleaned) >= 3 and not _FB_STATS.match(cleaned):
            return cleaned
    return ""


def is_generic(title: str, info: dict) -> bool:
    t = (title or "").strip()
    if not t or t == info.get("id") or t == info.get("display_id"):
        return True
    for owner in (info.get("uploader"), info.get("uploader_id"), info.get("channel")):
        if owner and t.lower() in (str(owner).lower(), f"video by {owner}".lower()):
            return True
    return any(p.search(t) for p in _GENERIC)


def _facebook_title(title: str) -> str:
    """«1,2 K visualizaciones · 300 reacciones | Texto real | Página» → «Texto real»."""
    parts = [p.strip() for p in title.split(" | ")]
    useful = [p for p in parts if p and not _FB_STATS.match(p) and "·" not in p[:25]]
    return useful[0] if useful else ""


def smart_title(info: dict) -> str:
    """El mejor título disponible para mostrar y para el nombre del archivo."""
    title = str(info.get("title") or "").strip()
    if " | " in title and _FB_STATS.match(title):
        title = _facebook_title(title)
    # X/Twitter: «Nombre - texto del tweet» → texto del tweet
    if (info.get("extractor_key") or "").lower() == "twitter" and " - " in title:
        title = title.split(" - ", 1)[1]
    title = _clean_line(title)
    if is_generic(title, info):
        caption = _caption(str(info.get("description") or ""))
        if caption:
            title = caption
        elif info.get("uploader") or info.get("channel"):
            title = f"Video de {info.get('uploader') or info.get('channel')}"
        else:
            title = title or str(info.get("id") or "video")
    return _shorten(title)
