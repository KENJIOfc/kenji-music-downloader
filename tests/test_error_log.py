"""Pruebas del registro local de errores."""

from pathlib import Path
import os
import tempfile
import unittest
from unittest.mock import patch

from src.error_log import get_error_log_path, log_error, log_info, read_error_log


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


if __name__ == "__main__":
    unittest.main()
