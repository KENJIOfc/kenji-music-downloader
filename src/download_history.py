"""Historial persistente y limitado de descargas."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from src.user_settings import get_settings_path


HISTORY_LIMIT = 20
VALID_HISTORY_STATUSES = {"completed", "cancelled", "error"}
STATUS_LABELS = {
    "completed": "Completado",
    "cancelled": "Cancelado",
    "error": "Error",
}


@dataclass(frozen=True, slots=True)
class DownloadHistoryEntry:
    """Resultado compacto de una operación de descarga."""

    name: str
    output_format: str
    quality: str
    status: str
    path: str = ""
    created_at: str = ""

    @classmethod
    def create(
        cls,
        name: str,
        output_format: str,
        quality: str,
        status: str,
        path: str = "",
    ) -> "DownloadHistoryEntry":
        """Crea una entrada con fecha local y estado validado."""
        if status not in VALID_HISTORY_STATUSES:
            raise ValueError("Estado de historial no compatible.")
        return cls(
            name=name.strip() or "Descarga sin título",
            output_format=output_format.strip().upper(),
            quality=quality.strip(),
            status=status,
            path=path.strip(),
            created_at=datetime.now().astimezone().isoformat(timespec="seconds"),
        )

    @property
    def status_label(self) -> str:
        """Devuelve el estado listo para mostrar al usuario."""
        return STATUS_LABELS[self.status]


class HistoryError(RuntimeError):
    """Error controlado al leer o escribir el historial."""


def get_history_path() -> Path:
    """Guarda el historial junto a las demás preferencias locales."""
    return get_settings_path().with_name("history.json")


def _entry_from_dict(raw_entry: object) -> DownloadHistoryEntry:
    if not isinstance(raw_entry, dict):
        raise ValueError("Entrada de historial inválida.")

    entry = DownloadHistoryEntry(
        name=str(raw_entry.get("name", "")).strip() or "Descarga sin título",
        output_format=str(raw_entry.get("output_format", "")).strip().upper(),
        quality=str(raw_entry.get("quality", "")).strip(),
        status=str(raw_entry.get("status", "")).strip().lower(),
        path=str(raw_entry.get("path", "")).strip(),
        created_at=str(raw_entry.get("created_at", "")).strip(),
    )
    if entry.status not in VALID_HISTORY_STATUSES:
        raise ValueError("Estado de historial inválido.")
    return entry


def load_download_history(history_path: Path | None = None) -> list[DownloadHistoryEntry]:
    """Carga como máximo las veinte entradas más recientes."""
    path = history_path or get_history_path()
    if not path.exists():
        return []

    try:
        raw_entries = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw_entries, list):
            raise ValueError("El historial no contiene una lista.")
        return [_entry_from_dict(item) for item in raw_entries[:HISTORY_LIMIT]]
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as error:
        raise HistoryError("No se pudo cargar el historial de descargas.") from error


def save_download_history(
    entries: list[DownloadHistoryEntry],
    history_path: Path | None = None,
) -> None:
    """Guarda el historial de forma atómica y evita crecimiento ilimitado."""
    path = history_path or get_history_path()
    temporary_path = path.with_suffix(".tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path.write_text(
            json.dumps(
                [asdict(entry) for entry in entries[:HISTORY_LIMIT]],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        temporary_path.replace(path)
    except OSError as error:
        try:
            temporary_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise HistoryError("No se pudo guardar el historial de descargas.") from error


def add_history_entry(
    entries: list[DownloadHistoryEntry],
    entry: DownloadHistoryEntry,
    history_path: Path | None = None,
) -> list[DownloadHistoryEntry]:
    """Añade la entrada al principio, conserva veinte y persiste el resultado."""
    updated_entries = [entry, *entries][:HISTORY_LIMIT]
    save_download_history(updated_entries, history_path)
    return updated_entries


def remove_history_entry(
    entries: list[DownloadHistoryEntry],
    entry: DownloadHistoryEntry,
    history_path: Path | None = None,
) -> list[DownloadHistoryEntry]:
    """Elimina una entrada del JSON sin borrar el archivo al que apunta."""
    updated_entries = list(entries)
    entry_index = next(
        (index for index, current in enumerate(entries) if current is entry),
        None,
    )
    if entry_index is None:
        try:
            entry_index = updated_entries.index(entry)
        except ValueError:
            return updated_entries
    if entry_index is None:
        return updated_entries

    updated_entries.pop(entry_index)

    save_download_history(updated_entries, history_path)
    return updated_entries


def clear_download_history(history_path: Path | None = None) -> None:
    """Vacía el historial persistente sin tocar los archivos descargados."""
    save_download_history([], history_path)
