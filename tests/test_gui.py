"""Pruebas de los formatos mostrados en la interfaz gráfica."""

import unittest

from src.audio_formats import (
    AUDIO_FORMATS,
    AUDIO_QUALITIES,
    DEFAULT_AUDIO_FORMAT_KEY,
    DEFAULT_AUDIO_QUALITY_KEY,
)
from src.gui import (
    HISTORY_VISIBLE_ROWS,
    WINDOW_RESIZABLE,
    connection_delay_notice,
    fit_window_to_screen,
    format_bytes,
    format_eta,
    format_speed,
    window_sizes_for_system,
)


class GuiFormattingTests(unittest.TestCase):
    """Comprueba que los valores técnicos sean fáciles de leer."""

    def test_formats_bytes_and_speed(self) -> None:
        self.assertEqual(format_bytes(1536), "1.5 KB")
        self.assertEqual(format_speed(2048), "2.0 KB/s")
        self.assertEqual(format_bytes(None), "—")

    def test_mp3_is_default_and_all_labels_are_clear(self) -> None:
        self.assertEqual(DEFAULT_AUDIO_FORMAT_KEY, "mp3")
        self.assertEqual(AUDIO_FORMATS[0].key, "mp3")
        self.assertEqual(
            [audio_format.key for audio_format in AUDIO_FORMATS],
            ["mp3", "m4a", "opus", "wav", "flac", "ogg"],
        )
        self.assertTrue(all(" - " in item.selector_label for item in AUDIO_FORMATS))

    def test_formats_eta(self) -> None:
        self.assertEqual(format_eta(65), "01:05")
        self.assertEqual(format_eta(3661), "01:01:01")
        self.assertEqual(format_eta(None), "—")

    def test_medium_quality_is_default(self) -> None:
        self.assertEqual(DEFAULT_AUDIO_QUALITY_KEY, "medium")
        self.assertEqual(
            [quality.bitrate_kbps for quality in AUDIO_QUALITIES],
            [128, 192, 256, 320],
        )

    def test_connection_delay_notices(self) -> None:
        self.assertEqual(connection_delay_notice(29.9), (0, None))

        level_30, message_30 = connection_delay_notice(30.0)
        self.assertEqual(level_30, 1)
        self.assertIn("YouTube está tardando", message_30 or "")

        level_90, message_90 = connection_delay_notice(90.0)
        self.assertEqual(level_90, 2)
        self.assertIn("Puedes cancelar e intentar de nuevo", message_90 or "")

    def test_window_sizes_are_compact_on_windows_and_linux(self) -> None:
        self.assertEqual(window_sizes_for_system("Windows"), ((1000, 720), (850, 600)))
        self.assertEqual(window_sizes_for_system("Linux"), ((920, 680), (820, 580)))
        self.assertEqual(WINDOW_RESIZABLE, (False, False))
        self.assertEqual(HISTORY_VISIBLE_ROWS, 3)

    def test_window_fits_on_a_small_screen(self) -> None:
        fitted, minimum = fit_window_to_screen(
            (920, 680),
            (820, 580),
            (800, 600),
        )
        self.assertEqual(fitted, (760, 520))
        self.assertEqual(minimum, (760, 520))

    def test_linux_default_fits_on_common_laptop_screen(self) -> None:
        fitted, minimum = fit_window_to_screen(
            *window_sizes_for_system("Linux"),
            (1366, 768),
        )
        self.assertEqual(fitted, (920, 680))
        self.assertEqual(minimum, (820, 580))
