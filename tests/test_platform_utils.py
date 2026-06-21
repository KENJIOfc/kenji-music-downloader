"""Pruebas de apertura segura de archivos."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.platform_utils import OpenFileError, open_file


class PlatformUtilsTests(unittest.TestCase):
    def test_missing_file_raises_clear_error(self) -> None:
        with self.assertRaisesRegex(OpenFileError, "ya no existe"):
            open_file(Path("archivo-inexistente.mp3"))

    @patch("src.platform_utils.sys.platform", "win32")
    @patch("src.platform_utils.os.startfile", create=True)
    def test_windows_uses_default_application_without_shell(self, startfile_mock) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            audio_path = Path(temporary_directory) / "audio.mp3"
            audio_path.write_bytes(b"audio")

            open_file(audio_path)

            startfile_mock.assert_called_once_with(str(audio_path.resolve()))


if __name__ == "__main__":
    unittest.main()
