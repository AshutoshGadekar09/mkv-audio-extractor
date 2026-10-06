# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller specification file for MKV Audio Extractor on Windows 11."""

from pathlib import Path

block_cipher = None

added_files = [
    ('mkv-audio-extractor.ico', '.'),
    ('mkv-audio-extractor.png', '.'),
    ('mkv-audio-extractor.svg', '.'),
]

a = Analysis(
    ['mkv_audio_extractor/__main__.py'],
    pathex=['.'],
    binaries=[],
    datas=added_files,
    hiddenimports=[
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'mkv_audio_extractor',
        'mkv_audio_extractor.core',
        'mkv_audio_extractor.core.probe',
        'mkv_audio_extractor.core.extractor',
        'mkv_audio_extractor.core.languages',
        'mkv_audio_extractor.core.batch',
        'mkv_audio_extractor.gui',
        'mkv_audio_extractor.gui.main_window',
        'mkv_audio_extractor.cli',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'numpy', 'scipy', 'pandas', 'unittest'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='mkv-audio-extractor',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Windowed GUI app; __main__.py attaches to console dynamically if CLI flags are given
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='mkv-audio-extractor.ico',
    version='version_info.txt',
)
