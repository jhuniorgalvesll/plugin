import functools
import http.server
import shutil
import subprocess
import threading

import pytest

from descargo.core import analyzer
from descargo.core.downloader import STATUS_DONE, DownloadJob, JobSettings
from descargo.core.models import DownloadRequest
from descargo.utils import find_ffmpeg_dir


@pytest.mark.parametrize("url,video,playlist", [
    ("https://www.youtube.com/watch?v=Rt7VigI12vo&list=RDbH1vr-5bsZM&index=5",
     "https://www.youtube.com/watch?v=Rt7VigI12vo", ""),                       # Mix: solo el video
    ("https://www.youtube.com/watch?v=Rt7VigI12vo&list=PLabc123",
     "https://www.youtube.com/watch?v=Rt7VigI12vo", "https://www.youtube.com/playlist?list=PLabc123"),
    ("https://youtu.be/Rt7VigI12vo", "https://youtu.be/Rt7VigI12vo", ""),
    ("https://www.youtube.com/playlist?list=PLabc123", "https://www.youtube.com/playlist?list=PLabc123", ""),
    ("https://vimeo.com/123", "https://vimeo.com/123", ""),
])
def test_split_watch_playlist(url, video, playlist):
    assert analyzer.split_watch_playlist(url) == (video, playlist)


def test_quick_thumbnail():
    for url in ("https://www.youtube.com/watch?v=Rt7VigI12vo&list=RDx", "https://youtu.be/Rt7VigI12vo",
                "https://www.youtube.com/shorts/Rt7VigI12vo"):
        assert analyzer.quick_thumbnail(url) == "https://i.ytimg.com/vi/Rt7VigI12vo/hqdefault.jpg"
    assert analyzer.quick_thumbnail("https://vimeo.com/1") == ""
    assert analyzer.oembed_preview("https://example.com/x") == ("", "")


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg no instalado")
def test_download_reuses_analysis(tmp_path):
    root = tmp_path / "www"
    root.mkdir()
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc=size=160x90:rate=10",
                    "-t", "1", "-pix_fmt", "yuv420p", str(root / "clip.mp4")], check=True)
    (root / "page.html").write_text('<html><head><title>Prueba</title></head>'
                                    '<body><video src="/clip.mp4"></video></body></html>')
    hits = []

    class Counting(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            hits.append(self.path)
            super().do_GET()

    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Counting, directory=str(root)))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{httpd.server_address[1]}/page.html"
    try:
        media = analyzer.analyze(url)
        assert media.raw_info and not media.playlist_url
        pages_after_analysis = hits.count("/page.html")
        req = DownloadRequest(url=media.url, title=media.title, platform=media.platform,
                              dest_dir=str(tmp_path / "out"), prefetched_info=media.raw_info)
        result = DownloadJob(req, JobSettings(ffmpeg_dir=find_ffmpeg_dir(), antivirus_enabled=False)).run()
        assert result.status == STATUS_DONE, result.message
        assert hits.count("/page.html") == pages_after_analysis  # no se volvió a analizar la página
    finally:
        httpd.shutdown()
