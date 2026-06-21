"""Descarga y conversión de audio mediante la API de yt-dlp."""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
import shutil
import sys
from tempfile import TemporaryDirectory
from threading import Event
from time import perf_counter

import yt_dlp
from yt_dlp.utils import DownloadError as YtDlpDownloadError

from src.audio_formats import DEFAULT_AUDIO_FORMAT_KEY, AudioFormat, get_audio_format
from src.config import FORCE_IPV4, SOCKET_TIMEOUT_SECONDS


StatusCallback = Callable[[str], None]


@dataclass(frozen=True, slots=True)
class DownloadProgress:
    """Datos de progreso independientes de cualquier interfaz de usuario."""

    stage: str
    percentage: float | None = None
    downloaded_bytes: int | None = None
    total_bytes: int | None = None
    speed_bytes_per_second: float | None = None
    eta_seconds: int | None = None
    title: str | None = None


ProgressCallback = Callable[[DownloadProgress], None]


@dataclass(frozen=True, slots=True)
class TimingMetric:
    """Duración de una etapa interna, lista para consola o interfaz gráfica."""

    key: str
    label: str
    seconds: float


TimingCallback = Callable[[TimingMetric], None]


def _find_deno_executable() -> Path | None:
    """Localiza el runtime oficial sin aceptar rutas proporcionadas por el usuario."""
    executable_name = "deno.exe" if sys.platform == "win32" else "deno"
    candidates = [Path(sys.executable).resolve().parent / executable_name]

    bundle_directory = getattr(sys, "_MEIPASS", None)
    if bundle_directory:
        candidates.append(Path(bundle_directory) / executable_name)

    path_match = shutil.which("deno")
    if path_match:
        candidates.append(Path(path_match))

    return next((candidate for candidate in candidates if candidate.is_file()), None)


class AudioDownloadError(RuntimeError):
    """Error de descarga presentado al usuario sin detalles técnicos innecesarios."""


class DownloadCancelledError(RuntimeError):
    """Indica una cancelación solicitada por el usuario."""


class CancellableYoutubeDL(yt_dlp.YoutubeDL):
    """YoutubeDL que revisa una señal antes de iniciar cada petición HTTP."""

    def __init__(self, params: dict, cancel_check: Callable[[], None]) -> None:
        self._cancel_check = cancel_check
        super().__init__(params)

    def urlopen(self, request):
        self._cancel_check()
        return super().urlopen(request)


def _friendly_error_message(error: Exception) -> str:
    """Convierte errores frecuentes de yt-dlp en explicaciones sencillas."""
    message = str(error).lower()

    if "private video" in message or "video privado" in message:
        return "El video es privado y no se puede descargar."
    if any(text in message for text in ("age-restricted", "age restricted", "confirm your age")):
        return "El video tiene restricción de edad y YouTube exige iniciar sesión."
    if any(text in message for text in ("geo-restricted", "not available in your country")):
        return "El video está restringido en tu país o región."
    if "members-only" in message or "members only" in message:
        return "El video está restringido a miembros del canal."
    if "not a bot" in message or "automated requests" in message:
        return (
            "YouTube rechazó la descarga y solicita verificar que no eres un bot. "
            "Espera un momento e inténtalo nuevamente."
        )
    if "429" in message or "too many requests" in message:
        return "YouTube rechazó temporalmente la solicitud. Espera unos minutos."
    if "403" in message or "forbidden" in message:
        return "YouTube rechazó la descarga. Inténtalo más tarde o actualiza yt-dlp."
    if "video unavailable" in message or "video no disponible" in message:
        return "El video no está disponible o fue eliminado."
    if "this content isn't available" in message or "content is unavailable" in message:
        return "El contenido no está disponible para descargar."
    if "sign in" in message or "login" in message:
        return "YouTube requiere iniciar sesión para acceder a ese video."
    if "copyright" in message:
        return "El video no está disponible por una restricción de derechos de autor."
    if any(text in message for text in ("timed out", "timeout", "unable to download")):
        return "No se pudo conectar con YouTube. Revisa tu conexión a Internet."
    if "ffmpeg" in message:
        return "FFmpeg no pudo convertir el audio. Comprueba que esté bien instalado."

    return "No fue posible descargar el audio. Verifica que el video esté disponible."


