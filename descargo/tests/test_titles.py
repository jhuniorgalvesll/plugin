import pytest

from descargo.core.formats import build_ydl_options
from descargo.core.models import DownloadRequest
from descargo.core.titles import smart_title


@pytest.mark.parametrize("info,expected", [
    # Instagram: «Video by usuario» → texto real de la publicación
    ({"title": "Video by loquenodices.co", "uploader": "loquenodices.co", "id": "DbcCW3SxF3Y",
      "description": "Cuando tu pareja te dice «no pasa nada» 😅\n\n#parejas #humor @amigo"},
     "Cuando tu pareja te dice «no pasa nada» 😅"),
    # Instagram sin descripción → nombre de la cuenta
    ({"title": "Video by lliuya.pe", "uploader": "lliuya.pe", "id": "x", "description": ""},
     "Video de lliuya.pe"),
    # Facebook con estadísticas en el título
    ({"title": "1,2 K visualizaciones · 300 reacciones | Receta de ceviche peruano | Cocina Perú",
      "id": "1", "uploader": "Cocina Perú"}, "Receta de ceviche peruano"),
    # TikTok: el título ya es el texto; se quitan hashtags del final
    ({"title": "Así se baila el huayno 🇵🇪 #peru #huayno #fyp", "id": "7", "uploader": "user"},
     "Así se baila el huayno 🇵🇪"),
    # X/Twitter: «Nombre - texto»
    ({"title": "Lliuya - Nuevo video subido hoy", "extractor_key": "Twitter", "id": "9"},
     "Nuevo video subido hoy"),
    # YouTube: título normal se respeta tal cual
    ({"title": "Machu Picchu en 4K | Documental", "id": "abc", "uploader": "Canal"},
     "Machu Picchu en 4K | Documental"),
    # Título igual al ID → descripción
    ({"title": "DbcCW3SxF3Y", "id": "DbcCW3SxF3Y", "description": "Mi primer video\nlinea 2"},
     "Mi primer video"),
])
def test_smart_title(info, expected):
    assert smart_title(info) == expected


def test_long_caption_is_shortened_at_word():
    info = {"title": "Reel by x", "uploader": "x", "id": "1", "description": "palabra " * 40}
    title = smart_title(info)
    assert len(title) <= 101 and title.endswith("…") and "palabr…" not in title


def test_filename_has_no_id():
    opts = build_ydl_options(DownloadRequest(url="u", title="t", platform="p"), "/tmp/x")
    assert opts["outtmpl"]["default"] == "%(title).150B.%(ext)s"
