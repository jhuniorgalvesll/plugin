"""Imprime las novedades de la versión actual en Markdown (para GitHub Releases)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from descargo import APP_VERSION, COPYRIGHT_TEXT  # noqa: E402
from descargo.changelog import markdown_for  # noqa: E402

print(f"## Novedades de DescarGO {APP_VERSION}\n")
print(markdown_for(APP_VERSION))
print("\n### Instalación\n")
print("Descarga **DescarGO-Setup-" + APP_VERSION + ".exe** y ábrelo. Si Windows muestra "
      "«Windows protegió su PC», toca «Más información» → «Ejecutar de todas formas».\n")
print("El archivo `.sha256` contiene la huella para verificar que el instalador no fue alterado.\n")
print(f"{COPYRIGHT_TEXT} · ☕ Invítame un café por Yape: 925 459 643")
