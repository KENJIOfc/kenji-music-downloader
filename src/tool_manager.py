"""Localización e instalación local de herramientas externas seguras."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
import shutil
import ssl
import sys
from tempfile import TemporaryDirectory
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from zipfile import BadZipFile, ZipFile, ZipInfo

from src.error_log import log_error, log_info
from src.user_settings import get_settings_path


# Gyan.dev mantiene compilaciones de Windows enlazadas desde ffmpeg.org.
# Esta URL estable redirige automáticamente a la versión essentials vigente.
FFMPEG_WINDOWS_X64_URL = (
    "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
)
FFMPEG_DOWNLOAD_TIMEOUT_SECONDS = 30
FFMPEG_MAX_ARCHIVE_BYTES = 250 * 1024 * 1024
FFMPEG_MAX_BINARY_BYTES = 200 * 1024 * 1024
DOWNLOAD_CHUNK_BYTES = 1024 * 1024
REQUIRED_FFMPEG_TOOLS = ("ffmpeg", "ffprobe")
LOCAL_SOURCE = "carpeta local de la aplicación"
BUNDLED_SOURCE = "junto al ejecutable"
PATH_SOURCE = "PATH del sistema"


StatusCallback = Callable[[str], None]


@dataclass(frozen=True, slots=True)
class ResolvedTool:
    """Ruta confiable y origen de una herramienta encontrada."""

    name: str
    path: Path
    source: str


class ToolInstallationError(RuntimeError):
    """Error controlado durante la descarga o extracción de herramientas."""


def get_tools_directory() -> Path:
    """Devuelve la carpeta privada de herramientas del perfil del usuario."""
    return get_settings_path().parent / "tools"


def ensure_tools_directory() -> Path:
    """Crea la carpeta local sin solicitar permisos de administrador."""
    tools_directory = get_tools_directory()
    try:
        tools_directory.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise ToolInstallationError(
            f"No se pudo crear la carpeta de herramientas: {tools_directory}"
        ) from error
    return tools_directory


def _executable_filename(tool_name: str) -> str:
    if tool_name not in {*REQUIRED_FFMPEG_TOOLS, "yt-dlp"}:
        raise ValueError(f"Herramienta no permitida: {tool_name}")
    return f"{tool_name}.exe" if sys.platform == "win32" else tool_name


def _application_directory() -> Path:
    """Obtiene una ruta portable tanto en desarrollo como con PyInstaller."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def resolve_tool(tool_name: str) -> ResolvedTool | None:
    """Busca una herramienta local, empaquetada y finalmente en PATH."""
    filename = _executable_filename(tool_name)
    local_candidate = get_tools_directory() / filename
    if local_candidate.is_file():
        return ResolvedTool(tool_name, local_candidate.resolve(), LOCAL_SOURCE)

    application_directory = _application_directory()
    bundled_candidates = (
        application_directory / "tools" / filename,
        application_directory / filename,
    )
    for candidate in bundled_candidates:
        if candidate.is_file():
            return ResolvedTool(tool_name, candidate.resolve(), BUNDLED_SOURCE)

    path_match = shutil.which(tool_name)
    if path_match:
        return ResolvedTool(tool_name, Path(path_match).resolve(), PATH_SOURCE)
    return None


def missing_ffmpeg_tools() -> tuple[str, ...]:
    """Enumera únicamente herramientas necesarias que aún no están disponibles."""
    return tuple(
        tool_name
        for tool_name in REQUIRED_FFMPEG_TOOLS
        if resolve_tool(tool_name) is None
    )


def _notify(callback: StatusCallback | None, message: str) -> None:
    if callback:
        callback(message)


def _download_archive(
    destination: Path,
    download_url: str,
    status_callback: StatusCallback | None,
    opener,
) -> None:
    """Descarga por HTTPS con límites para evitar archivos inesperadamente grandes."""
    request = Request(
        download_url,
        headers={"User-Agent": "Kenji-Music-Downloader/1.0"},
    )
    _notify(status_callback, "Descargando FFmpeg…")
    with opener(request, timeout=FFMPEG_DOWNLOAD_TIMEOUT_SECONDS) as response:
        raw_length = response.headers.get("Content-Length")
        total_length = int(raw_length) if raw_length and raw_length.isdigit() else None
        if total_length and total_length > FFMPEG_MAX_ARCHIVE_BYTES:
            raise ToolInstallationError(
                "El archivo de FFmpeg supera el tamaño máximo permitido."
            )

        downloaded = 0
        last_percentage = -1
        with destination.open("xb") as archive_file:
            while True:
                chunk = response.read(DOWNLOAD_CHUNK_BYTES)
                if not chunk:
                    break
                downloaded += len(chunk)
                if downloaded > FFMPEG_MAX_ARCHIVE_BYTES:
                    raise ToolInstallationError(
                        "La descarga de FFmpeg superó el tamaño máximo permitido."
                    )
                archive_file.write(chunk)

                if total_length:
                    percentage = min(100, int(downloaded * 100 / total_length))
                    if percentage != last_percentage:
                        _notify(
                            status_callback,
                            f"Descargando FFmpeg… {percentage}%",
                        )
                        last_percentage = percentage

    if downloaded == 0:
        raise ToolInstallationError("La descarga de FFmpeg llegó vacía.")


