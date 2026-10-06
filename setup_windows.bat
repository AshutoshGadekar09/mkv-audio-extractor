@echo off
setlocal enabledelayedexpansion
title MKV Audio Extractor - Windows 11 Setup

echo =======================================================
echo   MKV Audio Extractor - Windows 11 Setup
echo   Ashutosh Gadekar (c) 2026
echo =======================================================
echo.

:: 1. Check Python
where python >nul 2>&1
if %errorlevel% neq 0 (
    where py >nul 2>&1
    if %errorlevel% neq 0 (
        echo [ERROR] Python 3.10+ was not found on your system.
        echo.
        echo Would you like to install Python 3.12 automatically via winget?
        set /p INSTALL_PY="Install Python via winget now? (Y/N): "
        if /i "!INSTALL_PY!"=="Y" (
            winget install Python.Python.3.12
            echo.
            echo [!] Please restart this script after the installer completes.
            pause
            exit /b 0
        )
        pause
        exit /b 1
    ) else (
        set PYTHON_CMD=py -3
    )
) else (
    set PYTHON_CMD=python
)

echo [OK] Python detected: %PYTHON_CMD%
%PYTHON_CMD% --version

:: 2. Check/create virtualenv
echo.
echo [*] Setting up Python virtual environment (.venv)...
if not exist ".venv" (
    %PYTHON_CMD% -m venv .venv
)

call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt

:: 3. Check FFmpeg
echo.
echo [*] Checking FFmpeg and FFprobe...
where ffmpeg >nul 2>&1
if %errorlevel% neq 0 (
    if not exist "bin\ffmpeg.exe" (
        echo [!] Warning: ffmpeg is not yet in PATH or bin\
        echo Run install_ffmpeg.bat to install it easily.
    ) else (
        echo [OK] Bundled ffmpeg found in bin\
    )
) else (
    echo [OK] System ffmpeg found!
)

:: 4. Optional Desktop Shortcut creation via PowerShell
echo.
echo [*] Creating Desktop Shortcut...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$ws = New-Object -ComObject WScript.Shell; " ^
    "$desktop = [Environment]::GetFolderPath('Desktop'); " ^
    "$shortcut = $ws.CreateShortcut((Join-Path $desktop 'MKV Audio Extractor.lnk')); " ^
    "$shortcut.TargetPath = (Join-Path '%~dp0' 'mkv-audio-extractor.exe'); " ^
    "$shortcut.WorkingDirectory = '%~dp0'; " ^
    "$shortcut.IconLocation = (Join-Path '%~dp0' 'mkv-audio-extractor.ico'); " ^
    "$shortcut.Description = 'Extract audio tracks from MKV files with language selection'; " ^
    "$shortcut.Save()"

if %errorlevel% equ 0 (
    echo [OK] Desktop shortcut "MKV Audio Extractor" created successfully!
)

echo.
echo =======================================================
echo [SUCCESS] Setup complete!
echo Double-click mkv-audio-extractor.exe or run_gui.bat to launch!
echo =======================================================
echo.
pause
