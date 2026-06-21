"""Pruebas del avance reportado por el servicio de descarga."""

from pathlib import Path
import tempfile
from threading import Event
import unittest
from unittest.mock import patch
from yt_dlp.utils import DownloadError as YtDlpDownloadError

from src.audio_formats import AUDIO_FORMATS
from src.downloader import (
    AudioDownloader,
    AudioDownloadError,
    DownloadCancelledError,
    DownloadProgress,
    TimingMetric,
    _friendly_error_message,
)


class DownloaderProgressTests(unittest.TestCase):
    """Comprueba el contrato usado por la consola y la interfaz gráfica."""

    def setUp(self) -> None:
        self.statuses: list[str] = []
        self.progress_events: list[DownloadProgress] = []
        self.downloader = AudioDownloader(
            Path("downloads"),
            status_callback=self.statuses.append,
            progress_callback=self.progress_events.append,
        )

    def test_reports_download_details_from_hook(self) -> None:
        self.downloader._progress_hook(
            {
                "status": "downloading",
                "downloaded_bytes": 256,
                "total_bytes": 1024,
                "speed": 128.5,
                "eta": 6,
                "info_dict": {"title": "Video de prueba"},
            }
        )

        progress = self.progress_events[0]
        self.assertEqual(progress.stage, "downloading")
        self.assertEqual(progress.percentage, 25.0)
        self.assertEqual(progress.downloaded_bytes, 256)
        self.assertEqual(progress.total_bytes, 1024)
        self.assertEqual(progress.speed_bytes_per_second, 128.5)
        self.assertEqual(progress.eta_seconds, 6)
        self.assertEqual(progress.title, "Video de prueba")
        self.assertEqual(self.statuses, ["Descargando audio..."])

    def test_uses_indeterminate_progress_during_conversion(self) -> None:
        self.downloader._progress_hook({"status": "finished"})

        self.assertEqual(
            self.statuses,
            ["Convirtiendo a MP3..."],
        )
        self.assertEqual(self.progress_events[0].stage, "converting")
        self.assertIsNone(self.progress_events[0].percentage)


class FriendlyErrorTests(unittest.TestCase):
    """Verifica mensajes claros para rechazos habituales de YouTube."""

    def test_translates_restrictions_and_rejections(self) -> None:
        cases = [
            ("Private video", "privado"),
            ("This video is age-restricted", "restricción de edad"),
            ("This video is not available in your country", "país o región"),
            ("Sign in to confirm you're not a bot", "no eres un bot"),
            ("HTTP Error 403: Forbidden", "rechazó la descarga"),
            ("Video unavailable", "no está disponible"),
        ]

        for technical_message, expected_text in cases:
            with self.subTest(technical_message=technical_message):
                friendly_message = _friendly_error_message(Exception(technical_message))
                self.assertIn(expected_text, friendly_message)


class FakeYoutubeDL:
    """Sustituto determinista que reproduce hooks y crea el MP3 esperado."""

    instances_created = 0
    extract_info_calls = 0
    last_options: dict | None = None

    def __init__(self, options: dict, cancel_check) -> None:
        type(self).instances_created += 1
        type(self).last_options = options
        self.options = options
        self.cancel_check = cancel_check
        output_directory = Path(options["outtmpl"]).parent
        self.original_path = output_directory / "Video de prueba.webm"
        codec = options["postprocessors"][0]["preferredcodec"]
        extension = {
            "mp3": "mp3",
            "m4a": "m4a",
            "opus": "opus",
            "wav": "wav",
            "flac": "flac",
            "vorbis": "ogg",
        }[codec]
        self.converted_path = self.original_path.with_suffix(f".{extension}")

    def __enter__(self) -> "FakeYoutubeDL":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def extract_info(self, _url: str, download: bool) -> dict:
        type(self).extract_info_calls += 1
        self.cancel_check()
        if not download:
            raise AssertionError("La prueba esperaba una descarga.")

        info = {
            "id": "dQw4w9WgXcQ",
            "title": "Video de prueba",
            "ext": "webm",
        }
        hook = self.options["progress_hooks"][0]
        hook(
            {
                "status": "downloading",
                "downloaded_bytes": 512,
                "total_bytes": 1024,
                "speed": 256.0,
                "eta": 2,
                "info_dict": info,
            }
        )
        hook(
            {
                "status": "finished",
                "downloaded_bytes": 1024,
                "total_bytes": 1024,
                "info_dict": info,
            }
        )
        self.options["postprocessor_hooks"][0]({"status": "started"})
        self.converted_path.write_bytes(b"Audio simulado")
        return info

    def prepare_filename(self, _info: dict) -> str:
        return str(self.original_path)


class FailingFFmpegYoutubeDL(FakeYoutubeDL):
    """Simula un fallo controlado durante la conversión."""

    def extract_info(self, _url: str, download: bool) -> dict:
        del download
        raise YtDlpDownloadError("FFmpeg conversion failed")


