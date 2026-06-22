"""Pruebas de diagnóstico sin acceder a Internet ni ejecutar herramientas."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.diagnostics import verify_tools
from src.tool_manager import PATH_SOURCE, ResolvedTool


class DiagnosticsTests(unittest.TestCase):
    @patch("src.diagnostics.check_internet_connection", return_value=True)
    @patch("src.diagnostics.resolve_tool")
    @patch("src.diagnostics.importlib.util.find_spec")
    def test_reports_all_required_tools(
        self,
        find_spec_mock,
        resolve_tool_mock,
        _connection_mock,
    ) -> None:
        find_spec_mock.return_value = object()
        resolve_tool_mock.side_effect = lambda command: ResolvedTool(
            command,
            Path(f"C:/tools/{command}.exe"),
            PATH_SOURCE,
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            results = verify_tools(Path(temporary_directory))

        self.assertEqual(
            [result.label for result in results],
            ["yt-dlp", "ffmpeg", "ffprobe", "Carpeta de salida", "Conexión"],
        )
        self.assertTrue(all(result.available for result in results))
        self.assertIn("yt-dlp: encontrado", results[0].display_line())
        self.assertIn("PATH del sistema", results[1].detail)
        self.assertIn("Carpeta de salida: válida", results[3].display_line())
        self.assertIn("Conexión: disponible", results[4].display_line())

    @patch("src.diagnostics.check_internet_connection", return_value=False)
    @patch("src.diagnostics.resolve_tool", return_value=None)
    @patch("src.diagnostics.importlib.util.find_spec", return_value=None)
    def test_reports_missing_dependencies_and_creates_output_directory(
        self,
        _find_spec_mock,
        _resolve_tool_mock,
        _connection_mock,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_directory = Path(temporary_directory) / "nueva-salida"
            results = verify_tools(output_directory)

            self.assertTrue(output_directory.is_dir())

        by_label = {result.label: result for result in results}
        self.assertFalse(by_label["yt-dlp"].available)
        self.assertFalse(by_label["ffmpeg"].available)
        self.assertFalse(by_label["ffprobe"].available)
        self.assertTrue(by_label["Carpeta de salida"].available)
        self.assertFalse(by_label["Conexión"].available)


if __name__ == "__main__":
    unittest.main()
