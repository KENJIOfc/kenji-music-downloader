# -*- mode: python ; coding: utf-8 -*-
"""Configuración portable de PyInstaller para la interfaz gráfica."""

from PyInstaller.utils.hooks import collect_all
from pathlib import Path
import sys


yt_dlp_datas, yt_dlp_binaries, yt_dlp_hidden_imports = collect_all("yt_dlp")
ejs_datas, ejs_binaries, ejs_hidden_imports = collect_all("yt_dlp_ejs")

deno_name = "deno.exe" if sys.platform == "win32" else "deno"
deno_path = Path(sys.executable).resolve().parent / deno_name
deno_binaries = [(str(deno_path), ".")] if deno_path.is_file() else []

analysis = Analysis(
    ["src/gui.py"],
    pathex=["."],
    binaries=yt_dlp_binaries + ejs_binaries + deno_binaries,
    datas=yt_dlp_datas + ejs_datas,
    hiddenimports=yt_dlp_hidden_imports + ejs_hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

python_archive = PYZ(analysis.pure)

executable = EXE(
    python_archive,
    analysis.scripts,
    analysis.binaries,
    analysis.datas,
    [],
    name="KenjiMusicDownloader",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
)
