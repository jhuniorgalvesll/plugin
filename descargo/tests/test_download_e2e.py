"""Descarga real de principio a fin contra un servidor HTTP local (sin internet)."""

import functools
import http.server
import shutil
import subprocess
import threading

import pytest

from descargo.config import Settings
from descargo.core.downloader import (STATUS_BLOCKED, STATUS_DONE, STATUS_THREAT, DownloadJob,
                                      JobSettings)
from descargo.core.library import Library
from descargo.core.models import DownloadRequest
from descargo.utils import find_ffmpeg_dir

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg no instalado")


@pytest.fixture
def server(tmp_path):
    root = tmp_path / "www"
    root.mkdir()
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc=size=320x180:rate=15",
                    "-f", "lavfi", "-i", "sine=frequency=440", "-t", "2", "-pix_fmt", "yuv420p",
                    "-c:v", "libx264", "-c:a", "aac", "-shortest", str(root / "clip.mp4")], check=True)
    (root / "trampa.mp4").write_bytes(b"MZ\x90\x00" + b"\x00" * 4096)
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(root))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


def settings():
    return JobSettings(ffmpeg_dir=find_ffmpeg_dir(), antivirus_enabled=False)


def test_video_download_is_scanned_and_delivered(server, tmp_path):
    dest = tmp_path / "descargas"
    req = DownloadRequest(url=f"{server}/clip.mp4", title="clip", platform="Web", dest_dir=str(dest))
    events = []
    result = DownloadJob(req, settings(), on_progress=events.append).run()
    assert result.status == STATUS_DONE, result.message
    assert len(result.files) == 1 and result.files[0].startswith(str(dest / "Web"))
    assert result.reports[0].verdict == "clean"
    assert any(e["phase"] == "scanning" for e in events)


def test_audio_conversion_to_mp3(server, tmp_path):
    req = DownloadRequest(url=f"{server}/clip.mp4", title="clip", platform="Web", kind="audio",
                          audio_format="mp3", audio_bitrate=128, dest_dir=str(tmp_path / "d"))
    result = DownloadJob(req, settings()).run()
    assert result.status == STATUS_DONE, result.message
    assert result.files[0].endswith(".mp3")


def test_disguised_executable_is_removed(server, tmp_path):
    dest = tmp_path / "d"
    req = DownloadRequest(url=f"{server}/trampa.mp4", title="trampa", platform="Web", dest_dir=str(dest))
    result = DownloadJob(req, settings()).run()
    assert result.status == STATUS_THREAT
    assert not result.files
    assert not any(dest.rglob("*.mp4"))


def test_paid_site_never_downloads(tmp_path):
    req = DownloadRequest(url="https://www.netflix.com/watch/1", title="x", platform="x", dest_dir=str(tmp_path))
    assert DownloadJob(req, settings()).run().status == STATUS_BLOCKED


def test_library_and_settings_roundtrip(tmp_path):
    lib = Library(tmp_path / "h.db")
    f = tmp_path / "a.mp4"
    f.write_bytes(b"x")
    lib.add(job_id="1", url="u", title="Mi título", platform="YouTube", kind="video", quality="1080p",
            quality_key="k", filepath=str(f), size=1, status="done", verdict="clean")
    assert lib.find_completed("u", "k") is not None
    assert lib.find_completed("u", "otra") is None
    assert lib.search("título")[0].platform == "YouTube"

    s = Settings.load(tmp_path / "s.json")
    s.max_concurrent = 99
    s.save()
    assert Settings.load(tmp_path / "s.json").max_concurrent == 10
