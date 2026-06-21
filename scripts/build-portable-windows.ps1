<#
  Baut eine portable Windows-Version von FDDB Overview mit PyInstaller.
  Voraussetzung: Python 3.11+ ist installiert.

  Aufruf (PowerShell):
      powershell -ExecutionPolicy Bypass -File .\scripts\build-portable-windows.ps1
  Optional mit Version:
      powershell -ExecutionPolicy Bypass -File .\scripts\build-portable-windows.ps1 -Version "1.0.0"

  Ergebnis:
      dist\FDDB Overview\FDDB Overview.exe
      dist\FDDB-Overview-Windows-Portable.zip
#>
param(
    [string]$Version = "1.0.0"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host "== FDDB Overview Build $Version ==" -ForegroundColor Green

# Virtuelle Umgebung anlegen und Abhaengigkeiten installieren.
if (-not (Test-Path ".venv")) {
    python -m venv .venv
}
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt pyinstaller

# Aufraeumen.
if (Test-Path "build") { Remove-Item "build" -Recurse -Force }
if (Test-Path "dist")  { Remove-Item "dist"  -Recurse -Force }

# Statische Web-Dateien einbetten (Windows-Trenner ';').
$addData = "fddb_overview\web\static;fddb_overview\web\static"

& .\.venv\Scripts\python.exe -m PyInstaller `
    --noconfirm `
    --name "FDDB Overview" `
    --windowed `
    --add-data $addData `
    --collect-submodules uvicorn `
    --hidden-import uvicorn.logging `
    --hidden-import uvicorn.protocols.http.h11_impl `
    --hidden-import uvicorn.protocols.websockets.auto `
    --hidden-import uvicorn.lifespan.on `
    run_fddb_overview.py

# ZIP der portablen Variante erstellen.
$distApp = Join-Path $root "dist\FDDB Overview"
$zipPath = Join-Path $root "dist\FDDB-Overview-Windows-Portable.zip"
if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
Compress-Archive -Path $distApp -DestinationPath $zipPath

Write-Host "Fertig:" -ForegroundColor Green
Write-Host "  $distApp\FDDB Overview.exe"
Write-Host "  $zipPath"
