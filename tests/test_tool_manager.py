"""Pruebas del gestor local de FFmpeg sin realizar descargas reales."""

from io import BytesIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from src.tool_manager import (
    LOCAL_SOURCE,
    PATH_SOURCE,
    ToolInstallationError,
    ensure_tools_directory,
    install_ffmpeg_tools,
    missing_ffmpeg_tools,
    resolve_tool,
)


class FakeHTTPResponse(BytesIO):
    """Respuesta mínima compatible con urllib para las pruebas."""

    def __init__(self, content: bytes) -> None:
        super().__init__(content)
        self.headers = {"Content-Length": str(len(content))}


def make_ffmpeg_zip() -> bytes:
    """Crea un ZIP pequeño con los nombres reales y firmas PE simuladas."""
    stream = BytesIO()
    with ZipFile(stream, "w") as archive:
        archive.writestr("ffmpeg-test/bin/ffmpeg.exe", b"MZffmpeg")
        archive.writestr("ffmpeg-test/bin/ffprobe.exe", b"MZffprobe")
        archive.writestr("ffmpeg-test/doc/readme.txt", b"no extraer")
    return stream.getvalue()


class ToolResolutionTests(unittest.TestCase):
    @patch("src.tool_manager.sys.platform", "win32")
    def test_detects_tools_in_local_directory_before_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            tools_directory = Path(temporary_directory) / "tools"
            tools_directory.mkdir()
            ffmpeg_path = tools_directory / "ffmpeg.exe"
            ffmpeg_path.write_bytes(b"MZ")

            with patch("src.tool_manager.get_tools_directory", return_value=tools_directory):
                with patch("src.tool_manager.shutil.which") as which_mock:
                    result = resolve_tool("ffmpeg")

            self.assertIsNotNone(result)
            assert result is not None
            self.assertEqual(result.path, ffmpeg_path.resolve())
            self.assertEqual(result.source, LOCAL_SOURCE)
            which_mock.assert_not_called()

    @patch("src.tool_manager.sys.platform", "win32")
    def test_detects_tools_in_system_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            tools_directory = Path(temporary_directory) / "local-tools"
            path_tool = Path(temporary_directory) / "path" / "ffmpeg.exe"
            path_tool.parent.mkdir()
            path_tool.write_bytes(b"MZ")

            with patch("src.tool_manager.get_tools_directory", return_value=tools_directory):
                with patch("src.tool_manager._application_directory", return_value=Path(temporary_directory) / "app"):
                    with patch("src.tool_manager.shutil.which", return_value=str(path_tool)):
                        result = resolve_tool("ffmpeg")

            self.assertIsNotNone(result)
            assert result is not None
            self.assertEqual(result.source, PATH_SOURCE)
            self.assertEqual(result.path, path_tool.resolve())

    @patch("src.tool_manager.sys.platform", "win32")
    def test_reports_missing_tools(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            with patch("src.tool_manager.get_tools_directory", return_value=Path(temporary_directory) / "tools"):
                with patch("src.tool_manager._application_directory", return_value=Path(temporary_directory) / "app"):
                    with patch("src.tool_manager.shutil.which", return_value=None):
                        self.assertEqual(
                            missing_ffmpeg_tools(),
                            ("ffmpeg", "ffprobe"),
                        )

    def test_creates_tools_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            expected = Path(temporary_directory) / "perfil" / "tools"
            with patch("src.tool_manager.get_tools_directory", return_value=expected):
                result = ensure_tools_directory()
            self.assertEqual(result, expected)
            self.assertTrue(expected.is_dir())


class ToolInstallationTests(unittest.TestCase):
    @patch("src.tool_manager.sys.platform", "win32")
    @patch("src.tool_manager.sys.maxsize", 2**63 - 1)
    def test_rejects_unapproved_download_source(self) -> None:
        with self.assertRaisesRegex(ToolInstallationError, "fuente HTTPS permitida"):
            install_ffmpeg_tools(download_url="https://example.com/ffmpeg.zip")

    @patch("src.tool_manager.sys.platform", "win32")
    @patch("src.tool_manager.sys.maxsize", 2**63 - 1)
    @patch("src.tool_manager.log_info")
    @patch("src.tool_manager.log_error")
    def test_installs_only_required_binaries(
        self,
        _log_error_mock,
        _log_info_mock,
    ) -> None:
        archive_content = make_ffmpeg_zip()
        statuses: list[str] = []

        with tempfile.TemporaryDirectory() as temporary_directory:
            tools_directory = Path(temporary_directory) / "profile" / "tools"
            with patch("src.tool_manager.get_tools_directory", return_value=tools_directory):
                installed = install_ffmpeg_tools(
                    status_callback=statuses.append,
                    opener=lambda _request, timeout: FakeHTTPResponse(archive_content),
                )

            self.assertEqual(set(installed), {"ffmpeg", "ffprobe"})
            self.assertEqual(
                {path.name for path in tools_directory.iterdir()},
                {"ffmpeg.exe", "ffprobe.exe"},
            )
            self.assertTrue(all(path.read_bytes().startswith(b"MZ") for path in installed.values()))

        self.assertTrue(any("Descargando FFmpeg" in status for status in statuses))
        self.assertIn("Extrayendo herramientas…", statuses)
        self.assertEqual(statuses[-1], "Instalación completada.")

    @patch("src.tool_manager.sys.platform", "win32")
    @patch("src.tool_manager.sys.maxsize", 2**63 - 1)
    @patch("src.tool_manager.log_info")
    @patch("src.tool_manager.log_error")
    def test_rejects_invalid_zip(
        self,
        _log_error_mock,
        _log_info_mock,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            tools_directory = Path(temporary_directory) / "profile" / "tools"
            with patch("src.tool_manager.get_tools_directory", return_value=tools_directory):
                with self.assertRaisesRegex(ToolInstallationError, "ZIP válido"):
                    install_ffmpeg_tools(
                        opener=lambda _request, timeout: FakeHTTPResponse(b"no es zip"),
                    )


if __name__ == "__main__":
    unittest.main()
