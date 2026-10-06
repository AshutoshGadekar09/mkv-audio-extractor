@echo off
setlocal enabledelayedexpansion
title FFmpeg Setup for MKV Audio Extractor

echo =======================================================
echo   FFmpeg Setup for Windows 11
echo   MKV Audio Extractor
echo =======================================================
echo.

:: 1. Check if ffmpeg and ffprobe already exist
where ffmpeg >nul 2>&1
set FFMPEG_EXISTS=%errorlevel%

where ffprobe >nul 2>&1
set FFPROBE_EXISTS=%errorlevel%

if %FFMPEG_EXISTS% equ 0 if %FFPROBE_EXISTS% equ 0 (
    echo [OK] FFmpeg and FFprobe are already installed and available in PATH!
    ffmpeg -version | findstr /C:"ffmpeg version"
    echo.
    pause
    exit /b 0
)

echo [!] FFmpeg or FFprobe was not detected in PATH.
echo.
echo Options to install FFmpeg on Windows 11:
echo.
echo [1] Install automatically via Windows Package Manager (winget) - RECOMMENDED
echo [2] Download static FFmpeg zip from gyan.dev and place in bin\
echo [3] Open FFmpeg official download page in browser
echo.

set /p CHOICE="Choose an option [1-3] (default 1): "
if "%CHOICE%"=="" set CHOICE=1

if "%CHOICE%"=="1" (
    echo.
    echo [*] Running: winget install Gyan.FFmpeg
    winget install Gyan.FFmpeg
    if %errorlevel% equ 0 (
        echo.
        echo [OK] FFmpeg installed successfully!
        echo NOTE: Please close and restart any open Terminal or Command Prompt windows
        echo to ensure the new PATH environment variable is reloaded.
    ) else (
        echo.
        echo [!] winget failed. You can install manually from https://www.gyan.dev/ffmpeg/builds/
    )
    pause
    exit /b 0
)

if "%CHOICE%"=="2" (
    echo.
    echo Opening gyan.dev/ffmpeg/builds/ to download "ffmpeg-release-essentials.zip"...
    start https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip
    echo.
    echo After downloading:
    echo  1. Extract ffmpeg.exe and ffprobe.exe
    echo  2. Place both files in the "bin\" folder inside this directory
    echo.
    if not exist "%~dp0bin" mkdir "%~dp0bin"
    pause
    exit /b 0
)

if "%CHOICE%"=="3" (
    start https://ffmpeg.org/download.html#build-windows
    pause
    exit /b 0
)

pause
