import shutil
import subprocess

import pytest

from descargo.core.security import (CLEAN, FAIL, OK, SUSPICIOUS, THREAT, AntivirusEngine,
                                    SecurityScanner, sniff)

MP4_HEADER = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 100
HAS_FFMPEG = shutil.which("ffmpeg") is not None


def scanner(**kw):
    kw.setdefault("antivirus_enabled", False)
    kw.setdefault("use_ffprobe", False)
    return SecurityScanner(**kw)


def write(tmp_path, name, data):
    p = tmp_path / name
    p.write_bytes(data)
    return p


def test_exe_disguised_as_mp4_is_threat(tmp_path):
    p = write(tmp_path, "pelicula.mp4", b"MZ\x90\x00" + b"\x00" * 200)
    report = scanner().scan(p)
    assert report.verdict == THREAT
    assert "programa de Windows" in report.summary()


@pytest.mark.parametrize("name", ["video.mp4.exe", "song.mp3.scr", "clip.bat", "a.zip", "x.html", "noext"])
def test_dangerous_extensions_blocked(tmp_path, name):
    assert scanner().scan(write(tmp_path, name, MP4_HEADER)).verdict == THREAT


def test_double_extension_with_media_suffix_blocked(tmp_path):
    assert scanner().scan(write(tmp_path, "factura.exe.mp4", MP4_HEADER)).verdict == THREAT


def test_title_with_dot_com_is_not_flagged(tmp_path):
    report = scanner().scan(write(tmp_path, "Visita example.com [abc].mp4", MP4_HEADER))
    assert report.verdict == CLEAN


def test_rtlo_trick_blocked(tmp_path):
    p = write(tmp_path, "video‮4pm.exe.mp4", MP4_HEADER)
    assert scanner().scan(p).verdict == THREAT


def test_html_decoy_blocked(tmp_path):
    p = write(tmp_path, "video.mp4", b"<!DOCTYPE html><html><script>alert(1)</script>")
    assert scanner().scan(p).verdict == THREAT


def test_zip_as_mp3_blocked(tmp_path):
    assert scanner().scan(write(tmp_path, "tema.mp3", b"PK\x03\x04" + b"\x00" * 50)).verdict == THREAT


def test_valid_subtitle_and_malicious_subtitle(tmp_path):
    good = write(tmp_path, "v.es.srt", "1\n00:00:01,000 --> 00:00:02,000\nHola\n".encode())
    assert scanner().scan(good).verdict == CLEAN
    bad = write(tmp_path, "v.en.vtt", b"WEBVTT\n\n<script>evil()</script>")
    assert scanner().scan(bad).verdict == THREAT


def test_empty_file_suspicious(tmp_path):
    assert scanner().scan(write(tmp_path, "v.mp4", b"")).verdict == SUSPICIOUS


def test_sniff_signatures():
    assert sniff(b"\x1a\x45\xdf\xa3" + b"\x00" * 20)[0] == "media"
    assert sniff(b"ID3\x04" + b"\x00" * 20)[0] == "media"
    assert sniff(b"OggS" + b"\x00" * 20)[0] == "media"
    assert sniff(b"\x7fELF" + b"\x00" * 20)[0] == "executable"
    assert sniff(b"#EXTM3U\n")[0] == "playlist"


class FakeEngine(AntivirusEngine):
    name = "FakeAV"

    def __init__(self, status, detail=""):
        self.status, self.detail = status, detail

    def scan(self, path):
        return self.status, self.detail


def test_antivirus_threat_and_clean(tmp_path):
    p = write(tmp_path, "v.mp4", MP4_HEADER)
    assert scanner(antivirus_enabled=True, engine=FakeEngine(FAIL, "Eicar")).scan(p).verdict == THREAT
    assert scanner(antivirus_enabled=True, engine=FakeEngine(OK, "ok")).scan(p).verdict == CLEAN
    assert scanner(antivirus_enabled=True, engine=FakeEngine("warn", "err")).scan(p).verdict == SUSPICIOUS


@pytest.mark.skipif(not HAS_FFMPEG, reason="ffmpeg no instalado")
def test_ffprobe_validates_real_and_fake_media(tmp_path):
    real = tmp_path / "real.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc=size=160x90:rate=10",
                    "-t", "1", "-pix_fmt", "yuv420p", str(real)], check=True)
    assert SecurityScanner(antivirus_enabled=False).scan(real).verdict == CLEAN
    fake = write(tmp_path, "fake.mp4", MP4_HEADER)  # firma correcta pero sin pistas
    assert SecurityScanner(antivirus_enabled=False).scan(fake).verdict == THREAT
