"""Novedades de cada versión (se muestran en la app y en GitHub Releases)."""

CHANGELOG: list[tuple[str, list[str]]] = [
    ("1.5.0", [
        "👑 Panel de administrador: lista de clientes con el estado de su licencia (activa, por "
        "vencer, vencida o permanente), buscador e ingresos registrados.",
        "🔄 Renovar con un clic: doble clic en un cliente para generarle una licencia nueva con "
        "su mismo código de equipo.",
        "💰 Registra el monto pagado y una nota (por ejemplo, el n.º de operación de Yape).",
        "💬 «Copiar mensaje para el cliente»: copia la licencia junto con las instrucciones para activarla.",
    ]),
    ("1.4.2", [
        "🔧 Arreglado el error «Acceso denegado» al actualizar: ahora la actualización espera a "
        "que DescarGO se cierre por completo antes de instalar.",
        "🪄 Actualización invisible: sin asistente ni ventanas del instalador. DescarGO se cierra "
        "unos segundos, se actualiza y se vuelve a abrir solo, mostrando esta pantalla.",
        "📷 Sigue a @lliuya.pe en Instagram desde la pantalla de novedades.",
    ]),
    ("1.4.1", [
        "⬆ Actualización en un clic: DescarGO revisa GitHub al abrirse y cada hora; cuando hay "
        "versión nueva aparece «Actualizar ahora». Se descarga, se verifica, se instala sola sin "
        "asistente y la app se vuelve a abrir.",
    ]),
    ("1.4.0", [
        "♾️ Descargas sin límite diario para todos.",
        "🔒 Sin licencia activa (plan gratuito o licencia vencida) las descargas son en calidad "
        "estándar: video hasta 480p y audio hasta 128 kbps.",
        "💎 Con licencia: alta calidad — HD, Full HD, 2K, 4K, 60fps, HDR, audio 320 kbps, FLAC "
        "y audio original.",
        "⏰ Cuando una licencia vence, la app avisa y sigue descargando en calidad estándar "
        "hasta que la renueves.",
    ]),
    ("1.3.2", [
        "👑 Activa el modo autor desde la app: en «Licencia» toca «Soy el autor: cargar mi llave» "
        "y elige tu archivo. Aparece al instante el menú «Generar licencias».",
        "🛠 Generador mejorado: licencias de 1 a 12 meses (por ejemplo 5 meses), 2 años, "
        "permanentes o hasta una fecha que elijas, mostrando el día exacto en que vencen.",
        "📋 Historial de licencias emitidas: cliente, código de equipo, vencimiento y botón "
        "para volver a copiar cualquier licencia.",
    ]),
    ("1.3.1", [
        "👑 Modo autor: el computador con la llave de licencias de lliuya.pe descarga sin "
        "límites y ve el generador de licencias. Los demás usuarios tienen el plan gratuito "
        "de 10 descargas por día o su licencia.",
    ]),
    ("1.3.0", [
        "🔔 Actualizaciones automáticas: cada vez que abres DescarGO revisa si hay una versión "
        "nueva y te pregunta si quieres instalarla ahora (se descarga y verifica sola).",
        "🔑 Licencias: el plan gratuito permite 10 descargas por día. Con una licencia las "
        "descargas son ilimitadas. Obtén la tuya desde «Licencia» en la barra lateral.",
        "📊 La barra lateral muestra cuántas descargas gratuitas te quedan hoy.",
    ]),
    ("1.2.2", [
        "🎵 TikTok vuelve a funcionar: DescarGO ahora se presenta como un navegador real "
        "(Chrome/Safari), como exige TikTok. Antes fallaba con «Unexpected response from "
        "webpage request».",
        "🌐 Más sitios compatibles: se incluyen los componentes completos del motor "
        "(conexiones modernas, compresión y certificados actualizados).",
        "💬 Mensaje claro cuando una plataforma bloquea la solicitud, con la solución.",
    ]),
    ("1.2.1", [
        "🏷️ Los archivos se guardan con el título original del video en todas las plataformas. "
        "En Instagram (que solo dice «Video by usuario») se usa el texto real de la publicación; "
        "en Facebook se quitan las visualizaciones y reacciones del título.",
        "✂️ El nombre del archivo ya no lleva el código entre corchetes (por ejemplo [DbcCW3SxF3Y]). "
        "Si el nombre se repite, se agrega (1), (2)…",
    ]),
    ("1.2.0", [
        "⚡ Análisis mucho más rápido: los enlaces de YouTube con «&list=…» (por ejemplo, las "
        "listas Mix) ahora analizan solo el video. Si quieres la lista completa, hay un botón "
        "«Descargar la lista completa».",
        "🖼️ La portada del video aparece al instante mientras se analiza (YouTube) o en un "
        "segundo (TikTok, Vimeo, Dailymotion, SoundCloud).",
        "🚀 La descarga empieza de inmediato: se reutiliza el análisis en lugar de repetirlo, "
        "y el motor se precarga al abrir la app.",
        "📷 Página del autor: sigue a @lliuya.pe en Instagram desde la barra lateral, "
        "«Acerca de» e «Invítame un café».",
    ]),
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