class DownloadFlowTests(unittest.TestCase):
    """Comprueba el flujo completo desde conexión hasta archivo final."""

    @patch("src.downloader.CancellableYoutubeDL", FakeYoutubeDL)
    def test_download_flow_creates_mp3_and_reports_all_stages(self) -> None:
        FakeYoutubeDL.instances_created = 0
        FakeYoutubeDL.extract_info_calls = 0
        FakeYoutubeDL.last_options = None

        with tempfile.TemporaryDirectory() as temporary_directory:
            statuses: list[str] = []
            progress_events: list[DownloadProgress] = []
            timing_metrics: list[TimingMetric] = []
            downloader = AudioDownloader(
                Path(temporary_directory),
                status_callback=statuses.append,
                progress_callback=progress_events.append,
                timing_callback=timing_metrics.append,
            )

            result = downloader.download_mp3(
                "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
            )

            self.assertTrue(result.is_file())
            self.assertEqual(result.suffix, ".mp3")
            self.assertEqual(result.name, "Video de prueba.mp3")
            self.assertNotIn("dQw4w9WgXcQ", result.name)
            self.assertEqual(FakeYoutubeDL.instances_created, 1)
            self.assertEqual(FakeYoutubeDL.extract_info_calls, 1)
            self.assertEqual(
                statuses,
                [
                    "Iniciando yt-dlp...",
                    "Conectando con YouTube...",
                    "Descargando audio...",
                    "Convirtiendo a MP3...",
                    "Guardando archivo MP3...",
                    "Descarga completada.",
                ],
            )
            self.assertEqual(
                [event.stage for event in progress_events],
                [
                    "connecting",
                    "downloading",
                    "converting",
                    "saving",
                    "completed",
                ],
            )
            self.assertEqual(progress_events[1].title, "Video de prueba")
            self.assertEqual(
                [metric.key for metric in timing_metrics],
                [
                    "yt_dlp_startup",
                    "connection",
                    "first_progress",
                    "download",
                    "conversion",
                ],
            )

            options = FakeYoutubeDL.last_options
            self.assertIsNotNone(options)
            assert options is not None
            self.assertEqual(options["format"], "bestaudio/best")
            self.assertTrue(options["noplaylist"])
            self.assertFalse(options["extract_flat"])
            self.assertFalse(options["ignoreerrors"])
            self.assertEqual(options["source_address"], "0.0.0.0")
            self.assertEqual(options["socket_timeout"], 20.0)
            self.assertTrue(options["windowsfilenames"])
            self.assertNotIn("match_filter", options)
            self.assertEqual(
                Path(options["outtmpl"]).name,
                "%(title).150B.%(ext)s",
            )
            self.assertTrue(
                Path(options["js_runtimes"]["deno"]["path"]).is_file()
            )
            for disabled_option in (
                "writethumbnail",
                "writedescription",
                "writeinfojson",
                "getcomments",
                "writesubtitles",
                "writeautomaticsub",
            ):
                self.assertFalse(options[disabled_option])

    @patch("src.downloader.CancellableYoutubeDL", FakeYoutubeDL)
    def test_duplicate_titles_receive_incrementing_suffixes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            downloader = AudioDownloader(Path(temporary_directory))
            results = [
                downloader.download_mp3(
                    "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
                )
                for _ in range(3)
            ]

            self.assertEqual(
                [result.name for result in results],
                [
                    "Video de prueba.mp3",
                    "Video de prueba (1).mp3",
                    "Video de prueba (2).mp3",
                ],
            )
            self.assertTrue(all(result.is_file() for result in results))
            self.assertFalse(
                any(
                    path.name.startswith(".kenji-")
                    for path in Path(temporary_directory).iterdir()
                )
            )

    @patch("src.downloader.CancellableYoutubeDL", FakeYoutubeDL)
    def test_all_supported_output_formats(self) -> None:
        for audio_format in AUDIO_FORMATS:
            with self.subTest(audio_format=audio_format.key):
                with tempfile.TemporaryDirectory() as temporary_directory:
                    statuses: list[str] = []
                    downloader = AudioDownloader(
                        Path(temporary_directory),
                        status_callback=statuses.append,
                        output_format=audio_format.key,
                    )

                    result = downloader.download_audio(
                        "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
                    )

                    self.assertEqual(result.suffix, f".{audio_format.extension}")
                    self.assertEqual(result.name, f"Video de prueba.{audio_format.extension}")
                    self.assertIn(
                        f"Convirtiendo a {audio_format.display_name}...",
                        statuses,
                    )
                    self.assertIn(
                        f"Guardando archivo {audio_format.display_name}...",
                        statuses,
                    )
                    options = FakeYoutubeDL.last_options
                    assert options is not None
                    self.assertEqual(
                        options["postprocessors"][0]["preferredcodec"],
                        audio_format.yt_dlp_codec,
                    )

    def test_rejects_unknown_output_format(self) -> None:
        with self.assertRaises(AudioDownloadError):
            AudioDownloader(Path("downloads"), output_format="exe")

    @patch("src.downloader.CancellableYoutubeDL", FailingFFmpegYoutubeDL)
    def test_ffmpeg_error_mentions_selected_format(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            downloader = AudioDownloader(
                Path(temporary_directory),
                output_format="flac",
            )

            with self.assertRaisesRegex(AudioDownloadError, "FLAC"):
                downloader.download_audio(
                    "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
                )


class DownloadCancellationTests(unittest.TestCase):
    """Comprueba la cancelación antes y durante el trabajo de yt-dlp."""

    def test_cancels_before_starting_youtube_dl(self) -> None:
        cancel_event = Event()
        cancel_event.set()
        downloader = AudioDownloader(Path("downloads"), cancel_event=cancel_event)

        with self.assertRaises(DownloadCancelledError):
            downloader.download_mp3(
                "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
            )

    def test_progress_hook_honors_cancellation(self) -> None:
        cancel_event = Event()
        downloader = AudioDownloader(Path("downloads"), cancel_event=cancel_event)
        cancel_event.set()

        with self.assertRaises(DownloadCancelledError):
            downloader._progress_hook({"status": "downloading"})



if __name__ == "__main__":
    unittest.main()
