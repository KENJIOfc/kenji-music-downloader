"""Pruebas de preparación segura de la carpeta de salida."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.config import ConfigurationError, prepare_environment, prepare_output_directory


class ConfigurationTests(unittest.TestCase):
    def test_creates_missing_output_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            expected = Path(temporary_directory) / "audio" / "nueva"

            result = prepare_output_directory(expected)

            self.assertEqual(result, expected.resolve())
            self.assertTrue(result.is_dir())
            self.assertFalse(
                any(path.name.startswith(".kenji-write-test-") for path in result.iterdir())
            )

    def test_rejects_output_path_that_is_a_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            file_path = Path(temporary_directory) / "no-es-carpeta"
            file_path.write_text("contenido", encoding="utf-8")

            with self.assertRaises(ConfigurationError):
                prepare_output_directory(file_path)

    @patch("src.tool_manager.missing_ffmpeg_tools", return_value=("ffmpeg", "ffprobe"))
    def test_environment_rejects_download_when_tools_are_missing(
        self,
        _missing_mock,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            with self.assertRaisesRegex(ConfigurationError, "Instalar herramientas"):
                prepare_environment(Path(temporary_directory))


if __name__ == "__main__":
    unittest.main()
