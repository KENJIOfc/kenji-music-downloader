"""Registro local de errores importantes de la aplicación."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import traceback

from src.user_settings import get_settings_path


class ErrorLogReadError(RuntimeError):
    """Error controlado al consultar el registro."""


def get_error_log_path() -> Path:
    """Ubica el registro en una subcarpeta local dedicada."""
    return get_settings_path().parent / "logs" / "errors.log"


def get_legacy_error_log_path() -> Path:
    """Ruta utilizada por versiones anteriores para conservar compatibilidad."""
    return get_settings_path().with_name("errors.log")


def log_error(
    category: str,
    message: str,
    error: BaseException | None = None,
    log_path: Path | None = None,
) -> None:
    """Añade un error al registro; nunca provoca el cierre de la aplicación."""
    path = log_path or get_error_log_path()
    timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
    lines = [f"[{timestamp}] [{category}] {message.strip()}"]
    if error is not None:
        lines.extend(
            line.rstrip("\n")
            for line in traceback.format_exception(error)
        )
    lines.append("-" * 72)

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as log_file:
            log_file.write("\n".join(lines) + "\n")
    except OSError:
        # Un fallo del registro nunca debe ocultar el error original.
        return


def read_error_log(log_path: Path | None = None) -> str:
    """Lee el registro o devuelve texto vacío cuando aún no existe."""
    path = log_path or get_error_log_path()
    if log_path is None and not path.exists():
        legacy_path = get_legacy_error_log_path()
        if legacy_path.exists():
            path = legacy_path
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError as error:
        raise ErrorLogReadError("No se pudo leer el registro de errores.") from error
