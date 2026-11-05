"""Genera assets/descargo.ico y descargo.png a partir del logo SVG.

Uso:  python tools/make_icon.py   (requiere PySide6 y Pillow)
"""

import io
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "descargo" / "assets"

from PIL import Image  # noqa: E402
from PySide6.QtCore import QBuffer, QIODevice, Qt  # noqa: E402
from PySide6.QtGui import QGuiApplication, QImage, QPainter  # noqa: E402
from PySide6.QtSvg import QSvgRenderer  # noqa: E402


def render(size: int) -> Image.Image:
    image = QImage(size, size, QImage.Format_ARGB32)
    image.fill(Qt.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing)
    QSvgRenderer(str(ASSETS / "descargo.svg")).render(painter)
    painter.end()
    buf = QBuffer()
    buf.open(QIODevice.WriteOnly)
    image.save(buf, "PNG")
    return Image.open(io.BytesIO(bytes(buf.data())))


def main() -> int:
    QGuiApplication(sys.argv)
    big = render(256)
    big.save(ASSETS / "descargo.png")
    big.save(ASSETS / "descargo.ico", sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)])
    print("Iconos generados en", ASSETS)
    return 0


if __name__ == "__main__":
    sys.exit(main())
