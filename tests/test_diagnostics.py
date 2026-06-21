"""Pruebas de diagnóstico sin acceder a Internet ni ejecutar herramientas."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.diagnostics import verify_tools


class DiagnosticsTests(unittest.TestCase):
    @patch("src.diagnostics.check_internet_connection", return_value=True)
    @patch("src.diagnostics.shutil.which")
    @patch("src.diagnostics.importlib.util.find_spec")
    def test_reports_all_required_tools(
        self,
        find_spec_mock,
        which_mock,
        _connection_mock,
    ) -> None:
        find_spec_mock.return_value = object()
        which_mock.side_effect = lambda command: f"C:/tools/{command}.exe"

        with tempfile.TemporaryDirectory() as temporary_directory:
            results = verify_tools(Path(temporary_directory))

        self.assertEqual(
            [result.label for result in results],
            ["yt-dlp", "ffmpeg", "ffprobe", "Carpeta de salida", "Conexión"],
        )
        self.assertTrue(all(result.available for result in results))
        self.assertIn("yt-dlp: encontrado", results[0].display_line())
        self.assertIn("Carpeta de salida: válida", results[3].display_line())
        self.assertIn("Conexión: disponible", results[4].display_line())

    @patch("src.diagnostics.check_internet_connection", return_value=False)
    @patch("src.diagnostics.shutil.which", return_value=None)
    @patch("src.diagnostics.importlib.util.find_spec", return_value=None)
    def test_reports_missing_dependencies(
        self,
        _find_spec_mock,
        _which_mock,
        _connection_mock,
    ) -> None:
        results = verify_tools(Path("carpeta-que-no-existe"))
        self.assertTrue(all(not result.available for result in results))


if __name__ == "__main__":
    unittest.main()
