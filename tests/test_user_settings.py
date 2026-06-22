"""Pruebas de las preferencias persistentes sin tocar el perfil real."""

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.audio_formats import DEFAULT_AUDIO_FORMAT_KEY, DEFAULT_AUDIO_QUALITY_KEY
from src.user_settings import (
    DEFAULT_THEME,
    UserSettings,
    get_settings_path,
    load_user_settings,
    save_user_settings,
)


class UserSettingsTests(unittest.TestCase):
    """Comprueba escritura, carga y recuperación ante archivos inválidos."""

    @patch("src.user_settings.sys.platform", "win32")
    def test_windows_settings_path_uses_appdata(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            with patch.dict(os.environ, {"APPDATA": temporary_directory}):
                self.assertEqual(
                    get_settings_path(),
                    Path(temporary_directory)
                    / "KenjiMusicDownloader"
                    / "settings.json",
                )

    def test_round_trip_preserves_supported_preferences(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            settings_path = Path(temporary_directory) / "settings.json"
            expected = UserSettings(
                output_directory=str(Path(temporary_directory) / "audio"),
                output_format="flac",
                audio_quality="high",
                theme="dark",
                auto_check_updates=False,
                auto_download_updates=True,
                allow_auto_install_updates=True,
            )

            save_user_settings(expected, settings_path)

            self.assertEqual(load_user_settings(settings_path), expected)

    def test_invalid_json_returns_safe_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            settings_path = Path(temporary_directory) / "settings.json"
            settings_path.write_text("{archivo roto", encoding="utf-8")

            loaded = load_user_settings(settings_path)

            self.assertEqual(loaded.output_format, DEFAULT_AUDIO_FORMAT_KEY)
            self.assertEqual(loaded.audio_quality, DEFAULT_AUDIO_QUALITY_KEY)

    def test_legacy_settings_without_theme_use_light_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            settings_path = Path(temporary_directory) / "settings.json"
            settings_path.write_text(
                json.dumps(
                    {
                        "output_directory": temporary_directory,
                        "output_format": "mp3",
                        "audio_quality": "medium",
                    }
                ),
                encoding="utf-8",
            )

            loaded = load_user_settings(settings_path)
            self.assertEqual(loaded.theme, DEFAULT_THEME)
            self.assertTrue(loaded.auto_check_updates)
            self.assertFalse(loaded.auto_download_updates)
            self.assertFalse(loaded.allow_auto_install_updates)

    def test_unsupported_keys_return_safe_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            settings_path = Path(temporary_directory) / "settings.json"
            settings_path.write_text(
                json.dumps(
                    {
                        "output_directory": temporary_directory,
                        "output_format": "exe",
                        "audio_quality": "impossible",
                    }
                ),
                encoding="utf-8",
            )

            loaded = load_user_settings(settings_path)

            self.assertEqual(loaded.output_format, DEFAULT_AUDIO_FORMAT_KEY)
            self.assertEqual(loaded.audio_quality, DEFAULT_AUDIO_QUALITY_KEY)

    def test_unsupported_theme_returns_safe_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            settings_path = Path(temporary_directory) / "settings.json"
            settings_path.write_text(
                json.dumps(
                    {
                        "output_directory": temporary_directory,
                        "output_format": "mp3",
                        "audio_quality": "medium",
                        "theme": "neon",
                    }
                ),
                encoding="utf-8",
            )

            loaded = load_user_settings(settings_path)
            self.assertEqual(loaded.theme, DEFAULT_THEME)

    def test_invalid_update_preference_returns_safe_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            settings_path = Path(temporary_directory) / "settings.json"
            settings_path.write_text(
                json.dumps(
                    {
                        "output_directory": temporary_directory,
                        "output_format": "mp3",
                        "audio_quality": "medium",
                        "theme": "light",
                        "check_updates_on_startup": "yes",
                    }
                ),
                encoding="utf-8",
            )

            loaded = load_user_settings(settings_path)
            self.assertTrue(loaded.auto_check_updates)
            self.assertFalse(loaded.auto_download_updates)
            self.assertFalse(loaded.allow_auto_install_updates)

    def test_migrates_legacy_update_preference(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            settings_path = Path(temporary_directory) / "settings.json"
            settings_path.write_text(
                json.dumps(
                    {
                        "output_directory": temporary_directory,
                        "output_format": "mp3",
                        "audio_quality": "medium",
                        "theme": "light",
                        "check_updates_on_startup": False,
                    }
                ),
                encoding="utf-8",
            )

            loaded = load_user_settings(settings_path)

            self.assertFalse(loaded.auto_check_updates)
            self.assertFalse(loaded.auto_download_updates)
            self.assertFalse(loaded.allow_auto_install_updates)


if __name__ == "__main__":
    unittest.main()
