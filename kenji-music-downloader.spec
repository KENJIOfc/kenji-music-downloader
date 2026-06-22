# -*- mode: python ; coding: utf-8 -*-
"""Configuración portable de PyInstaller para la interfaz gráfica."""

from PyInstaller.utils.hooks import collect_all
from pathlib import Path
import shutil
import sys


yt_dlp_datas, yt_dlp_binaries, yt_dlp_hidden_imports = collect_all("yt_dlp")
ejs_datas, ejs_binaries, ejs_hidden_imports = collect_all("yt_dlp_ejs")

deno_name = "deno.exe" if sys.platform == "win32" else "deno"
deno_candidates = (
    Path(sys.executable).resolve().parent / deno_name,
    Path(".venv") / ("Scripts" if sys.platform == "win32" else "bin") / deno_name,
    Path(shutil.which("deno") or ""),
)
deno_path = next((path.resolve() for path in deno_candidates if path.is_file()), None)
deno_binaries = [(str(deno_path), ".")] if deno_path else []

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

# Helper pequeño e independiente: puede seguir ejecutándose después de que la
# ventana principal cierre y así reemplazar archivos bloqueados en Windows.
installer_analysis = Analysis(
    ["src/update_installer.py"],
    pathex=["."],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

installer_archive = PYZ(installer_analysis.pure)

installer_executable = EXE(
    installer_archive,
    installer_analysis.scripts,
    installer_analysis.binaries,
    installer_analysis.datas,
    [],
    name="KenjiUpdateInstaller",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
)
