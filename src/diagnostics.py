"""Diagnóstico no destructivo de dependencias y conectividad."""

from __future__ import annotations

from dataclasses import dataclass
import importlib.util
import os
from pathlib import Path
import shutil
from urllib.error import URLError
from urllib.request import Request, urlopen


@dataclass(frozen=True, slots=True)
class ToolCheckResult:
    """Resultado individual listo para presentar en la interfaz."""

    label: str
    available: bool
    detail: str

    def display_line(self) -> str:
        if self.label == "Conexión":
            state = "disponible" if self.available else "no disponible"
        elif self.label == "Carpeta de salida":
            state = "válida" if self.available else "no válida"
        else:
            state = "encontrado" if self.available else "no encontrado"
        return f"{self.label}: {state} — {self.detail}"


def check_internet_connection(timeout: float = 5.0) -> bool:
    """Comprueba una conexión HTTPS básica relevante para la aplicación."""
    request = Request(
        "https://www.youtube.com/generate_204",
        headers={"User-Agent": "Kenji-Music-Downloader/1.0"},
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            return int(getattr(response, "status", 200)) < 500
    except (OSError, URLError, ValueError):
        return False


def verify_tools(output_directory: Path) -> list[ToolCheckResult]:
    """Revisa dependencias sin ejecutar comandos aportados por el usuario."""
    yt_dlp_found = importlib.util.find_spec("yt_dlp") is not None
    ffmpeg_path = shutil.which("ffmpeg")
    ffprobe_path = shutil.which("ffprobe")

    resolved_output = output_directory.expanduser().resolve()
    output_valid = resolved_output.is_dir() and os.access(resolved_output, os.W_OK)
    connection_available = check_internet_connection()

    return [
        ToolCheckResult(
            "yt-dlp",
            yt_dlp_found,
            "módulo de Python disponible" if yt_dlp_found else "instala requirements.txt",
        ),
        ToolCheckResult(
            "ffmpeg",
            ffmpeg_path is not None,
            ffmpeg_path or "instala FFmpeg y agrégalo al PATH",
        ),
        ToolCheckResult(
            "ffprobe",
            ffprobe_path is not None,
            ffprobe_path or "normalmente se instala junto con FFmpeg",
        ),
        ToolCheckResult(
            "Carpeta de salida",
            output_valid,
            str(resolved_output) if output_valid else "no existe o no permite escritura",
        ),
        ToolCheckResult(
            "Conexión",
            connection_available,
            "respuesta HTTPS recibida"
            if connection_available
            else "sin respuesta de YouTube",
        ),
    ]
