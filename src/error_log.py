"""Registro local de errores importantes de la aplicación."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import traceback

from src.user_settings import get_settings_path


class ErrorLogReadError(RuntimeError):
    """Error controlado al consultar el registro."""


class ErrorLogClearError(RuntimeError):
    """Error controlado al limpiar registros internos."""


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


def log_info(
    category: str,
    message: str,
    log_path: Path | None = None,
) -> None:
    """Registra operaciones relevantes sin marcarlas como excepciones."""
    path = log_path or get_error_log_path()
    timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
    lines = [
        f"[{timestamp}] [INFO] [{category}] {message.strip()}",
        "-" * 72,
    ]
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as log_file:
            log_file.write("\n".join(lines) + "\n")
    except OSError:
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


def _is_relative_to(child: Path, parent: Path) -> bool:
    """Comprueba contención de rutas sin depender de rutas fijas del sistema."""
    try:
        child.resolve(strict=False).relative_to(parent.resolve(strict=False))
        return True
    except ValueError:
        return False


def clear_internal_logs(
    log_directory: Path | None = None,
    legacy_log_path: Path | None = None,
) -> int:
    """Vacía únicamente archivos `.log` generados por la app.

    No borra carpetas completas ni toca historial, configuración, descargas,
    assets, ejecutables o manifests. Por seguridad solo actúa dentro de la
    carpeta dedicada `logs/` y sobre el archivo legacy `errors.log`.
    """
    logs_dir = log_directory or get_error_log_path().parent
    legacy_path = legacy_log_path or get_legacy_error_log_path()
    candidates: set[Path] = {logs_dir / "errors.log", legacy_path}

    try:
        if logs_dir.exists():
            candidates.update(
                path for path in logs_dir.glob("*.log") if path.is_file()
            )

        cleared_count = 0
        for path in sorted(candidates):
            resolved_path = path.resolve(strict=False)
            is_allowed_log = _is_relative_to(resolved_path, logs_dir)
            is_legacy_log = (
                resolved_path == legacy_path.resolve(strict=False)
            )
            if not (is_allowed_log or is_legacy_log):
                continue
            if resolved_path.suffix.lower() != ".log":
                continue
            if not resolved_path.exists() or not resolved_path.is_file():
                continue

            # Vaciar es más seguro que eliminar: evita borrar directorios o
            # rutas inesperadas y conserva permisos/metadatos del archivo.
            resolved_path.write_text("", encoding="utf-8")
            cleared_count += 1

        return cleared_count
    except OSError as error:
        raise ErrorLogClearError(
            "No se pudieron limpiar los registros internos."
        ) from error
