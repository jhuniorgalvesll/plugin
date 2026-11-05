import functools
import hashlib
import http.server
import json
import subprocess
import sys
import textwrap
import threading
import zipfile
from pathlib import Path

import pytest

from descargo.core import updater
from descargo.core.formats import build_ydl_options
from descargo.core.models import DownloadRequest


def test_version_compare():
    assert updater.is_newer("2026.11.01", "2026.10.26")
    assert not updater.is_newer("2026.10.26", "2026.10.26")
    assert updater.is_newer("1.10.0", "1.9.9")
    assert updater.parse_version("v1.2.0") == (1, 2, 0)


@pytest.fixture
def server(tmp_path):
    root = tmp_path / "www"
    root.mkdir()

    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass

    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(root)))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield root, f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


def _fake_wheel(path: Path, version: str) -> str:
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("yt_dlp/__init__.py", "MARK = 'actualizado'\n")
        zf.writestr("yt_dlp/version.py", f"__version__ = '{version}'\n")
        zf.writestr("yt_dlp/extra/__init__.py", "")
        zf.writestr("../evil.py", "raise SystemExit")          # ruta peligrosa: se ignora
        zf.writestr("yt_dlp-x.dist-info/METADATA", "x")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_install_engine_verifies_and_extracts(server, monkeypatch):
    root, base = server
    sha = _fake_wheel(root / "m.whl", "2099.1.1")
    update = updater.EngineUpdate("2099.1.1", f"{base}/m.whl", sha)
    assert updater.install_engine(update) == "2099.1.1"
    state = json.loads((updater.engine_dir() / "estado.json").read_text())
    folder = updater.engine_dir() / state["folder"]
    assert (folder / "yt_dlp" / "version.py").is_file()
    assert not (folder / "yt_dlp-x.dist-info").exists()
    assert not any(updater.engine_dir().parent.rglob("evil.py"))


def test_install_engine_rejects_bad_hash(server):
    root, base = server
    _fake_wheel(root / "m.whl", "2099.1.1")
    update = updater.EngineUpdate("2099.1.1", f"{base}/m.whl", "0" * 64)
    with pytest.raises(updater.UpdateError, match="SHA-256"):
        updater.install_engine(update)
    assert not (updater.engine_dir() / "estado.json").exists()


def test_activated_engine_is_used(server, isolated_app_data):
    root, base = server
    sha = _fake_wheel(root / "m.whl", "2099.1.1")
    updater.install_engine(updater.EngineUpdate("2099.1.1", f"{base}/m.whl", sha))
    code = textwrap.dedent("""
        from descargo.core import updater
        updater.activate_engine()
        import yt_dlp, yt_dlp.version, yt_dlp.extra
        print(yt_dlp.MARK, yt_dlp.version.__version__, updater.engine_source())
    """)
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                         cwd=str(Path(__file__).resolve().parents[1]),
                         env={**__import__("os").environ, "XDG_CONFIG_HOME": str(isolated_app_data),
                              "APPDATA": str(isolated_app_data)})
    assert out.stdout.split() == ["actualizado", "2099.1.1", "actualizado"], out.stderr


def test_older_engine_is_ignored(server, isolated_app_data):
    root, base = server
    sha = _fake_wheel(root / "m.whl", "2000.1.1")
    updater.install_engine(updater.EngineUpdate("2000.1.1", f"{base}/m.whl", sha))
    code = "from descargo.core import updater; updater.activate_engine(); print(updater.engine_source())"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                         cwd=str(Path(__file__).resolve().parents[1]),
                         env={**__import__("os").environ, "XDG_CONFIG_HOME": str(isolated_app_data)})
    assert out.stdout.strip() == "incluido", out.stderr


def test_check_app_update_filters_releases(monkeypatch):
    releases = [
        {"tag_name": "otro-proyecto-v9.0", "assets": []},
        {"tag_name": "descargo-v9.9.9", "prerelease": True, "assets": []},
        {"tag_name": "descargo-v1.2.0", "body": "Notas", "html_url": "https://x/r",
         "assets": [{"name": "DescarGO-Setup-1.2.0.exe", "browser_download_url": "https://x/s.exe"},
                    {"name": "DescarGO-Setup-1.2.0.exe.sha256", "browser_download_url": "https://x/s.sha"}]},
        {"tag_name": "descargo-v1.0.0", "assets": []},
    ]
    monkeypatch.setattr(updater, "_get_json", lambda url, timeout=20: releases)
    update = updater.check_app_update("1.1.0")
    assert update.version == "1.2.0" and update.installer_url == "https://x/s.exe"
    assert update.sha256_url == "https://x/s.sha"
    assert updater.check_app_update("1.2.0") is None


def test_download_installer_checks_hash(server, monkeypatch):
    root, base = server
    (root / "s.exe").write_bytes(b"instalador")
    good = hashlib.sha256(b"instalador").hexdigest()
    (root / "s.sha").write_text(f"{good}  s.exe")
    (root / "bad.sha").write_text("f" * 64)
    upd = updater.AppUpdate("1.2.0", "", "", f"{base}/s.exe", "DescarGO-Setup-1.2.0.exe", f"{base}/s.sha")
    assert updater.download_installer(upd).read_bytes() == b"instalador"
    upd.sha256_url = f"{base}/bad.sha"
    with pytest.raises(updater.UpdateError):
        updater.download_installer(upd)


def test_cover_postprocessor_is_last():
    req = DownloadRequest(url="u", title="t", platform="p", video_height=1080, container="mp4",
                          subtitles=["es"], embed_subtitles=True)
    opts = build_ydl_options(req, "/tmp/x")
    assert opts["writethumbnail"] and opts["postprocessors"][-1]["key"] == "EmbedThumbnail"
    req.container = "webm"
    assert "writethumbnail" not in build_ydl_options(req, "/tmp/x")
    audio = DownloadRequest(url="u", title="t", platform="p", kind="audio", audio_format="wav")
    assert "writethumbnail" not in build_ydl_options(audio, "/tmp/x")
    audio.audio_format = "mp3"
    assert build_ydl_options(audio, "/tmp/x", embed_thumbnail=False).get("writethumbnail") is None
