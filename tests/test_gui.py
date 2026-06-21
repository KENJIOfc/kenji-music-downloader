"""Pruebas de los formatos mostrados en la interfaz gráfica."""

import unittest

from src.audio_formats import AUDIO_FORMATS, DEFAULT_AUDIO_FORMAT_KEY
from src.gui import connection_delay_notice, format_bytes, format_eta, format_speed


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

    def test_connection_delay_notices(self) -> None:
        self.assertEqual(connection_delay_notice(29.9), (0, None))

        level_30, message_30 = connection_delay_notice(30.0)
        self.assertEqual(level_30, 1)
        self.assertIn("YouTube está tardando", message_30 or "")

        level_90, message_90 = connection_delay_notice(90.0)
        self.assertEqual(level_90, 2)
        self.assertIn("Puedes cancelar e intentar de nuevo", message_90 or "")
