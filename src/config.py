"""Configuración y rutas compartidas por la aplicación."""

from pathlib import Path
import sys
from tempfile import NamedTemporaryFile


APP_NAME = "Yūgen Audio"
APP_FULL_NAME = "Yūgen Audio Music Downloader"
APP_TECHNICAL_NAME = "YugenAudio"
APP_VERSION = "1.0.8"
APP_DESCRIPTION = "Music Downloader para descargar y convertir audio de YouTube de forma sencilla y segura."
APP_TAGLINE = "幽玄の音、静かに響く。"
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


def _get_resource_directory() -> Path:
    """Devuelve la carpeta donde PyInstaller expone recursos incluidos."""
    bundled_directory = getattr(sys, "_MEIPASS", None)
    if bundled_directory:
        return Path(bundled_directory)
    return BASE_DIRECTORY


RESOURCE_DIRECTORY = _get_resource_directory()
ASSETS_DIRECTORY = RESOURCE_DIRECTORY / "assets"
YUGEN_ASSETS_DIRECTORY = ASSETS_DIRECTORY / "yugen"
LOGO_IMAGE_PATH = ASSETS_DIRECTORY / "logo_main.png"
LOGO_HEADER_IMAGE_PATH = ASSETS_DIRECTORY / "logo_main_header.png"
TASKBAR_ICON_IMAGE_PATH = ASSETS_DIRECTORY / "logo_main.png"
TASKBAR_ICON_PREVIEW_PATH = ASSETS_DIRECTORY / "logo_main_icon.png"
TASKBAR_ICON_PATH = ASSETS_DIRECTORY / "logo_main.ico"
UPDATE_INSTALLER_ICON_IMAGE_PATH = ASSETS_DIRECTORY / "updater_logo.png"
UPDATE_INSTALLER_ICON_PREVIEW_PATH = ASSETS_DIRECTORY / "updater_logo_icon.png"
UPDATE_INSTALLER_ICON_PATH = ASSETS_DIRECTORY / "updater_logo.ico"
TYPOGRAPHY_REFERENCE_IMAGE_PATH = ASSETS_DIRECTORY / "typography_reference.png"
INTERFACE_REFERENCE_IMAGE_PATH = ASSETS_DIRECTORY / "interface_reference_new.png"
YUGEN_HERO_BANNER_PATH = YUGEN_ASSETS_DIRECTORY / "hero_banner.png"
YUGEN_EMBLEM_PATH = YUGEN_ASSETS_DIRECTORY / "yugen_emblem.png"
YUGEN_PLAQUE_PATH = YUGEN_ASSETS_DIRECTORY / "japanese_plaque.png"
YUGEN_HEADER_EQUALIZER_PATH = YUGEN_ASSETS_DIRECTORY / "header_equalizer.png"
YUGEN_DOWNLOAD_BUTTON_PATH = YUGEN_ASSETS_DIRECTORY / "download_button.png"
YUGEN_PROGRESS_BRUSH_PATH = YUGEN_ASSETS_DIRECTORY / "progress_brush.png"
YUGEN_CONCERT_PLACEHOLDER_PATH = YUGEN_ASSETS_DIRECTORY / "concert_placeholder.png"
YUGEN_DETAILS_DECORATION_PATH = YUGEN_ASSETS_DIRECTORY / "details_decoration_simple.png"
YUGEN_SIDEBAR_WAVES_PATH = YUGEN_ASSETS_DIRECTORY / "sidebar_waves.png"
YUGEN_INTERFACE_REFERENCE_PATH = YUGEN_ASSETS_DIRECTORY / "interface_reference.png"
YUGEN_WINDOW_ICON_PREVIEW_PATH = YUGEN_ASSETS_DIRECTORY / "yugen_audio_icon.png"
YUGEN_WINDOW_ICON_PATH = YUGEN_ASSETS_DIRECTORY / "yugen_audio.ico"


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
