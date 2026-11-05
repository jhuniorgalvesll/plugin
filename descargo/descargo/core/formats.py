"""Traduce la elección del usuario (DownloadRequest) a opciones de yt-dlp."""

from __future__ import annotations

from typing import Any, Callable

from .models import AUDIO_FORMATS_WITH_BITRATE, DownloadRequest

# Códec que usa el postprocesador de yt-dlp para cada formato de audio.
_AUDIO_CODEC = {
    "original": "best",  # copia la pista tal cual, sin recomprimir
    "mp3": "mp3",
    "m4a": "m4a",
    "opus": "opus",
    "ogg": "vorbis",
    "flac": "flac",
    "wav": "wav",
}

# Preferencias de códec por contenedor (la resolución siempre manda).
_FORMAT_SORT = {
    "mp4": ["res", "fps", "vcodec:h264", "acodec:aac"],
    "webm": ["res", "fps", "vcodec:vp9", "acodec:opus"],
    "mkv": ["res", "fps"],
}
# Formatos que admiten portada incrustada.
_COVER_AUDIO = {"original", "mp3", "m4a", "opus", "ogg", "flac"}
_COVER_VIDEO = {"mp4", "mkv"}

# Si los códecs no caben en el contenedor elegido, se usa MKV como respaldo.
_MERGE_FORMAT = {"mp4": "mp4/mkv", "webm": "webm/mkv", "mkv": "mkv"}


class QuietLogger:
    """Evita que el motor escriba en la consola; los errores llegan como excepciones."""

    def debug(self, msg: str) -> None:
        pass

    info = warning = error = debug


def video_selector(height: int | None, fps60: bool | None = None, hdr: bool | None = None) -> str:
    """Selector de formato con alternativas, de la más exacta a la más flexible."""
    if not height:
        return "bv*+ba/b"
    fps = "[fps>?30]" if fps60 is True else "[fps<=?30]" if fps60 is False else ""
    dr = "[dynamic_range!^=?SDR]" if hdr is True else "[dynamic_range!^=?HDR]" if hdr is False else ""
    exact = f"[height={height}]{fps}{dr}"
    return "/".join([
        f"bv*{exact}+ba",
        f"b{exact}",
        f"bv*[height<={height}]+ba",
        f"b[height<={height}]",
        "bv*+ba",
        "b",
    ])


def build_ydl_options(
    req: DownloadRequest,
    workdir: str,
    *,
    ffmpeg_dir: str | None = None,
    cookies_browser: str = "",
    rate_limit_kb: int = 0,
    embed_thumbnail: bool = True,
    progress_hook: Callable[[dict], Any] | None = None,
    postprocessor_hook: Callable[[dict], Any] | None = None,
) -> dict:
    opts: dict[str, Any] = {
        "paths": {"home": workdir, "temp": workdir},
        "outtmpl": {"default": "%(title).150B [%(id)s].%(ext)s"},
        "windowsfilenames": True,
        "noplaylist": True,
        "continuedl": True,
        "overwrites": False,
        "retries": 10,
        "fragment_retries": 10,
        "concurrent_fragment_downloads": 4,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "logger": QuietLogger(),
        "postprocessors": [],
        "progress_hooks": [progress_hook] if progress_hook else [],
        "postprocessor_hooks": [postprocessor_hook] if postprocessor_hook else [],
    }
    if ffmpeg_dir:
        opts["ffmpeg_location"] = ffmpeg_dir
    if cookies_browser:
        opts["cookiesfrombrowser"] = (cookies_browser,)
    if rate_limit_kb > 0:
        opts["ratelimit"] = rate_limit_kb * 1024

    pps: list[dict] = opts["postprocessors"]

    if req.kind == "audio":
        opts["format"] = "ba/b"
        codec = _AUDIO_CODEC.get(req.audio_format, "best")
        quality = str(req.audio_bitrate) if req.audio_format in AUDIO_FORMATS_WITH_BITRATE else "0"
        pps.append({"key": "FFmpegExtractAudio", "preferredcodec": codec, "preferredquality": quality})
        pps.append({"key": "FFmpegMetadata", "add_metadata": True})
        if embed_thumbnail and req.audio_format in _COVER_AUDIO:
            _add_cover(opts)
        return opts

    container = req.container if req.container in _MERGE_FORMAT else "mp4"
    opts["format"] = video_selector(req.video_height, req.video_fps60, req.video_hdr)
    opts["format_sort"] = list(_FORMAT_SORT[container])
    opts["merge_output_format"] = _MERGE_FORMAT[container]
    pps.append({"key": "FFmpegMetadata", "add_metadata": True})
    if embed_thumbnail and container in _COVER_VIDEO:
        _add_cover(opts)

    if req.subtitles:
        opts["writesubtitles"] = True
        opts["writeautomaticsub"] = True
        opts["subtitleslangs"] = list(req.subtitles)
        opts["subtitlesformat"] = "srt/vtt/best"
        if req.embed_subtitles:
            pps.append({"key": "FFmpegEmbedSubtitle", "already_have_subtitle": False})
        else:
            pps.append({"key": "FFmpegSubtitlesConvertor", "format": "srt", "when": "before_dl"})
    # la portada se incrusta al final, después de unir video, audio y subtítulos
    covers = [p for p in pps if p["key"] == "EmbedThumbnail"]
    opts["postprocessors"] = [p for p in pps if p["key"] != "EmbedThumbnail"] + covers
    return opts


def _add_cover(opts: dict) -> None:
    """Portada (miniatura) incrustada en el archivo; la imagen suelta se borra."""
    opts["writethumbnail"] = True
    opts["postprocessors"].append({"key": "EmbedThumbnail", "already_have_thumbnail": False})
