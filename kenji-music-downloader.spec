# -*- mode: python ; coding: utf-8 -*-
"""Configuración portable de PyInstaller para la interfaz gráfica."""

from PyInstaller.utils.hooks import collect_all
from pathlib import Path
import shutil
import sys

from src.config import APP_VERSION


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
assets_directory = Path("assets")
assets_datas = (
    [(str(assets_directory.resolve()), "assets")]
    if assets_directory.is_dir()
    else []
)
main_icon_path = Path("assets") / "logo_main.ico"
installer_icon_path = Path("assets") / "updater_logo.ico"
app_icon = (
    str(main_icon_path.resolve())
    if sys.platform == "win32" and main_icon_path.is_file()
    else None
)
installer_icon = (
    str(installer_icon_path.resolve())
    if sys.platform == "win32" and installer_icon_path.is_file()
    else None
)


def _windows_version_tuple(version):
    parts = [int(part) for part in version.split(".")]
    return tuple((parts + [0, 0, 0, 0])[:4])


def _write_windows_version_file(path, file_description, internal_name):
    """Crea metadata visible para Windows sin duplicar APP_VERSION a mano."""
    file_version = _windows_version_tuple(APP_VERSION)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={file_version},
    prodvers={file_version},
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        '040904B0',
        [
          StringStruct('CompanyName', 'KENJIOFC'),
          StringStruct('FileDescription', '{file_description}'),
          StringStruct('FileVersion', '{APP_VERSION}'),
          StringStruct('InternalName', '{internal_name}'),
          StringStruct('OriginalFilename', '{internal_name}.exe'),
          StringStruct('ProductName', 'Kenji Music Downloader'),
          StringStruct('ProductVersion', '{APP_VERSION}')
        ]
      )
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
""",
        encoding="utf-8",
    )
    return str(path.resolve())


version_directory = Path("build") / "version_info"
app_version_file = (
    _write_windows_version_file(
        version_directory / "KenjiMusicDownloader_version_info.txt",
        "Kenji Music Downloader",
        "KenjiMusicDownloader",
    )
    if sys.platform == "win32"
    else None
)
installer_version_file = (
    _write_windows_version_file(
        version_directory / "KenjiUpdateInstaller_version_info.txt",
        "Kenji Music Downloader Update Installer",
        "KenjiUpdateInstaller",
    )
    if sys.platform == "win32"
    else None
)
excluded_modules = [
    # Mantenemos fuera del build solo elementos claramente innecesarios para
    # producción. No se excluyen pip, wheel, setuptools ni pkg_resources porque
    # PyInstaller o sus hooks pueden necesitarlos durante el análisis.
    "pytest",
    "tests",
    "tkinter.test",
    "idlelib",
]

analysis = Analysis(
    ["src/gui.py"],
    pathex=["."],
    binaries=yt_dlp_binaries + ejs_binaries + deno_binaries,
    datas=yt_dlp_datas + ejs_datas + assets_datas,
    hiddenimports=yt_dlp_hidden_imports + ejs_hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excluded_modules,
    noarchive=False,
    optimize=0,
)

python_archive = PYZ(analysis.pure)

executable = EXE(
    python_archive,
    analysis.scripts,
    [],
    name="KenjiMusicDownloader",
    icon=app_icon,
    version=app_version_file,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    exclude_binaries=True,
    disable_windowed_traceback=False,
    uac_admin=False,
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
    excludes=excluded_modules,
    noarchive=False,
    optimize=0,
)

installer_archive = PYZ(installer_analysis.pure)

installer_executable = EXE(
    installer_archive,
    installer_analysis.scripts,
    [],
    name="KenjiUpdateInstaller",
    icon=installer_icon,
    version=installer_version_file,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    exclude_binaries=True,
    disable_windowed_traceback=False,
    uac_admin=False,
)

application = COLLECT(
    executable,
    installer_executable,
    analysis.binaries,
    analysis.zipfiles,
    analysis.datas,
    installer_analysis.binaries,
    installer_analysis.zipfiles,
    installer_analysis.datas,
    strip=False,
    upx=False,
    name="KenjiMusicDownloader",
)
