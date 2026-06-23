"""Carga y guardado de preferencias locales del usuario."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from src.audio_formats import (
    DEFAULT_AUDIO_FORMAT_KEY,
    DEFAULT_AUDIO_QUALITY_KEY,
    get_audio_format,
    get_audio_quality,
)
from src.config import DOWNLOADS_DIRECTORY


DEFAULT_THEME = "dark"
VALID_THEMES = {"light", "dark"}


@dataclass(frozen=True)
class UserSettings:
    """Preferencias que deben sobrevivir entre ejecuciones."""

    output_directory: str = str(DOWNLOADS_DIRECTORY)
    output_format: str = DEFAULT_AUDIO_FORMAT_KEY
    audio_quality: str = DEFAULT_AUDIO_QUALITY_KEY
    theme: str = DEFAULT_THEME
    auto_check_updates: bool = True
    auto_download_updates: bool = False
    allow_auto_install_updates: bool = False


class SettingsError(RuntimeError):
    """Error controlado al escribir las preferencias."""


def get_settings_path() -> Path:
    """Obtiene una ruta apropiada para Windows, Linux o macOS."""
    if sys.platform == "win32":
        base_directory = Path(
            os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")
        )
        return base_directory / "KenjiMusicDownloader" / "settings.json"

    base_directory = Path(
        os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")
    )
    return base_directory / "kenji-music-downloader" / "settings.json"


def load_user_settings(settings_path: Path | None = None) -> UserSettings:
    """Carga preferencias válidas y recupera valores seguros si el JSON falla."""
    path = settings_path or get_settings_path()
    try:
        raw_data = json.loads(path.read_text(encoding="utf-8"))
        output_directory = str(raw_data.get("output_directory", "")).strip()
        output_format = str(raw_data.get("output_format", "")).strip().lower()
        audio_quality = str(raw_data.get("audio_quality", "")).strip().lower()
        theme = str(raw_data.get("theme", DEFAULT_THEME)).strip().lower()
        # Migra de forma transparente la clave usada por versiones anteriores.
        auto_check_updates = raw_data.get(
            "auto_check_updates",
            raw_data.get("check_updates_on_startup", True),
        )
        auto_download_updates = raw_data.get("auto_download_updates", False)
        allow_auto_install_updates = raw_data.get(
            "allow_auto_install_updates",
            False,
        )

        # Estas claves se validan antes de que puedan llegar al descargador.
        get_audio_format(output_format)
        get_audio_quality(audio_quality)
        if theme not in VALID_THEMES:
            raise ValueError("Tema no compatible.")
        if not isinstance(auto_check_updates, bool):
            raise ValueError("Preferencia de actualizaciones no compatible.")
        if not isinstance(auto_download_updates, bool):
            raise ValueError("Preferencia de descarga automática no compatible.")
        if not isinstance(allow_auto_install_updates, bool):
            raise ValueError("Preferencia de instalación automática no compatible.")
        if not output_directory:
            output_directory = str(DOWNLOADS_DIRECTORY)

        return UserSettings(
            output_directory,
            output_format,
            audio_quality,
            theme,
            auto_check_updates,
            auto_download_updates,
            allow_auto_install_updates,
        )
    except (OSError, json.JSONDecodeError, TypeError, ValueError, AttributeError) as error:
        # Solo registramos errores del archivo real; las pruebas pueden usar otra ruta.
        if settings_path is None and path.exists():
            try:
                from src.error_log import log_error

                log_error("Configuración", "No se pudo cargar settings.json.", error)
            except Exception:
                pass
        return UserSettings()


def save_user_settings(
    settings: UserSettings,
    settings_path: Path | None = None,
) -> None:
    """Guarda el JSON de forma atómica para evitar archivos incompletos."""
    path = settings_path or get_settings_path()
    temporary_path = path.with_suffix(".tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path.write_text(
            json.dumps(asdict(settings), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary_path.replace(path)
    except OSError as error:
        try:
            temporary_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise SettingsError(
            "No se pudo guardar la configuración del usuario."
        ) from error
