"""Pruebas de preparación segura de la carpeta de salida."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.config import (
    ASSETS_DIRECTORY,
    INTERFACE_REFERENCE_IMAGE_PATH,
    LOGO_HEADER_IMAGE_PATH,
    LOGO_IMAGE_PATH,
    TASKBAR_ICON_PATH,
    TASKBAR_ICON_PREVIEW_PATH,
    TYPOGRAPHY_REFERENCE_IMAGE_PATH,
    UPDATE_INSTALLER_ICON_IMAGE_PATH,
    UPDATE_INSTALLER_ICON_PATH,
    UPDATE_INSTALLER_ICON_PREVIEW_PATH,
    YUGEN_CONCERT_PLACEHOLDER_PATH,
    YUGEN_DETAILS_DECORATION_PATH,
    YUGEN_DOWNLOAD_BUTTON_PATH,
    YUGEN_EMBLEM_PATH,
    YUGEN_HEADER_EQUALIZER_PATH,
    YUGEN_HERO_BANNER_PATH,
    YUGEN_PLAQUE_PATH,
    YUGEN_PROGRESS_BRUSH_PATH,
    YUGEN_SIDEBAR_WAVES_PATH,
    YUGEN_WINDOW_ICON_PATH,
    YUGEN_WINDOW_ICON_PREVIEW_PATH,
    ConfigurationError,
    prepare_environment,
    prepare_output_directory,
)


class ConfigurationTests(unittest.TestCase):
    def test_visual_assets_exist_in_project(self) -> None:
        self.assertEqual(LOGO_IMAGE_PATH.parent, ASSETS_DIRECTORY)
        self.assertEqual(LOGO_IMAGE_PATH.name, "logo_main.png")
        self.assertEqual(TASKBAR_ICON_PATH.name, "logo_main.ico")
        self.assertEqual(UPDATE_INSTALLER_ICON_PATH.name, "updater_logo.ico")
        self.assertTrue(LOGO_IMAGE_PATH.is_file())
        self.assertTrue(LOGO_HEADER_IMAGE_PATH.is_file())
        self.assertTrue(TASKBAR_ICON_PREVIEW_PATH.is_file())
        self.assertTrue(TASKBAR_ICON_PATH.is_file())
        self.assertTrue(UPDATE_INSTALLER_ICON_IMAGE_PATH.is_file())
        self.assertTrue(UPDATE_INSTALLER_ICON_PREVIEW_PATH.is_file())
        self.assertTrue(UPDATE_INSTALLER_ICON_PATH.is_file())
        self.assertTrue(TYPOGRAPHY_REFERENCE_IMAGE_PATH.is_file())
        self.assertTrue(INTERFACE_REFERENCE_IMAGE_PATH.is_file())
        self.assertEqual(YUGEN_WINDOW_ICON_PATH.name, "yugen_audio.ico")
        for yugen_asset in (
            YUGEN_HERO_BANNER_PATH,
            YUGEN_EMBLEM_PATH,
            YUGEN_PLAQUE_PATH,
            YUGEN_HEADER_EQUALIZER_PATH,
            YUGEN_DOWNLOAD_BUTTON_PATH,
            YUGEN_PROGRESS_BRUSH_PATH,
            YUGEN_CONCERT_PLACEHOLDER_PATH,
            YUGEN_DETAILS_DECORATION_PATH,
            YUGEN_SIDEBAR_WAVES_PATH,
            YUGEN_WINDOW_ICON_PATH,
            YUGEN_WINDOW_ICON_PREVIEW_PATH,
        ):
            self.assertTrue(yugen_asset.is_file(), yugen_asset)

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
