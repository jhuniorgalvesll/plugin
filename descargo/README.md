<p align="center">
  <img src="descargo/assets/descargo.png" width="96" alt="DescarGO">
</p>

<h1 align="center">DescarGO</h1>
<p align="center"><b>Descarga y listo</b> — video y audio de cualquier página pública, seguro y sin límites.</p>
<p align="center">© 2026 <a href="https://lliuya.pe">lliuya.pe</a> — Todos los derechos reservados</p>

---

## ¿Qué hace?

| | |
|---|---|
| 🌐 **Fuentes** | YouTube, Facebook, Facebook Reels, Instagram, TikTok, Vimeo, X, Twitch, Reddit, SoundCloud… más de 1.800 sitios, además de un detector genérico para páginas con video y enlaces directos `.mp4` / `.mp3`. |
| 🎬🎵 **Tú eliges** | Antes de descargar: **video o solo audio**, la **calidad** (solo se muestran las que existen de verdad: 8K, 4K, 2K, 1080p 60fps, HDR…), el formato y los subtítulos. |
| 🎵 **Audio** | Original sin recomprimir (recomendado), MP3, M4A, OPUS, OGG, FLAC y WAV, a 320, 256, 192 o 128 kbps. |
| 📋 **Sin límites** | Sin tope diario, sin límite de playlists, sin licencia ni publicidad. Cola con pausa, reanudación y cancelación. |
| 📚 **Listas y perfiles** | Marca qué elementos de una lista quieres. Lo que ya descargaste se omite (descarga incremental). |
| 🛡️ **Seguridad** | Cada archivo pasa por cuarentena y un análisis de 5 capas antes de llegar a tu carpeta. |
| 🚫 **Uso responsable** | Bloquea páginas de pago (Netflix, Disney+, Spotify, Udemy, OnlyFans…) y contenido con DRM. |
| ☕ **Invítame un café** | Apoyo voluntario por Yape: **925 459 643**. |

## 🛡️ Cómo protege tu computador

```
Descarga → carpeta de CUARENTENA aislada
   1. Tipo real del archivo: lee su firma interna (no confía en la extensión) y lo valida con FFprobe
   2. Bloqueo de .exe, .bat, .scr, .js…, dobles extensiones (video.mp4.exe) y nombres disfrazados (Unicode RTLO)
   3. Subtítulos: solo texto plano, sin scripts
   4. Antivirus del sistema: Microsoft Defender (Windows) o ClamAV (Mac/Linux)
   5. VirusTotal (opcional): solo se envía la huella SHA-256, nunca el archivo
→ ✅ Seguro: se mueve a tu carpeta  ·  ⚠️ Sospechoso: queda en cuarentena  ·  ❌ Amenaza: se elimina
```

Las capas 1 a 3 y el bloqueo de páginas de pago **no se pueden desactivar**. Si una descarga falla a medias, lo que llegó también se analiza y nunca se entrega un archivo incompleto.

## 💻 Instalar en Windows

**Opción A, descargar la versión compilada:** en GitHub, entra a **Actions → «DescarGO — compilar para Windows»**, abre la ejecución más reciente y descarga `DescarGO-Setup-Windows` (instalador) o `DescarGO-Portable-Windows`.

**Opción B, compilar tú mismo:** con [Python 3.12](https://www.python.org/downloads/) instalado, abre PowerShell en la carpeta `descargo`:

```powershell
powershell -ExecutionPolicy Bypass -File build_windows.ps1
```

El script instala las dependencias, descarga FFmpeg **comprobando su huella SHA-256**, ejecuta las pruebas y genera `dist\DescarGO\DescarGO.exe`. Si tienes [Inno Setup 6](https://jrsoftware.org/isdl.php), también genera el instalador `dist\DescarGO-Setup-1.0.0.exe`.

## 🧑‍💻 Ejecutar desde el código (Windows, Mac o Linux)

```bash
cd descargo
python -m venv .venv
.venv/bin/pip install -r requirements-dev.txt     # en Windows: .venv\Scripts\pip
.venv/bin/python run.py
```

Necesitas FFmpeg instalado (`winget install Gyan.FFmpeg`, `brew install ffmpeg` o `sudo apt install ffmpeg`) o copiar `ffmpeg` y `ffprobe` en `descargo/descargo/bin/`.

Pruebas automáticas:

```bash
.venv/bin/python -m pytest -q tests
```

## 📁 Estructura

```
descargo/
├── run.py                    # lanzador
├── descargo/
│   ├── app.py                # arranque, tema, términos de uso
│   ├── config.py             # ajustes (JSON)
│   ├── core/
│   │   ├── analyzer.py       # lee calidades reales de cada enlace
│   │   ├── formats.py        # traduce tu elección a opciones de yt-dlp
│   │   ├── downloader.py     # cuarentena → análisis → carpeta final
│   │   ├── security.py       # escáner de 5 capas
│   │   ├── policy.py         # bloqueo de páginas de pago y DRM
│   │   └── library.py        # historial SQLite (evita duplicados)
│   ├── ui/                   # ventanas (PySide6 / Qt)
│   └── assets/               # logo e iconos
├── tests/                    # pruebas automáticas
├── packaging/                # PyInstaller, instalador e información de versión
└── build_windows.ps1
```

Los ajustes, el historial y la cuarentena se guardan en `%APPDATA%\DescarGO` (Windows), `~/Library/Application Support/DescarGO` (Mac) o `~/.config/descargo` (Linux).

## ⚖️ Uso responsable

DescarGO está pensado para descargar **contenido propio, con licencia libre o con permiso de su autor**. No descarga contenido de pago ni evade protecciones DRM. Respeta los términos de cada plataforma y los derechos de autor; el usuario es responsable del uso de los archivos descargados.

Las plataformas cambian a menudo. Si una deja de funcionar, actualiza el motor con `pip install -U yt-dlp` y vuelve a compilar.

## 📜 Derechos

**© 2026 lliuya.pe — Todos los derechos reservados.** Queda prohibida la reproducción, distribución o modificación de este software sin autorización del titular.

Componentes de terceros, cada uno con su propia licencia: [yt-dlp](https://github.com/yt-dlp/yt-dlp) (Unlicense), [FFmpeg](https://ffmpeg.org) (LGPL), [Qt / PySide6](https://www.qt.io/qt-for-python) (LGPL).

## ☕ Invítame un café

Si DescarGO te es útil, puedes apoyar su desarrollo por **Yape** al número **925 459 643**. ¡Gracias! 💜
