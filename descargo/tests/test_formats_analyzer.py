import pytest
import yt_dlp

from descargo.core import analyzer
from descargo.core.formats import build_ydl_options, video_selector
from descargo.core.models import DownloadRequest


def fmt(fid, height=None, fps=30, vcodec="avc1", acodec="none", ext="mp4", dr="SDR", size=1000, abr=None, width=None):
    f = {"format_id": fid, "ext": ext, "vcodec": vcodec, "acodec": acodec, "url": f"http://x/{fid}",
         "protocol": "https", "filesize": size, "dynamic_range": dr}
    if height:
        f.update(height=height, width=width or int(height * 16 / 9), fps=fps)
    if abr:
        f["abr"] = abr
    return f


FORMATS = [
    fmt("a1", vcodec="none", acodec="mp4a.40.2", ext="m4a", abr=128, size=3_000_000),
    fmt("a2", vcodec="none", acodec="opus", ext="webm", abr=160, size=3_500_000),
    fmt("360", 360, size=5_000_000),
    fmt("720", 720, size=20_000_000),
    fmt("1080", 1080, size=50_000_000),
    fmt("1080p60", 1080, fps=60, size=80_000_000),
    fmt("2160", 2160, vcodec="vp9", ext="webm", size=300_000_000),
    fmt("2160hdr", 2160, fps=60, vcodec="vp09.02", ext="webm", dr="HDR10", size=400_000_000),
]


def pick(selector):
    ydl = yt_dlp.YoutubeDL({"quiet": True})
    sel = ydl.build_format_selector(selector)
    ctx = {"formats": [dict(f) for f in FORMATS], "incomplete_formats": False}
    chosen = list(sel(ctx))
    return chosen[0]["format_id"] if chosen else None


def test_selector_exact_height_and_fps():
    assert pick(video_selector(1080, False, False)).startswith("1080+")
    assert pick(video_selector(1080, True, False)).startswith("1080p60+")
    assert pick(video_selector(2160, True, True)).startswith("2160hdr+")
    assert pick(video_selector(2160, False, False)).startswith("2160+")
    # resolución inexistente: baja a la más cercana inferior
    assert pick(video_selector(1440)).split("+")[0] in ("1080", "1080p60")
    assert pick(video_selector(None)).split("+")[0] in ("2160", "2160hdr")


def test_build_video_options_groups_and_sizes():
    options, abr, audio_size = analyzer.build_video_options(FORMATS, duration=100)
    labels = [o.label for o in options]
    assert labels[0] == "4K · 2160p · 60fps · HDR"
    assert "Full HD · 1080p · 60fps" in labels and "Full HD · 1080p" in labels
    assert labels[-1] == "SD · 360p"
    assert abr == 160 and audio_size == 3_500_000
    full_hd = next(o for o in options if o.label == "Full HD · 1080p")
    assert full_hd.est_size == 50_000_000 + 3_500_000


def test_vertical_video_uses_short_side():
    options, _, _ = analyzer.build_video_options([fmt("v", 1920, width=1080)], None)
    assert options[0].label == "Full HD · 1080p"
    assert options[0].height == 1920


def test_drm_formats_ignored():
    f = fmt("drm", 1080)
    f["has_drm"] = True
    options, _, _ = analyzer.build_video_options([f, fmt("720", 720)], None)
    assert [o.label_res for o in options] == [720]


def test_info_to_media_single_and_playlist():
    info = {"id": "x", "title": "Mi video", "extractor_key": "Youtube", "duration": 100,
            "formats": FORMATS, "webpage_url": "https://www.youtube.com/watch?v=x",
            "subtitles": {"es": [], "live_chat": []}, "automatic_captions": {"en": [], "fr": []}}
    media = analyzer.info_to_media("https://youtu.be/x", info)
    assert media.platform == "YouTube" and media.title == "Mi video"
    assert media.subtitles == ["es", "en"]
    assert not media.is_playlist

    pl = {"_type": "playlist", "title": "Lista", "extractor_key": "YoutubeTab",
          "entries": [{"url": "https://www.youtube.com/watch?v=1", "title": "Uno"},
                      {"url": "https://www.netflix.com/watch/1", "title": "Pago"},
                      None, {"url": "abc", "title": "sin enlace"}]}
    media = analyzer.info_to_media("https://youtube.com/playlist?list=1", pl)
    assert media.is_playlist and [e.title for e in media.entries] == ["Uno"]


def test_audio_options():
    req = DownloadRequest(url="u", title="t", platform="p", kind="audio", audio_format="mp3", audio_bitrate=320)
    opts = build_ydl_options(req, "/tmp/x")
    pp = opts["postprocessors"][0]
    assert opts["format"] == "ba/b"
    assert pp == {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "320"}
    req.audio_format = "original"
    pp = build_ydl_options(req, "/tmp/x")["postprocessors"][0]
    assert pp["preferredcodec"] == "best" and pp["preferredquality"] == "0"


def test_video_options_with_subtitles():
    req = DownloadRequest(url="u", title="t", platform="p", video_height=1080, container="mp4",
                          subtitles=["es"], embed_subtitles=True)
    opts = build_ydl_options(req, "/tmp/x", cookies_browser="firefox", rate_limit_kb=500)
    assert opts["merge_output_format"] == "mp4/mkv"
    assert opts["cookiesfrombrowser"] == ("firefox",)
    assert opts["ratelimit"] == 500 * 1024
    assert opts["subtitleslangs"] == ["es"]
    assert any(p["key"] == "FFmpegEmbedSubtitle" for p in opts["postprocessors"])


@pytest.mark.parametrize("msg,expected", [
    ("ERROR: Unsupported URL: https://x", "No se encontró"),
    ("Sign in to confirm you're not a bot", "robot"),
    ("ERROR: Private video", "privado"),
    ("This video is DRM protected", "DRM"),
])
def test_friendly_errors(msg, expected):
    assert expected in analyzer.friendly_error(msg)


def test_quality_labels_and_choice_roundtrip():
    req = DownloadRequest(url="u", title="t", platform="p", video_height=2160, video_fps60=True, container="mkv")
    assert req.quality_label == "2160p 60fps MKV"
    again = DownloadRequest.from_choice(req.choice_dict(), url="u2", title="t2", platform="p", dest_dir="/d")
    assert again.quality_key == req.quality_key and again.url == "u2"
