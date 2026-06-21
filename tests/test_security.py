"""Pruebas de la lista permitida de enlaces de YouTube."""

import unittest

from src.security import InvalidYouTubeURLError, validate_and_normalize_youtube_url


class YouTubeURLValidationTests(unittest.TestCase):
    """Comprueba que solo lleguen identificadores de video seguros al descargador."""

    def test_accepts_supported_video_urls(self) -> None:
        expected = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        valid_urls = [
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://music.youtube.com/watch?v=dQw4w9WgXcQ&list=otro-dato",
            "https://m.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://youtu.be/dQw4w9WgXcQ?t=20",
            "https://youtube.com/shorts/dQw4w9WgXcQ",
            "https://youtube.com/live/dQw4w9WgXcQ",
        ]

        for url in valid_urls:
            with self.subTest(url=url):
                self.assertEqual(validate_and_normalize_youtube_url(url), expected)

    def test_rejects_unsafe_or_unsupported_urls(self) -> None:
        invalid_urls = [
            "",
            "javascript:alert(1)",
            "https://youtube.com.example.org/watch?v=dQw4w9WgXcQ",
            "https://user:password@youtube.com/watch?v=dQw4w9WgXcQ",
            "https://youtube.com:8080/watch?v=dQw4w9WgXcQ",
            "https://youtube.com/playlist?list=PL123",
            "https://youtube.com/embed/dQw4w9WgXcQ",
            "https://youtu.be/identificador-invalido",
            "https://example.com/watch?v=dQw4w9WgXcQ",
        ]

        for url in invalid_urls:
            with self.subTest(url=url):
                with self.assertRaises(InvalidYouTubeURLError):
                    validate_and_normalize_youtube_url(url)


if __name__ == "__main__":
    unittest.main()