def _find_binary_entries(archive: ZipFile) -> dict[str, ZipInfo]:
    """Selecciona por nombre los binarios, sin confiar en rutas del ZIP."""
    selected: dict[str, ZipInfo] = {}
    expected_names = {f"{name}.exe" for name in REQUIRED_FFMPEG_TOOLS}
    for entry in archive.infolist():
        filename = PurePosixPath(entry.filename.replace("\\", "/")).name.lower()
        if entry.is_dir() or filename not in expected_names:
            continue
        if entry.file_size <= 0 or entry.file_size > FFMPEG_MAX_BINARY_BYTES:
            raise ToolInstallationError(
                f"El binario {filename} tiene un tamaño inválido."
            )
        selected[filename.removesuffix(".exe")] = entry
    return selected


def _extract_required_binaries(archive_path: Path, staging_directory: Path) -> None:
    """Extrae solo FFmpeg y FFprobe a destinos fijos para impedir path traversal."""
    _ = staging_directory.mkdir(parents=True, exist_ok=True)
    with ZipFile(archive_path) as archive:
        entries = _find_binary_entries(archive)
        missing = [name for name in REQUIRED_FFMPEG_TOOLS if name not in entries]
        if missing:
            raise ToolInstallationError(
                "El ZIP no contiene las herramientas esperadas: " + ", ".join(missing)
            )

        for tool_name in REQUIRED_FFMPEG_TOOLS:
            destination = staging_directory / f"{tool_name}.exe"
            copied = 0
            with archive.open(entries[tool_name]) as source, destination.open("xb") as target:
                while True:
                    chunk = source.read(DOWNLOAD_CHUNK_BYTES)
                    if not chunk:
                        break
                    copied += len(chunk)
                    if copied > FFMPEG_MAX_BINARY_BYTES:
                        raise ToolInstallationError(
                            f"El binario {tool_name}.exe supera el límite permitido."
                        )
                    target.write(chunk)

            # Los ejecutables PE de Windows comienzan con la firma MZ.
            with destination.open("rb") as binary_file:
                if binary_file.read(2) != b"MZ":
                    raise ToolInstallationError(
                        f"El archivo {tool_name}.exe extraído no es un ejecutable válido."
                    )


def install_ffmpeg_tools(
    status_callback: StatusCallback | None = None,
    download_url: str = FFMPEG_WINDOWS_X64_URL,
    opener=None,
) -> dict[str, Path]:
    """Instala FFmpeg/FFprobe en APPDATA sin modificar PATH ni usar shell."""
    if sys.platform != "win32":
        raise ToolInstallationError(
            "La instalación automática está disponible actualmente para Windows x64."
        )
    if sys.maxsize <= 2**32:
        raise ToolInstallationError(
            "La instalación automática requiere una versión de Windows de 64 bits."
        )

    parsed_url = urlparse(download_url)
    if parsed_url.scheme != "https" or parsed_url.hostname != "www.gyan.dev":
        raise ToolInstallationError(
            "La URL configurada para FFmpeg no pertenece a la fuente HTTPS permitida."
        )

    tools_directory = ensure_tools_directory()
    open_request = opener or urlopen
    log_info("Instalación de herramientas", "Inicio de descarga de FFmpeg.")
    log_info("Instalación de herramientas", f"URL usada: {download_url}")

    try:
        with TemporaryDirectory(
            prefix=".ffmpeg-install-",
            dir=tools_directory.parent,
        ) as temporary_directory:
            temporary_path = Path(temporary_directory)
            archive_path = temporary_path / "ffmpeg.zip"
            staging_directory = temporary_path / "extracted"

            _download_archive(
                archive_path,
                download_url,
                status_callback,
                open_request,
            )
            log_info("Instalación de herramientas", "Descarga de FFmpeg completada.")
            _notify(status_callback, "Extrayendo herramientas…")
            _extract_required_binaries(archive_path, staging_directory)

            installed: dict[str, Path] = {}
            for tool_name in REQUIRED_FFMPEG_TOOLS:
                source = staging_directory / f"{tool_name}.exe"
                destination = tools_directory / source.name
                source.replace(destination)
                installed[tool_name] = destination.resolve()
                log_info(
                    "Instalación de herramientas",
                    f"{source.name} instalado en: {destination}",
                )

        _notify(status_callback, "Instalación completada.")
        log_info("Instalación de herramientas", "Extracción completada correctamente.")
        return installed
    except ToolInstallationError as error:
        log_error("Instalación de herramientas", str(error), error)
        raise
    except HTTPError as error:
        message = f"No se pudo descargar FFmpeg: el servidor respondió HTTP {error.code}."
        log_error("Instalación de herramientas", message, error)
        raise ToolInstallationError(message) from error
    except (URLError, TimeoutError, ssl.SSLError) as error:
        message = "No se pudo descargar FFmpeg. Revisa tu conexión a Internet."
        log_error("Instalación de herramientas", message, error)
        raise ToolInstallationError(message) from error
    except BadZipFile as error:
        message = "El archivo descargado no es un ZIP válido de FFmpeg."
        log_error("Instalación de herramientas", message, error)
        raise ToolInstallationError(message) from error
    except PermissionError as error:
        message = "No hay permisos para guardar FFmpeg en la carpeta local de la aplicación."
        log_error("Instalación de herramientas", message, error)
        raise ToolInstallationError(message) from error
    except OSError as error:
        message = "No se pudo guardar o extraer FFmpeg en la carpeta local."
        log_error("Instalación de herramientas", message, error)
        raise ToolInstallationError(message) from error
