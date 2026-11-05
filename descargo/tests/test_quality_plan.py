import pytest
import yt_dlp

from descargo.core.formats import build_ydl_options
from descargo.core.licensing import STANDARD_MAX_KBPS, LicenseManager, apply_standard_quality
from descargo.core.models import DownloadRequest


def fmt(fid, w=None, h=None, vcodec="avc1", acodec="none", abr=None, ext="mp4", fps=30):
    f = {"format_id": fid, "url": f"http://x/{fid}", "ext": ext, "vcodec": vcodec, "acodec": acodec,
         "protocol": "https"}
    if h:
        f.update(width=w, height=h, fps=fps)
    if abr:
        f["abr"] = abr
    return f


LANDSCAPE = [fmt("a48", vcodec="none", acodec="opus", abr=48, ext="webm"),
             fmt("a128", vcodec="none", acodec="mp4a", abr=128, ext="m4a"),
             fmt("a160", vcodec="none", acodec="opus", abr=160, ext="webm"),
             fmt("360", 640, 360), fmt("480", 854, 480), fmt("720", 1280, 720),
             fmt("1080", 1920, 1080), fmt("2160", 3840, 2160, fps=60)]
VERTICAL = [fmt("a128", vcodec="none", acodec="mp4a", abr=128, ext="m4a"),
            fmt("v480", 480, 854), fmt("v720", 720, 1280), fmt("v1080", 1080, 1920)]


def chosen(req, formats):
    opts = build_ydl_options(req, "/tmp/x")
    params = {"quiet": True, "format": opts["format"], "format_sort": opts.get("format_sort", []),
              "simulate": True, "logger": opts["logger"]}
    with yt_dlp.YoutubeDL(params) as ydl:
        info = ydl.process_ie_result({"id": "t", "title": "t", "formats": [dict(f) for f in formats],
                                      "extractor": "x", "extractor_key": "X", "webpage_url": "http://x"},
                                     download=False)
    return info["format_id"]


def capped(**kw):
    req = DownloadRequest(url="u", title="t", platform="p", **kw)
    apply_standard_quality(req)
    return req


def test_standard_video_never_above_480_and_audio_128():
    assert chosen(capped(), LANDSCAPE) == "480+a128"
    assert chosen(capped(video_height=1080), LANDSCAPE) == "480+a128"   # pidió 1080: se limita
    assert chosen(capped(video_height=360), LANDSCAPE) == "360+a128"    # pidió menos: se respeta


def test_standard_vertical_uses_short_side():
    assert chosen(capped(), VERTICAL) == "v480+a128"


def test_premium_keeps_full_quality():
    req = DownloadRequest(url="u", title="t", platform="p")
    assert chosen(req, LANDSCAPE).startswith("2160+")


def test_standard_audio_formats_and_bitrate():
    for fmt_name in ("original", "flac", "wav"):
        req = capped(kind="audio", audio_format=fmt_name, audio_bitrate=320)
        assert req.audio_format == "mp3" and req.audio_bitrate == STANDARD_MAX_KBPS
    req = capped(kind="audio", audio_format="opus", audio_bitrate=96)
    assert req.audio_format == "opus" and req.audio_bitrate == 96
    assert chosen(req, LANDSCAPE) == "a128"
    pp = build_ydl_options(req, "/tmp/x")["postprocessors"][0]
    assert pp["preferredquality"] == "96"


def test_manager_enforce(tmp_path):
    lm = LicenseManager(tmp_path)
    req = DownloadRequest(url="u", title="t", platform="p", video_height=2160, video_fps60=True)
    assert lm.enforce(req) and req.quality_cap == 480 and req.quality_label == "Estándar 480p MP4"