class AudioDownloader:
    """Servicio reutilizable para descargar un video individual como MP3."""

    def __init__(
        self,
        output_directory: Path,
        status_callback: StatusCallback | None = None,
        progress_callback: ProgressCallback | None = None,
        timing_callback: TimingCallback | None = None,
        cancel_event: Event | None = None,
        force_ipv4: bool = FORCE_IPV4,
        socket_timeout: float = SOCKET_TIMEOUT_SECONDS,
        output_format: str = DEFAULT_AUDIO_FORMAT_KEY,
    ) -> None:
        self.output_directory = output_directory
        self.status_callback = status_callback
        self.progress_callback = progress_callback
        self.timing_callback = timing_callback
        self.cancel_event = cancel_event
        self.force_ipv4 = force_ipv4
        self.socket_timeout = max(1.0, float(socket_timeout))
        try:
            self.audio_format: AudioFormat = get_audio_format(output_format)
        except ValueError as error:
            raise AudioDownloadError(str(error)) from error
        self._last_status: str | None = None
        self._detected_title: str | None = None
        self._last_progress: DownloadProgress | None = None
        self._yt_dlp_started_at: float | None = None
        self._extract_started_at: float | None = None
        self._first_progress_at: float | None = None
        self._download_finished_at: float | None = None

    def _notify(self, message: str) -> None:
        """Envía cambios de estado a la consola o a una interfaz futura."""
        if self.status_callback and message != self._last_status:
            self.status_callback(message)
        self._last_status = message

    def _notify_progress(self, progress: DownloadProgress) -> None:
        """Entrega a la interfaz los valores crudos recibidos desde yt-dlp."""
        self._last_progress = progress
        if self.progress_callback:
            self.progress_callback(progress)

    def _report_timing(self, key: str, label: str, seconds: float) -> None:
        """Publica una medición para consola y para la interfaz gráfica."""
        metric = TimingMetric(key=key, label=label, seconds=max(0.0, seconds))
        print(f"[TIEMPO] {metric.label}: {metric.seconds:.2f}s", flush=True)
        if self.timing_callback:
            self.timing_callback(metric)

    def _check_cancelled(self) -> None:
        """Aborta cooperativamente cuando la interfaz activa la señal."""
        if self.cancel_event and self.cancel_event.is_set():
            raise DownloadCancelledError("La descarga fue cancelada por el usuario.")

    @staticmethod
    def _number(value: object) -> float | None:
        """Devuelve valores numéricos válidos e ignora datos inesperados del hook."""
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
        return None

    def _title_from_hook(self, data: dict) -> str | None:
        """Extrae y conserva el título del diccionario de información de yt-dlp."""
        info = data.get("info_dict")
        if isinstance(info, dict):
            title = info.get("title")
            if isinstance(title, str) and title.strip():
                self._detected_title = title.strip()
        return self._detected_title

    def _progress_hook(self, data: dict) -> None:
        """Recibe eventos de yt-dlp sin ejecutar código proporcionado por el usuario."""
        self._check_cancelled()
        status = data.get("status")
        title = self._title_from_hook(data)

        if status == "downloading":
            now = perf_counter()
            if self._first_progress_at is None:
                self._first_progress_at = now
                if self._extract_started_at is not None:
                    self._report_timing(
                        "connection",
                        "Conexión/obtención",
                        now - self._extract_started_at,
                    )
                if self._yt_dlp_started_at is not None:
                    self._report_timing(
                        "first_progress",
                        "Primer progreso recibido",
                        now - self._yt_dlp_started_at,
                    )

            self._notify("Descargando audio...")
            downloaded = self._number(data.get("downloaded_bytes")) or 0.0
            total = self._number(data.get("total_bytes")) or self._number(
                data.get("total_bytes_estimate")
            )
            speed = self._number(data.get("speed"))
            eta = self._number(data.get("eta"))
            percentage = None
            if total and total > 0:
                percentage = max(0.0, min(100.0, downloaded / total * 100))

            self._notify_progress(
                DownloadProgress(
                    stage="downloading",
                    percentage=percentage,
                    downloaded_bytes=int(downloaded),
                    total_bytes=int(total) if total is not None else None,
                    speed_bytes_per_second=speed,
                    eta_seconds=int(eta) if eta is not None else None,
                    title=title,
                )
            )

        elif status == "finished":
            now = perf_counter()
            if self._download_finished_at is None:
                self._download_finished_at = now
                if self._first_progress_at is not None:
                    self._report_timing(
                        "download",
                        "Descarga",
                        now - self._first_progress_at,
                    )

            previous = self._last_progress
            downloaded = self._number(data.get("downloaded_bytes"))
            if downloaded is None and previous and previous.downloaded_bytes is not None:
                downloaded = float(previous.downloaded_bytes)
            total = self._number(data.get("total_bytes"))
            if total is None and previous and previous.total_bytes is not None:
                total = float(previous.total_bytes)
            total = total or downloaded
            self._notify(f"Convirtiendo a {self.audio_format.display_name}...")
            self._notify_progress(
                DownloadProgress(
                    stage="converting",
                    downloaded_bytes=int(downloaded) if downloaded is not None else None,
                    total_bytes=int(total) if total is not None else None,
                    eta_seconds=0,
                    title=title,
                )
            )

    def _postprocessor_hook(self, _data: dict) -> None:
        """Evita iniciar una nueva etapa de FFmpeg después de cancelar."""
        self._check_cancelled()

    def _move_to_unique_output(self, source_path: Path) -> Path:
        """Mueve el audio sin sobrescribir y agrega un número solo si hace falta."""
        for number in range(10_000):
            suffix = "" if number == 0 else f" ({number})"
            candidate = self.output_directory / (
                f"{source_path.stem}{suffix}.{self.audio_format.extension}"
            )
            try:
                # Reserva atómicamente el nombre para evitar sobrescrituras accidentales.
                with candidate.open("xb"):
                    pass
            except FileExistsError:
                continue

            try:
                source_path.replace(candidate)
            except OSError:
                candidate.unlink(missing_ok=True)
                raise
            return candidate

        raise AudioDownloadError(
            "No se encontró un nombre disponible para guardar el archivo de audio."
        )

    def download_audio(self, safe_url: str) -> Path:
        """Descarga en un área temporal y guarda el formato seleccionado."""
        try:
            with TemporaryDirectory(
                prefix=".kenji-",
                dir=self.output_directory,
            ) as working_directory:
                return self._download_audio_in_directory(
                    safe_url,
                    Path(working_directory),
                )
        except (AudioDownloadError, DownloadCancelledError):
            raise
        except OSError as error:
            raise AudioDownloadError(
                "No se pudo escribir el archivo. Revisa los permisos y el espacio disponible."
            ) from error

    def download_mp3(self, safe_url: str) -> Path:
        """Mantiene compatibilidad con la versión anterior, cuyo valor es MP3."""
        return self.download_audio(safe_url)

    def _download_audio_in_directory(
        self,
        safe_url: str,
        working_directory: Path,
    ) -> Path:
        """Ejecuta yt-dlp una vez usando una plantilla basada solo en el título."""
        output_template = str(
            working_directory / "%(title).150B.%(ext)s"
        )
        postprocessor = {
            "key": "FFmpegExtractAudio",
            "preferredcodec": self.audio_format.yt_dlp_codec,
        }
        if self.audio_format.preferred_quality:
            postprocessor["preferredquality"] = self.audio_format.preferred_quality

        ydl_options = {
            "format": "bestaudio/best",
            "outtmpl": output_template,
            "noplaylist": True,
            "ignoreerrors": False,
            "extract_flat": False,
            # No se solicitan ni escriben recursos que la aplicación no utiliza.
            "writethumbnail": False,
            "writedescription": False,
            "writeinfojson": False,
            "getcomments": False,
            "writesubtitles": False,
            "writeautomaticsub": False,
            "windowsfilenames": True,
            "continuedl": True,
            "overwrites": False,
            "retries": 3,
            "fragment_retries": 3,
            "socket_timeout": self.socket_timeout,
            "quiet": True,
            "no_warnings": True,
            "progress_hooks": [self._progress_hook],
            "postprocessor_hooks": [self._postprocessor_hook],
            "postprocessors": [postprocessor],
        }

        if self.force_ipv4:
            # La API Python representa --force-ipv4 con esta dirección de enlace.
            ydl_options["source_address"] = "0.0.0.0"

        deno_executable = _find_deno_executable()
        if deno_executable:
            # yt-dlp usa Deno para resolver retos JavaScript modernos de YouTube.
            ydl_options["js_runtimes"] = {
                "deno": {"path": str(deno_executable)},
            }

        self._last_status = None
        self._detected_title = None
        self._last_progress = None
        self._extract_started_at = None
        self._first_progress_at = None
        self._download_finished_at = None
        self._yt_dlp_started_at = perf_counter()
        self._check_cancelled()
        self._notify("Iniciando yt-dlp...")
        try:
            # Se usa la API de Python: nunca se concatena la URL en un comando de shell.
            initialization_started_at = perf_counter()
            with CancellableYoutubeDL(ydl_options, self._check_cancelled) as ydl:
                self._report_timing(
                    "yt_dlp_startup",
                    "Inicio yt-dlp",
                    perf_counter() - initialization_started_at,
                )
                self._notify("Conectando con YouTube...")
                self._notify_progress(DownloadProgress(stage="connecting"))
                self._extract_started_at = perf_counter()
                self._check_cancelled()
                # Una sola extracción obtiene la información necesaria y descarga el audio.
                info = ydl.extract_info(safe_url, download=True)
                self._check_cancelled()
                extraction_finished_at = perf_counter()
                if self._download_finished_at is not None:
                    self._report_timing(
                        "conversion",
                        "Conversión",
                        extraction_finished_at - self._download_finished_at,
                    )
                if isinstance(info, dict):
                    title = info.get("title")
                    if isinstance(title, str) and title.strip():
                        self._detected_title = title.strip()
                original_path = Path(ydl.prepare_filename(info))
                converted_path = original_path.with_suffix(
                    f".{self.audio_format.extension}"
                )
        except DownloadCancelledError:
            raise
        except YtDlpDownloadError as error:
            if self.cancel_event and self.cancel_event.is_set():
                raise DownloadCancelledError(
                    "La descarga fue cancelada por el usuario."
                ) from error
            if "ffmpeg" in str(error).lower():
                raise AudioDownloadError(
                    f"FFmpeg no pudo convertir el audio a "
                    f"{self.audio_format.display_name}. Comprueba que FFmpeg esté "
                    "instalado correctamente."
                ) from error
            raise AudioDownloadError(_friendly_error_message(error)) from error
        except OSError as error:
            raise AudioDownloadError(
                "No se pudo escribir el archivo. Revisa los permisos y el espacio disponible."
            ) from error

        if not converted_path.is_file():
            raise AudioDownloadError(
                "La conversión terminó, pero no se encontró el archivo "
                f"{self.audio_format.display_name} resultante."
            )

        previous = self._last_progress
        self._notify(f"Guardando archivo {self.audio_format.display_name}...")
        self._notify_progress(
            DownloadProgress(
                stage="saving",
                percentage=100.0,
                downloaded_bytes=previous.downloaded_bytes if previous else None,
                total_bytes=previous.total_bytes if previous else None,
                eta_seconds=0,
                title=self._detected_title,
            )
        )
        final_path = self._move_to_unique_output(converted_path)

        self._notify("Descarga completada.")
        self._notify_progress(
            DownloadProgress(
                stage="completed",
                percentage=100.0,
                downloaded_bytes=previous.downloaded_bytes if previous else None,
                total_bytes=previous.total_bytes if previous else None,
                eta_seconds=0,
                title=self._detected_title,
            )
        )
        return final_path
