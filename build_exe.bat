@echo off
setlocal enabledelayedexpansion
title Building MKV Audio Extractor for Windows 11

echo =======================================================
echo   MKV Audio Extractor - Windows 11 Build Script
echo   Ashutosh Gadekar (c) 2026
echo =======================================================
echo.

:: 1. Check for Python
where python >nul 2>&1
if %errorlevel% neq 0 (
    where py >nul 2>&1
    if %errorlevel% neq 0 (
        echo [ERROR] Python was not found in your system PATH.
        echo Please install Python 3.10+ from https://www.python.org/
        echo Or run: winget install Python.Python.3.12
        pause
        exit /b 1
    ) else (
        set PYTHON_CMD=py -3
    )
) else (
    set PYTHON_CMD=python
)

echo [OK] Using Python: %PYTHON_CMD%
%PYTHON_CMD% --version

:: 2. Setup Virtual Environment
if not exist ".venv" (
    echo.
    echo [*] Creating virtual environment (.venv)...
    %PYTHON_CMD% -m venv .venv
)

call .venv\Scripts\activate.bat
if %errorlevel% neq 0 (
    echo [ERROR] Failed to activate virtual environment.
    pause
    exit /b 1
)

:: 3. Upgrade pip and install requirements
echo.
echo [*] Installing dependencies and PyInstaller...
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller

:: 4. Build Standalone Executable
echo.
echo [*] Building standalone Windows executable with PyInstaller...
if exist "dist" rmdir /s /q "dist"
if exist "build" rmdir /s /q "build"

pyinstaller --clean mkv-audio-extractor.spec

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] PyInstaller build failed. Check error messages above.
    pause
    exit /b 1
)

echo.
echo =======================================================
echo [SUCCESS] Windows Executable built successfully!
echo Binary location: dist\mkv-audio-extractor.exe
echo =======================================================
echo.

if exist "dist\mkv-audio-extractor.exe" (
    echo Output file verified:
    dir dist\mkv-audio-extractor.exe
)

echo.
pause
