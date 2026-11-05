# Compila DescarGO para Windows: instala dependencias, descarga y VERIFICA FFmpeg,
# genera DescarGO.exe y (si Inno Setup está instalado) el instalador.
#
# Uso (PowerShell, dentro de la carpeta descargo):
#   powershell -ExecutionPolicy Bypass -File build_windows.ps1

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "==> Creando entorno virtual" -ForegroundColor Cyan
if (-not (Test-Path .venv)) { python -m venv .venv }
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\pip.exe install -r requirements-dev.txt

Write-Host "==> Descargando FFmpeg (compilación oficial LGPL de BtbN)" -ForegroundColor Cyan
$bin = "descargo\bin"
if (-not (Test-Path "$bin\ffmpeg.exe")) {
    $base = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest"
    $zipName = "ffmpeg-master-latest-win64-lgpl.zip"
    $tmp = Join-Path $env:TEMP "descargo-ffmpeg"
    New-Item -ItemType Directory -Force -Path $tmp | Out-Null
    Invoke-WebRequest "$base/$zipName" -OutFile "$tmp\$zipName"
    Invoke-WebRequest "$base/checksums.sha256" -OutFile "$tmp\checksums.sha256"

    # Verificación de integridad: la huella SHA-256 debe coincidir con la publicada.
    $expected = (Select-String -Path "$tmp\checksums.sha256" -Pattern $zipName).Line.Split(" ")[0].ToLower()
    $actual = (Get-FileHash "$tmp\$zipName" -Algorithm SHA256).Hash.ToLower()
    if ($expected -ne $actual) { throw "La huella SHA-256 de FFmpeg NO coincide. Descarga abortada." }
    Write-Host "    SHA-256 verificado: $actual" -ForegroundColor Green

    Expand-Archive "$tmp\$zipName" -DestinationPath $tmp -Force
    $dir = Get-ChildItem $tmp -Directory | Where-Object { $_.Name -like "ffmpeg-*" } | Select-Object -First 1
    Copy-Item "$($dir.FullName)\bin\ffmpeg.exe" $bin
    Copy-Item "$($dir.FullName)\bin\ffprobe.exe" $bin
}

Write-Host "==> Ejecutando pruebas" -ForegroundColor Cyan
& .\.venv\Scripts\python.exe -m pytest -q tests

$version = (Select-String -Path "descargo\__init__.py" -Pattern 'APP_VERSION = "([^"]+)"').Matches[0].Groups[1].Value
Write-Host "==> Compilando DescarGO.exe v$version" -ForegroundColor Cyan
& .\.venv\Scripts\pyinstaller.exe packaging\descargo.spec --noconfirm --distpath dist --workpath build

$iscc = @("${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe", "$env:ProgramFiles\Inno Setup 6\ISCC.exe") |
    Where-Object { Test-Path $_ } | Select-Object -First 1
if ($iscc) {
    Write-Host "==> Creando instalador" -ForegroundColor Cyan
    & $iscc "/DAppVersion=$version" packaging\installer.iss
    $setup = "dist\DescarGO-Setup-$version.exe"
    # Huella SHA-256 publicada junto al instalador (la app la verifica al actualizarse)
    $hash = (Get-FileHash $setup -Algorithm SHA256).Hash.ToLower()
    Set-Content -Path "$setup.sha256" -Value "$hash  DescarGO-Setup-$version.exe" -Encoding ascii -NoNewline
    Write-Host "Listo: $setup  (SHA-256 $hash)" -ForegroundColor Green
} else {
    Write-Host "Listo: dist\DescarGO\DescarGO.exe  (instala Inno Setup 6 para generar el instalador)" -ForegroundColor Green
}
