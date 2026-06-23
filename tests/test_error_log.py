"""Pruebas del registro local de errores."""

from pathlib import Path
import os
import tempfile
import unittest
from unittest.mock import patch

from src.error_log import (
    clear_internal_logs,
    get_error_log_path,
    log_error,
    log_info,
    read_error_log,
)


class ErrorLogTests(unittest.TestCase):
    @patch("src.user_settings.sys.platform", "win32")
    def test_default_windows_log_uses_appdata_logs_folder(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            with patch.dict(os.environ, {"APPDATA": temporary_directory}):
                expected = (
                    Path(temporary_directory)
                    / "KenjiMusicDownloader"
                    / "logs"
                    / "errors.log"
                )
                self.assertEqual(get_error_log_path(), expected)

    def test_empty_log_returns_empty_text(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            log_path = Path(temporary_directory) / "errors.log"
            self.assertEqual(read_error_log(log_path), "")

    def test_log_contains_category_message_and_exception(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            log_path = Path(temporary_directory) / "errors.log"
            error = RuntimeError("detalle técnico")

            log_error("FFmpeg", "Falló la conversión.", error, log_path)
            content = read_error_log(log_path)

            self.assertIn("[FFmpeg]", content)
            self.assertIn("Falló la conversión", content)
            self.assertIn("RuntimeError: detalle técnico", content)

    def test_info_events_are_recorded_without_exception(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            log_path = Path(temporary_directory) / "errors.log"

            log_info("Instalación", "FFmpeg instalado.", log_path)
            content = read_error_log(log_path)

            self.assertIn("[INFO] [Instalación]", content)
            self.assertIn("FFmpeg instalado.", content)

    def test_clear_internal_logs_only_empties_app_log_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            base_path = Path(temporary_directory)
            logs_directory = base_path / "logs"
            downloads_directory = base_path / "downloads"
            logs_directory.mkdir()
            downloads_directory.mkdir()

            error_log = logs_directory / "errors.log"
            diagnostic_log = logs_directory / "diagnostics.log"
            legacy_log = base_path / "errors.log"
            note_file = logs_directory / "note.txt"
            settings_file = base_path / "settings.json"
            history_file = base_path / "history.json"
            downloaded_file = downloads_directory / "cancion.mp3"

            for log_file in (error_log, diagnostic_log, legacy_log):
                log_file.write_text("contenido anterior", encoding="utf-8")
            note_file.write_text("no es log", encoding="utf-8")
            settings_file.write_text('{"theme": "dark"}', encoding="utf-8")
            history_file.write_text("[]", encoding="utf-8")
            downloaded_file.write_text("audio falso", encoding="utf-8")

            cleared_count = clear_internal_logs(logs_directory, legacy_log)

            self.assertEqual(cleared_count, 3)
            self.assertEqual(error_log.read_text(encoding="utf-8"), "")
            self.assertEqual(diagnostic_log.read_text(encoding="utf-8"), "")
            self.assertEqual(legacy_log.read_text(encoding="utf-8"), "")
            self.assertEqual(note_file.read_text(encoding="utf-8"), "no es log")
            self.assertEqual(
                settings_file.read_text(encoding="utf-8"),
                '{"theme": "dark"}',
            )
            self.assertEqual(history_file.read_text(encoding="utf-8"), "[]")
            self.assertEqual(
                downloaded_file.read_text(encoding="utf-8"),
                "audio falso",
            )

    def test_clear_internal_logs_with_no_logs_is_safe(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            base_path = Path(temporary_directory)
            cleared_count = clear_internal_logs(
                base_path / "logs",
                base_path / "errors.log",
            )

            self.assertEqual(cleared_count, 0)


if __name__ == "__main__":
    unittest.main()
