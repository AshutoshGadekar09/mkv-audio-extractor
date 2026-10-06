@echo off
setlocal
title Launching MKV Audio Extractor

:: If standalone exe exists, run that
if exist "%~dp0mkv-audio-extractor.exe" (
    start "" "%~dp0mkv-audio-extractor.exe"
    exit /b 0
)

:: Otherwise check venv pythonw
if exist "%~dp0.venv\Scripts\pythonw.exe" (
    start "" "%~dp0.venv\Scripts\pythonw.exe" -m mkv_audio_extractor
    exit /b 0
)

:: Otherwise check system pythonw
where pythonw >nul 2>&1
if %errorlevel% equ 0 (
    start "" pythonw -m mkv_audio_extractor
    exit /b 0
)

:: Fallback to python
where python >nul 2>&1
if %errorlevel% equ 0 (
    start "" python -m mkv_audio_extractor
    exit /b 0
)

echo [ERROR] Neither mkv-audio-extractor.exe nor Python was found.
echo Run setup_windows.bat to configure the environment.
pause
exit /b 1
