# -*- mode: python ; coding: utf-8 -*-
# Compilación:  pyinstaller packaging/descargo.spec --noconfirm
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

ROOT = Path(SPECPATH).parent
PKG = ROOT / "descargo"

datas = [(str(PKG / "assets"), "descargo/assets")]
binaries = [(str(p), "descargo/bin") for p in (PKG / "bin").glob("*.exe")]

a = Analysis(
    [str(ROOT / "run.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=collect_submodules("yt_dlp.extractor") + collect_submodules("yt_dlp.postprocessor"),
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
    version=str(ROOT / "packaging" / "version_info.txt"),
    console=False,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="DescarGO", upx=False)
