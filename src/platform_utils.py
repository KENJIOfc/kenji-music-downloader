"""Operaciones del sistema operativo usadas por la interfaz."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


class OpenDirectoryError(RuntimeError):
    """Error controlado al intentar abrir una carpeta."""


class OpenFileError(RuntimeError):
    """Error controlado al intentar abrir un archivo descargado."""


def open_directory(directory: Path) -> None:
    """Abre una carpeta sin shell y con comandos compatibles por plataforma."""
    resolved_directory = directory.expanduser().resolve()
    if not resolved_directory.is_dir():
        raise OpenDirectoryError("La carpeta de salida no existe.")

    try:
        if sys.platform == "win32":
            os.startfile(str(resolved_directory))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(resolved_directory)], shell=False)
        else:
            subprocess.Popen(["xdg-open", str(resolved_directory)], shell=False)
    except (OSError, subprocess.SubprocessError) as error:
        raise OpenDirectoryError(
            "No se pudo abrir la carpeta de salida con el sistema operativo."
        ) from error


def open_file(file_path: Path) -> None:
    """Abre un archivo con la aplicación predeterminada sin usar un shell."""
    resolved_file = file_path.expanduser().resolve()
    if not resolved_file.is_file():
        raise OpenFileError("El archivo descargado ya no existe.")

    try:
        if sys.platform == "win32":
            os.startfile(str(resolved_file))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(resolved_file)], shell=False)
        else:
            subprocess.Popen(["xdg-open", str(resolved_file)], shell=False)
    except (OSError, subprocess.SubprocessError) as error:
        raise OpenFileError(
            "No se pudo abrir el archivo con el reproductor predeterminado."
        ) from error
