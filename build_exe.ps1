# PowerShell 5.1 / 7+ Build Script for MKV Audio Extractor on Windows 11
[CmdletBinding()]
param(
    [switch]$BundleFfmpeg = $false,
    [switch]$CreateZip = $true
)

$ErrorActionPreference = "Stop"

Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host "  MKV Audio Extractor - Windows 11 Build Script        " -ForegroundColor Cyan
Write-Host "  Ashutosh Gadekar (c) 2026                            " -ForegroundColor Cyan
Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host ""

# 1. Check Python
$PythonExe = $null
if (Get-Command python -ErrorAction SilentlyContinue) {
    $PythonExe = "python"
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $PythonExe = "py -3"
} else {
    Write-Error "Python 3.10+ not found in PATH. Install with: winget install Python.Python.3.12"
    exit 1
}

Write-Host "[OK] Detected Python: $PythonExe" -ForegroundColor Green

# 2. Virtual environment
if (-not (Test-Path ".venv")) {
    Write-Host "[*] Creating virtual environment (.venv)..." -ForegroundColor Yellow
    & $PythonExe -m venv .venv
}

$VenvPython = Join-Path (Get-Location) ".venv\Scripts\python.exe"

# 3. Dependencies
Write-Host "[*] Installing Python packages..." -ForegroundColor Yellow
& $VenvPython -m pip install --upgrade pip
& $VenvPython -m pip install -r requirements.txt
& $VenvPython -m pip install pyinstaller

# 4. Clean previous builds
if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }
if (Test-Path "build") { Remove-Item -Recurse -Force "build" }

# 5. Run PyInstaller
Write-Host "[*] Building Windows standalone executable..." -ForegroundColor Yellow
$PyInstaller = Join-Path (Get-Location) ".venv\Scripts\pyinstaller.exe"
& $PyInstaller --clean mkv-audio-extractor.spec

$ExePath = "dist\mkv-audio-extractor.exe"
if (-not (Test-Path $ExePath)) {
    Write-Error "Build failed: $ExePath does not exist."
    exit 1
}

$ExeSize = (Get-Item $ExePath).Length / 1MB
Write-Host ""
Write-Host "[SUCCESS] Windows 11 Executable built successfully!" -ForegroundColor Green
Write-Host "Location: $ExePath ($([math]::Round($ExeSize, 2)) MB)" -ForegroundColor Green

# 6. Optional: Create distribution ZIP archive
if ($CreateZip) {
    $ZipPath = "dist\mkv-audio-extractor-windows-x64.zip"
    Write-Host "[*] Creating release ZIP: $ZipPath..." -ForegroundColor Yellow
    Compress-Archive -Path $ExePath, "README.md", "LICENSE" -DestinationPath $ZipPath -Force
    Write-Host "[OK] Archive created: $ZipPath" -ForegroundColor Green
}

Write-Host ""
Write-Host "Build complete!" -ForegroundColor Cyan
