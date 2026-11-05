"""Modelos de datos compartidos entre el motor y la interfaz."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

AUDIO_FORMATS: dict[str, str] = {
    "original": "Original (sin recomprimir) — recomendado",
    "mp3": "MP3",
    "m4a": "M4A (AAC)",
    "opus": "OPUS",
    "ogg": "OGG (Vorbis)",
    "flac": "FLAC",
    "wav": "WAV",
}
AUDIO_FORMATS_WITH_BITRATE = {"mp3", "m4a", "opus", "ogg"}
AUDIO_BITRATES = [320, 256, 192, 128]
VIDEO_CONTAINERS: dict[str, str] = {
    "mp4": "MP4 — compatible con todo",
    "mkv": "MKV — máxima calidad",
    "webm": "WEBM",
}
PLAYLIST_HEIGHT_PRESETS = [None, 2160, 1440, 1080, 720, 480, 360]


def resolution_name(height: int | None) -> str:
    if not height:
        return "Máxima calidad"
    if height >= 4320:
        return "8K"
    if height >= 2160:
        return "4K"
    if height >= 1440:
        return "2K"
    if height >= 1080:
        return "Full HD"
    if height >= 720:
        return "HD"
    return "SD"


@dataclass
class VideoOption:
    height: int           # alto real del formato (para el selector)
    label_res: int        # lado corto (para videos verticales: 1080 en 1080x1920)
    fps: int
    hdr: bool
    est_size: int | None = None

    @property
    def hfr(self) -> bool:
        return self.fps > 30

    @property
    def label(self) -> str:
        parts = [resolution_name(self.label_res), f"{self.label_res}p"]
        if self.hfr:
            parts.append(f"{self.fps}fps")
        if self.hdr:
            parts.append("HDR")
        return " · ".join(parts)


@dataclass
class PlaylistEntry:
    url: str
    title: str
    duration: float | None = None
    thumbnail: str = ""


@dataclass
class MediaInfo:
    url: str
    title: str
    platform: str
    uploader: str = ""
    duration: float | None = None
    thumbnail: str = ""
    video_options: list[VideoOption] = field(default_factory=list)
    audio_abr: float | None = None
    audio_size: int | None = None
    subtitles: list[str] = field(default_factory=list)
    is_playlist: bool = False
    entries: list[PlaylistEntry] = field(default_factory=list)


@dataclass
class DownloadRequest:
    url: str
    title: str
    platform: str
    kind: str = "video"                  # "video" | "audio"
    video_height: int | None = None      # None = máxima disponible
    video_fps60: bool | None = None      # None = indiferente
    video_hdr: bool | None = None
    container: str = "mp4"
    audio_format: str = "original"
    audio_bitrate: int = 192
    subtitles: list[str] = field(default_factory=list)
    embed_subtitles: bool = False
    dest_dir: str = ""
    thumbnail: str = ""
    job_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])

    @property
    def quality_label(self) -> str:
        if self.kind == "audio":
            if self.audio_format in AUDIO_FORMATS_WITH_BITRATE:
                return f"{self.audio_format.upper()} {self.audio_bitrate} kbps"
            if self.audio_format == "original":
                return "Audio original"
            return self.audio_format.upper()
        parts = [f"{self.video_height}p" if self.video_height else "Máxima"]
        if self.video_fps60:
            parts.append("60fps")
        if self.video_hdr:
            parts.append("HDR")
        parts.append(self.container.upper())
        return " ".join(parts)

    @property
    def quality_key(self) -> str:
        """Clave para detectar descargas duplicadas."""
        if self.kind == "audio":
            return f"audio:{self.audio_format}:{self.audio_bitrate}"
        return f"video:{self.video_height}:{self.video_fps60}:{self.video_hdr}:{self.container}"

    def choice_dict(self) -> dict:
        return {
            "kind": self.kind,
            "video_height": self.video_height,
            "video_fps60": self.video_fps60,
            "container": self.container,
            "audio_format": self.audio_format,
            "audio_bitrate": self.audio_bitrate,
            "subtitles": list(self.subtitles),
            "embed_subtitles": self.embed_subtitles,
        }

    @classmethod
    def from_choice(cls, choice: dict, *, url: str, title: str, platform: str,
                    dest_dir: str, thumbnail: str = "") -> "DownloadRequest":
        req = cls(url=url, title=title, platform=platform, dest_dir=dest_dir, thumbnail=thumbnail)
        req.kind = choice.get("kind", "video") if choice.get("kind") in ("video", "audio") else "video"
        height = choice.get("video_height")
        req.video_height = int(height) if isinstance(height, int) and height > 0 else None
        fps60 = choice.get("video_fps60")
        req.video_fps60 = fps60 if isinstance(fps60, bool) else None
        if choice.get("container") in VIDEO_CONTAINERS:
            req.container = choice["container"]
        if choice.get("audio_format") in AUDIO_FORMATS:
            req.audio_format = choice["audio_format"]
        if choice.get("audio_bitrate") in AUDIO_BITRATES:
            req.audio_bitrate = choice["audio_bitrate"]
        subs = choice.get("subtitles") or []
        req.subtitles = [s for s in subs if isinstance(s, str)]
        req.embed_subtitles = bool(choice.get("embed_subtitles"))
        return req
