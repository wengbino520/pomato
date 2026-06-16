# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for POMATO 番茄日志助手."""

import sys
from pathlib import Path

block_cipher = None

# Project root
PROJECT_ROOT = Path(SPECPATH)  # SPECPATH is set by PyInstaller to spec file dir

# Collect all src modules
src_dir = PROJECT_ROOT / "src"
src_files = []
if src_dir.is_dir():
    src_files = [(str(f), str(f.relative_to(PROJECT_ROOT.parent)))
                 for f in src_dir.rglob("*.py")]

a = Analysis(
    [str(PROJECT_ROOT / "main.py")],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=src_files,
    hiddenimports=[
        "PyQt6",
        "PyQt6.QtCore",
        "PyQt6.QtGui",
        "PyQt6.QtWidgets",
        "pyqtgraph",
        "numpy",
        "openai",
        "sqlite3",
        "json",
        "logging",
        "ctypes",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "matplotlib",
        "pandas",
        "scipy",
        "PIL",
        "cv2",
    ],
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
    name="POMATO",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # Windows: no console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(PROJECT_ROOT / "assets" / "pomato.ico") if (PROJECT_ROOT / "assets" / "pomato.ico").exists() else None,
)
