"""Diagnóstico no destructivo de dependencias y conectividad."""

from __future__ import annotations

from dataclasses import dataclass
import importlib.util
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

from src.config import ConfigurationError, prepare_output_directory
from src.tool_manager import resolve_tool


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
    ffmpeg = resolve_tool("ffmpeg")
    ffprobe = resolve_tool("ffprobe")

    try:
        resolved_output = prepare_output_directory(output_directory)
    except ConfigurationError as error:
        resolved_output = output_directory.expanduser().resolve()
        output_valid = False
        output_detail = str(error)
    else:
        output_valid = True
        output_detail = str(resolved_output)
    connection_available = check_internet_connection()

    return [
        ToolCheckResult(
            "yt-dlp",
            yt_dlp_found,
            "módulo de Python disponible" if yt_dlp_found else "instala requirements.txt",
        ),
        ToolCheckResult(
            "ffmpeg",
            ffmpeg is not None,
            f"{ffmpeg.source}: {ffmpeg.path}"
            if ffmpeg
            else "puede instalarse desde el menú Herramientas",
        ),
        ToolCheckResult(
            "ffprobe",
            ffprobe is not None,
            f"{ffprobe.source}: {ffprobe.path}"
            if ffprobe
            else "puede instalarse junto con FFmpeg",
        ),
        ToolCheckResult(
            "Carpeta de salida",
            output_valid,
            output_detail,
        ),
        ToolCheckResult(
            "Conexión",
            connection_available,
            "respuesta HTTPS recibida"
            if connection_available
            else "sin respuesta de YouTube",
        ),
    ]
