# -*- mode: python ; coding: utf-8 -*-
# Compilación:  pyinstaller packaging/descargo.spec --noconfirm
from pathlib import Path

import re

from PyInstaller.utils.hooks import (collect_data_files, collect_dynamic_libs, collect_submodules,
                                     copy_metadata)

ROOT = Path(SPECPATH).parent
PKG = ROOT / "descargo"

# Versión única: se lee de descargo/__init__.py
VERSION = re.search(r'APP_VERSION = "([^"]+)"', (PKG / "__init__.py").read_text(encoding="utf-8")).group(1)
parts = tuple(int(x) for x in VERSION.split(".")) + (0,) * (4 - len(VERSION.split(".")))
version_file = Path(workpath) / "version_info.txt"
version_file.parent.mkdir(parents=True, exist_ok=True)
version_file.write_text(
    (ROOT / "packaging" / "version_info.txt").read_text(encoding="utf-8").replace("{v}", VERSION)
    .replace("{vt}", str(parts[:4])), encoding="utf-8")

# copy_metadata: permite saber qué versión del motor trae el instalador
datas = ([(str(PKG / "assets"), "descargo/assets")] + copy_metadata("yt-dlp")
         + collect_data_files("curl_cffi") + collect_data_files("certifi"))
binaries = [(str(p), "descargo/bin") for p in (PKG / "bin").glob("*.exe")]
# curl_cffi: biblioteca nativa para presentarse como navegador real (TikTok la exige)
binaries += collect_dynamic_libs("curl_cffi")

a = Analysis(
    [str(ROOT / "run.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=collect_submodules("yt_dlp.extractor") + collect_submodules("yt_dlp.postprocessor")
    + collect_submodules("mutagen") + collect_submodules("curl_cffi")
    + ["yt_dlp.networking._curlcffi", "yt_dlp.networking._requests", "yt_dlp.networking._websockets"],
    excludes=["tkinter", "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.Qt3DCore",
              "PySide6.QtQuick", "PySide6.QtQml", "PySide6.QtMultimedia", "PySide6.QtCharts",
              "PySide6.QtDataVisualization", "PySide6.QtPdf"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="DescarGO",
    icon=str(PKG / "assets" / "descargo.ico"),
    version=str(version_file),
    console=False,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="DescarGO", upx=False)
