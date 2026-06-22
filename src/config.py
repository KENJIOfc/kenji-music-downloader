"""Configuración y rutas compartidas por la aplicación."""

from pathlib import Path
import sys
from tempfile import NamedTemporaryFile


APP_NAME = "Kenji Music Downloader"
APP_VERSION = "1.0.6"
APP_DESCRIPTION = "Descarga y convierte audio de YouTube de forma sencilla y segura."
SUPPORT_DISCORD_URL = "https://discordapp.com/users/649369933226180658"

# Opciones internas de red. No provienen de la entrada del usuario.
FORCE_IPV4 = True
SOCKET_TIMEOUT_SECONDS = 20


def _get_base_directory() -> Path:
    """Devuelve la carpeta del proyecto o la carpeta del ejecutable empaquetado."""
    if getattr(sys, "frozen", False):
        # PyInstaller define sys.frozen. Guardamos las descargas junto al ejecutable.
        return Path(sys.executable).resolve().parent

    # config.py está en src/, por lo que su carpeta padre es la raíz del proyecto.
    return Path(__file__).resolve().parent.parent


BASE_DIRECTORY = _get_base_directory()
DOWNLOADS_DIRECTORY = BASE_DIRECTORY / "downloads"


class ConfigurationError(RuntimeError):
    """Error entendible relacionado con la configuración local."""


def prepare_output_directory(output_directory: Path | None = None) -> Path:
    """Crea y verifica una carpeta de salida sin dejar archivos de prueba."""
    target_directory = (output_directory or DOWNLOADS_DIRECTORY).expanduser()

    try:
        # resolve() normaliza la ruta sin depender de separadores de Windows o Linux.
        target_directory = target_directory.resolve()
        target_directory.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise ConfigurationError(
            f"No se pudo crear la carpeta de descargas: {target_directory}"
        ) from error

    if not target_directory.is_dir():
        raise ConfigurationError(
            f"La ruta de salida no es una carpeta: {target_directory}"
        )

    try:
        with NamedTemporaryFile(
            prefix=".kenji-write-test-",
            suffix=".tmp",
            dir=target_directory,
        ):
            pass
    except OSError as error:
        raise ConfigurationError(
            f"La carpeta de salida no permite escritura: {target_directory}"
        ) from error

    return target_directory


def prepare_environment(output_directory: Path | None = None) -> Path:
    """Prepara la salida y comprueba herramientas locales o disponibles en PATH."""
    target_directory = prepare_output_directory(output_directory)

    # Importación local para evitar ciclos entre configuración y rutas de usuario.
    from src.tool_manager import missing_ffmpeg_tools

    missing = missing_ffmpeg_tools()
    if missing:
        tool_names = " y ".join(name for name in missing)
        raise ConfigurationError(
            f"No se encontró {tool_names}. Usa "
            "Herramientas > Instalar herramientas necesarias."
        )

    return target_directory
