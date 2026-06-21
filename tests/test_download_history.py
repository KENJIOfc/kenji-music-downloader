"""Pruebas del historial persistente y limitado."""

from pathlib import Path
from dataclasses import replace
import tempfile
import unittest

from src.download_history import (
    HISTORY_LIMIT,
    DownloadHistoryEntry,
    HistoryError,
    add_history_entry,
    clear_download_history,
    load_download_history,
    remove_history_entry,
)


class DownloadHistoryTests(unittest.TestCase):
    """Comprueba estados, persistencia y límite de entradas."""

    def test_history_keeps_only_twenty_most_recent_entries(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            history_path = Path(temporary_directory) / "history.json"
            entries: list[DownloadHistoryEntry] = []

            for index in range(HISTORY_LIMIT + 5):
                entry = DownloadHistoryEntry.create(
                    name=f"Canción {index}.mp3",
                    output_format="MP3",
                    quality="192 kbps",
                    status="completed",
                    path=str(Path(temporary_directory) / f"Canción {index}.mp3"),
                )
                entries = add_history_entry(entries, entry, history_path)

            loaded = load_download_history(history_path)
            self.assertEqual(len(loaded), HISTORY_LIMIT)
            self.assertEqual(loaded[0].name, "Canción 24.mp3")
            self.assertEqual(loaded[-1].name, "Canción 5.mp3")

    def test_history_preserves_cancelled_and_error_states(self) -> None:
        cancelled = DownloadHistoryEntry.create(
            "Canción cancelada",
            "OPUS",
            "128 kbps",
            "cancelled",
        )
        failed = DownloadHistoryEntry.create(
            "Canción con error",
            "FLAC",
            "Sin pérdida",
            "error",
        )

        self.assertEqual(cancelled.status_label, "Cancelado")
        self.assertEqual(failed.status_label, "Error")

    def test_clear_history_does_not_touch_downloads(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            base = Path(temporary_directory)
            history_path = base / "history.json"
            audio_path = base / "Canción.mp3"
            audio_path.write_bytes(b"audio")
            entry = DownloadHistoryEntry.create(
                audio_path.name,
                "MP3",
                "192 kbps",
                "completed",
                str(audio_path),
            )
            add_history_entry([], entry, history_path)

            clear_download_history(history_path)

            self.assertEqual(load_download_history(history_path), [])
            self.assertTrue(audio_path.is_file())

    def test_invalid_history_raises_controlled_error(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            history_path = Path(temporary_directory) / "history.json"
            history_path.write_text("{roto", encoding="utf-8")

            with self.assertRaises(HistoryError):
                load_download_history(history_path)

    def test_remove_entry_keeps_the_real_audio_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            base = Path(temporary_directory)
            history_path = base / "history.json"
            audio_path = base / "Audio.flac"
            audio_path.write_bytes(b"audio")
            entry = DownloadHistoryEntry.create(
                audio_path.name,
                "FLAC",
                "Sin pérdida",
                "completed",
                str(audio_path),
            )
            entries = add_history_entry([], entry, history_path)

            updated = remove_history_entry(entries, entry, history_path)

            self.assertEqual(updated, [])
            self.assertEqual(load_download_history(history_path), [])
            self.assertTrue(audio_path.is_file())

    def test_remove_uses_the_exact_selected_entry_when_duplicates_exist(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            history_path = Path(temporary_directory) / "history.json"
            first = DownloadHistoryEntry.create(
                "Duplicada.mp3",
                "MP3",
                "192 kbps",
                "completed",
                str(Path(temporary_directory) / "Duplicada.mp3"),
            )
            second = replace(first)

            updated = remove_history_entry([first, second], second, history_path)

            self.assertEqual(len(updated), 1)
            self.assertIs(updated[0], first)


if __name__ == "__main__":
    unittest.main()
