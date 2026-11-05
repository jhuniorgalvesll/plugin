"""Novedades de cada versión (se muestran en la app y en GitHub Releases)."""

CHANGELOG: list[tuple[str, list[str]]] = [
    ("1.1.0", [
        "🔄 Centro de actualizaciones: el motor de descarga se actualiza solo, una vez al día, "
        "desde su sitio oficial y con verificación SHA-256. Así las descargas siguen funcionando "
        "aunque YouTube, TikTok o Instagram cambien.",
        "🎉 Aviso de nueva versión: DescarGO revisa si hay una versión nueva y la descarga e "
        "instala con un clic (instalador verificado con SHA-256).",
        "🎵 Portada y datos dentro del archivo: los MP3, M4A, OPUS, FLAC y MP4 guardan la "
        "miniatura como carátula, además del título y el artista.",
        "🔔 Avisos de Windows cuando termina una descarga o se bloquea una amenaza, aunque la "
        "app esté minimizada. Icono junto al reloj con acceso rápido.",
        "📦 Descarga directa del instalador desde GitHub Releases.",
    ]),
    ("1.0.0", [
        "Primera versión: video o audio con calidad a elección, más de 1.800 sitios, cola sin "
        "límites, historial, análisis de seguridad de 5 capas y bloqueo de páginas de pago.",
    ]),
]


def notes_for(version: str) -> list[str]:
    for ver, notes in CHANGELOG:
        if ver == version:
            return notes
    return []


def markdown_for(version: str) -> str:
    return "\n".join(f"- {line}" for line in notes_for(version))
