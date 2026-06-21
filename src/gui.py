"""Interfaz gráfica de Kenji Music Downloader construida con Tkinter."""

from pathlib import Path
import queue
import threading
from time import perf_counter
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from src.config import (
    APP_NAME,
    DOWNLOADS_DIRECTORY,
    ConfigurationError,
    prepare_environment,
)
from src.downloader import (
    AudioDownloader,
    AudioDownloadError,
    DownloadCancelledError,
    DownloadProgress,
    TimingMetric,
)
from src.security import InvalidYouTubeURLError, validate_and_normalize_youtube_url


GuiEvent = tuple[str, object]
EVENT_POLL_INTERVAL_MS = 50
CONNECTION_MONITOR_INTERVAL_MS = 1_000
SLOW_CONNECTION_WARNING_SECONDS = 30
VERY_SLOW_CONNECTION_WARNING_SECONDS = 90
TIMING_ORDER = (
    "validation",
    "yt_dlp_startup",
    "connection",
    "first_progress",
    "download",
    "conversion",
    "total",
)


def format_bytes(value: int | float | None) -> str:
    """Convierte bytes a una representación breve para la interfaz."""
    if value is None:
        return "—"

    size = max(0.0, float(value))
    units = ("B", "KB", "MB", "GB", "TB")
    for unit in units:
        if size < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{size:.0f} {unit}"
            return f"{size:.1f} {unit}"
        size /= 1024
    return "—"


def format_speed(value: float | None) -> str:
    """Formatea la velocidad entregada por yt-dlp."""
    return f"{format_bytes(value)}/s" if value is not None else "—"


def format_eta(seconds: int | None) -> str:
    """Convierte segundos restantes a MM:SS o HH:MM:SS."""
    if seconds is None or seconds < 0:
        return "—"

    hours, remainder = divmod(seconds, 3600)
    minutes, remaining_seconds = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{remaining_seconds:02d}"
    return f"{minutes:02d}:{remaining_seconds:02d}"


def connection_delay_notice(elapsed_seconds: float) -> tuple[int, str | None]:
    """Devuelve el nivel y mensaje correspondiente al tiempo de conexión."""
    if elapsed_seconds >= VERY_SLOW_CONNECTION_WARNING_SECONDS:
        return (
            2,
            "La obtención del video está tardando demasiado. "
            "Puedes cancelar e intentar de nuevo.",
        )
    if elapsed_seconds >= SLOW_CONNECTION_WARNING_SECONDS:
        return (
            1,
            "YouTube está tardando en responder…",
        )
    return 0, None


class KenjiMusicDownloaderGUI:
    """Ventana principal y coordinación segura con el hilo de descarga."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.events: queue.Queue[GuiEvent] = queue.Queue()
        self.is_downloading = False
        self.progress_is_indeterminate = False
        self.timings: dict[str, TimingMetric] = {}
        self.cancel_event: threading.Event | None = None
        self.cancel_requested = False
        self.current_stage = "idle"
        self.connection_started_at: float | None = None
        self.connection_warning_level = 0

        self.url_value = tk.StringVar()
        self.output_value = tk.StringVar(value=str(DOWNLOADS_DIRECTORY))
        self.status_value = tk.StringVar(value="Listo para descargar.")
        self.percentage_value = tk.StringVar(value="0 %")
        self.video_title_value = tk.StringVar(value="Esperando información...")
        self.size_value = tk.StringVar(value="0 B / —")
        self.speed_value = tk.StringVar(value="—")
        self.eta_value = tk.StringVar(value="—")
        self.timings_value = tk.StringVar(value="Esperando una descarga...")

        self._configure_window()
        self._build_widgets()
        self.root.after(EVENT_POLL_INTERVAL_MS, self._process_events)
        self.root.after(
            CONNECTION_MONITOR_INTERVAL_MS,
            self._monitor_connection_delay,
        )

    def _configure_window(self) -> None:
        """Configura tamaño, título y comportamiento general de la ventana."""
        self.root.title(APP_NAME)
        self.root.geometry("760x555")
        self.root.minsize(660, 510)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_widgets(self) -> None:
        """Crea los controles usando únicamente componentes estándar de Tkinter."""
        container = ttk.Frame(self.root, padding=24)
        container.grid(row=0, column=0, sticky="nsew")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        container.columnconfigure(0, weight=1)

        title = ttk.Label(
            container,
            text=APP_NAME,
            font=("TkDefaultFont", 18, "bold"),
        )
        title.grid(row=0, column=0, columnspan=2, sticky="w")

        subtitle = ttk.Label(
            container,
            text="Descarga el audio de un video individual de YouTube como MP3.",
        )
        subtitle.grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 20))

        ttk.Label(container, text="Enlace de YouTube:").grid(
            row=2, column=0, columnspan=2, sticky="w"
        )
        self.url_entry = ttk.Entry(container, textvariable=self.url_value)
        self.url_entry.grid(
            row=3, column=0, columnspan=2, sticky="ew", pady=(6, 16)
        )

        ttk.Label(container, text="Carpeta de salida:").grid(
            row=4, column=0, columnspan=2, sticky="w"
        )
        self.output_entry = ttk.Entry(
            container,
            textvariable=self.output_value,
            state="readonly",
        )
        self.output_entry.grid(row=5, column=0, sticky="ew", pady=(6, 18))

        self.folder_button = ttk.Button(
            container,
            text="Elegir carpeta...",
            command=self._select_output_directory,
        )
        self.folder_button.grid(row=5, column=1, padx=(10, 0), pady=(6, 18))

        progress_row = ttk.Frame(container)
        progress_row.grid(row=6, column=0, columnspan=2, sticky="ew")
        progress_row.columnconfigure(0, weight=1)
        self.progress_bar = ttk.Progressbar(
            progress_row,
            mode="determinate",
            maximum=100,
        )
        self.progress_bar.grid(row=0, column=0, sticky="ew")
        ttk.Label(progress_row, textvariable=self.percentage_value, width=7).grid(
            row=0, column=1, padx=(10, 0)
        )

        details = ttk.LabelFrame(container, text="Detalles del proceso", padding=12)
        details.grid(row=7, column=0, columnspan=2, sticky="ew", pady=(14, 18))
        details.columnconfigure(1, weight=1)
        details.columnconfigure(3, weight=1)
        details.columnconfigure(5, weight=1)

        ttk.Label(details, text="Estado actual:").grid(row=0, column=0, sticky="nw")
        ttk.Label(details, textvariable=self.status_value, wraplength=560).grid(
            row=0, column=1, columnspan=5, sticky="w", padx=(8, 0)
        )

        ttk.Label(details, text="Video:").grid(row=1, column=0, sticky="nw", pady=(8, 0))
        ttk.Label(
            details,
            textvariable=self.video_title_value,
            wraplength=560,
        ).grid(row=1, column=1, columnspan=5, sticky="w", padx=(8, 0), pady=(8, 0))

        ttk.Label(details, text="Tamaño:").grid(row=2, column=0, sticky="w", pady=(10, 0))
        ttk.Label(details, textvariable=self.size_value).grid(
            row=2, column=1, sticky="w", padx=(8, 18), pady=(10, 0)
        )
        ttk.Label(details, text="Velocidad:").grid(row=2, column=2, sticky="w", pady=(10, 0))
        ttk.Label(details, textvariable=self.speed_value).grid(
            row=2, column=3, sticky="w", padx=(8, 18), pady=(10, 0)
        )
        ttk.Label(details, text="Tiempo restante:").grid(
            row=2, column=4, sticky="w", pady=(10, 0)
        )
        ttk.Label(details, textvariable=self.eta_value).grid(
            row=2, column=5, sticky="w", padx=(8, 0), pady=(10, 0)
        )

        ttk.Label(details, text="Tiempos:").grid(
            row=3, column=0, sticky="nw", pady=(10, 0)
        )
        ttk.Label(
            details,
            textvariable=self.timings_value,
            wraplength=580,
        ).grid(row=3, column=1, columnspan=5, sticky="w", padx=(8, 0), pady=(10, 0))

        actions = ttk.Frame(container)
        actions.grid(row=8, column=0, columnspan=2, sticky="ew")
        actions.columnconfigure(0, weight=1)

        self.download_button = ttk.Button(
            actions,
            text="Descargar MP3",
            command=self._start_download,
        )
        self.download_button.grid(row=0, column=0, sticky="ew")

        self.cancel_button = ttk.Button(
            actions,
            text="Cancelar",
            command=self._cancel_download,
            state="disabled",
        )
        self.cancel_button.grid(row=0, column=1, padx=(10, 0))
        self.url_entry.focus_set()

    def _select_output_directory(self) -> None:
        """Abre el selector nativo y conserva la ruta como un objeto portable."""
        selected = filedialog.askdirectory(
            title="Seleccionar carpeta de salida",
            initialdir=self.output_value.get(),
            mustexist=False,
        )
        if selected:
            self.output_value.set(str(Path(selected)))

    def _start_download(self) -> None:
        """Valida los datos antes de crear el hilo que hará el trabajo pesado."""
        raw_url = self.url_value.get()
        output_text = self.output_value.get().strip()
        if not output_text:
            messagebox.showerror(
                "Carpeta no válida",
                "Selecciona una carpeta donde guardar el MP3.",
                parent=self.root,
            )
            return

        self.cancel_event = threading.Event()
        self.cancel_requested = False
        self.current_stage = "validating"
        self.connection_started_at = None
        self.connection_warning_level = 0
        self._set_busy(True)
        self._show_progress(0.0)
        self.video_title_value.set("Detectando título...")
        self.size_value.set("0 B / —")
        self.speed_value.set("—")
        self.eta_value.set("—")
        self.timings.clear()
        self.timings_value.set("Midiendo etapas...")
        self.status_value.set("Validando enlace...")

        # Dibuja el estado y arranca inmediatamente, sin una espera artificial.
        self.root.update_idletasks()
        self._launch_download_worker(
            raw_url,
            Path(output_text),
            perf_counter(),
            self.cancel_event,
        )

    def _launch_download_worker(
        self,
        raw_url: str,
        output_directory: Path,
        operation_started_at: float,
        cancel_event: threading.Event,
    ) -> None:
        """Inicia el trabajo después de que la ventana haya actualizado su estado."""

        worker = threading.Thread(
            target=self._download_worker,
            args=(raw_url, output_directory, operation_started_at, cancel_event),
            daemon=True,
        )
        worker.start()

    def _download_worker(
        self,
        raw_url: str,
        output_directory: Path,
        operation_started_at: float,
        cancel_event: threading.Event,
    ) -> None:
        """Ejecuta yt-dlp fuera del hilo gráfico y comunica resultados por una cola."""
        try:
            if cancel_event.is_set():
                raise DownloadCancelledError("La descarga fue cancelada.")
            validation_started_at = perf_counter()
            try:
                safe_url = validate_and_normalize_youtube_url(raw_url)
            finally:
                self._publish_local_timing(
                    TimingMetric(
                        key="validation",
                        label="Validación",
                        seconds=perf_counter() - validation_started_at,
                    )
                )

            if cancel_event.is_set():
                raise DownloadCancelledError("La descarga fue cancelada.")
            prepared_directory = prepare_environment(output_directory)
            downloader = AudioDownloader(
                prepared_directory,
                status_callback=lambda text: self.events.put(("status", text)),
                progress_callback=lambda value: self.events.put(("progress", value)),
                timing_callback=lambda metric: self.events.put(("timing", metric)),
                cancel_event=cancel_event,
            )
            output_path = downloader.download_mp3(safe_url)
        except DownloadCancelledError:
            result_event: GuiEvent = ("cancelled", None)
        except InvalidYouTubeURLError as error:
            result_event = ("validation_error", str(error))
        except (ConfigurationError, AudioDownloadError) as error:
            result_event = ("error", str(error))
        except Exception:
            # No se muestra una traza técnica al usuario final.
            result_event = (
                "error",
                "Ocurrió un error inesperado. Reinicia la aplicación e inténtalo de nuevo.",
            )
        else:
            result_event = ("success", output_path)

        self._publish_local_timing(
            TimingMetric(
                key="total",
                label="Total",
                seconds=perf_counter() - operation_started_at,
            )
        )
        self.events.put(result_event)

    def _publish_local_timing(self, metric: TimingMetric) -> None:
        """Imprime mediciones de GUI y las envía al hilo principal."""
        print(f"[TIEMPO] {metric.label}: {metric.seconds:.2f}s", flush=True)
        self.events.put(("timing", metric))

    def _process_events(self) -> None:
        """Procesa en el hilo gráfico los eventos producidos por la descarga."""
        try:
            while True:
                event_name, value = self.events.get_nowait()
                if self.cancel_requested and event_name in {"status", "progress"}:
                    continue
                if event_name == "status":
                    self._show_status(str(value))
                elif event_name == "progress" and isinstance(value, DownloadProgress):
                    self._show_download_progress(value)
                elif event_name == "timing" and isinstance(value, TimingMetric):
                    self._show_timing(value)
                elif event_name == "validation_error":
                    self._finish_error(str(value), "Enlace no válido")
                elif event_name == "success":
                    self._finish_success(Path(value))
                elif event_name == "cancelled":
                    self._finish_cancelled()
                elif event_name == "error":
                    self._finish_error(str(value))
        except queue.Empty:
            pass

        self.root.after(EVENT_POLL_INTERVAL_MS, self._process_events)

    def _show_status(self, message: str) -> None:
        """Actualiza el texto y registra el inicio de la conexión lenta."""
        self.status_value.set(message)
        stages = {
            "Iniciando yt-dlp...": "starting",
            "Conectando con YouTube...": "connecting",
            "Descargando audio...": "downloading",
            "Convirtiendo a MP3...": "converting",
            "Guardando archivo...": "saving",
            "Descarga completada.": "completed",
        }
        stage = stages.get(message)
        if stage:
            self.current_stage = stage
        if stage == "connecting" and self.connection_started_at is None:
            self.connection_started_at = perf_counter()

    def _monitor_connection_delay(self) -> None:
        """Muestra avisos no modales mientras el extractor espera a YouTube."""
        if (
            self.is_downloading
            and not self.cancel_requested
            and self.current_stage == "connecting"
            and self.connection_started_at is not None
        ):
            elapsed = perf_counter() - self.connection_started_at
            warning_level, message = connection_delay_notice(elapsed)
            if warning_level > self.connection_warning_level and message:
                self.status_value.set(message)
                self.connection_warning_level = warning_level

        self.root.after(
            CONNECTION_MONITOR_INTERVAL_MS,
            self._monitor_connection_delay,
        )

    def _show_timing(self, metric: TimingMetric) -> None:
        """Conserva y presenta un resumen compacto de las etapas medidas."""
        self.timings[metric.key] = metric
        parts = [
            f"{self.timings[key].label}: {self.timings[key].seconds:.2f}s"
            for key in TIMING_ORDER
            if key in self.timings
        ]
        self.timings_value.set(" · ".join(parts))

    def _show_download_progress(self, progress: DownloadProgress) -> None:
        """Actualiza todos los detalles usando un solo evento coherente del hook."""
        self.current_stage = progress.stage
        if progress.stage == "connecting" and self.connection_started_at is None:
            self.connection_started_at = perf_counter()
        self._show_progress(progress.percentage)

        if progress.title:
            self.video_title_value.set(progress.title)

        if progress.downloaded_bytes is not None:
            downloaded = format_bytes(progress.downloaded_bytes)
            total = format_bytes(progress.total_bytes)
            self.size_value.set(f"{downloaded} / {total}")

        self.speed_value.set(format_speed(progress.speed_bytes_per_second))
        self.eta_value.set(format_eta(progress.eta_seconds))

    def _show_progress(self, percentage: float | None) -> None:
        """Alterna entre porcentaje real y animación cuando el total es desconocido."""
        if percentage is None:
            if not self.progress_is_indeterminate:
                self.progress_bar.stop()
                self.progress_bar.configure(mode="indeterminate")
                self.progress_bar.start(12)
                self.progress_is_indeterminate = True
            self.percentage_value.set("—")
            return

        if self.progress_is_indeterminate:
            self.progress_bar.stop()
            self.progress_bar.configure(mode="determinate")
            self.progress_is_indeterminate = False

        bounded_percentage = max(0.0, min(100.0, percentage))
        self.progress_bar["value"] = bounded_percentage
        self.percentage_value.set(f"{bounded_percentage:.0f} %")

    def _finish_success(self, output_path: Path) -> None:
        """Restaura la ventana e informa dónde quedó el MP3."""
        self._show_progress(100.0)
        self._clear_active_operation("completed")
        self.status_value.set("Descarga completada.")
        self.speed_value.set("—")
        self.eta_value.set("00:00")
        messagebox.showinfo(
            "Descarga completada",
            f"El MP3 se guardó en:\n{output_path}",
            parent=self.root,
        )

    def _finish_error(
        self,
        message: str,
        dialog_title: str = "No se pudo descargar",
    ) -> None:
        """Restaura la ventana y presenta un error entendible."""
        self._show_progress(0.0)
        self._clear_active_operation("error")
        self.status_value.set(message)
        messagebox.showerror(dialog_title, message, parent=self.root)

    def _finish_cancelled(self) -> None:
        """Finaliza una cancelación cooperativa y permite iniciar otra descarga."""
        self._show_progress(0.0)
        self._clear_active_operation("cancelled")
        self.status_value.set("Operación cancelada.")
        self.speed_value.set("—")
        self.eta_value.set("—")
        messagebox.showinfo(
            "Operación cancelada",
            "La descarga fue cancelada.",
            parent=self.root,
        )

    def _cancel_download(self) -> None:
        """Solicita al hilo que detenga yt-dlp en el siguiente punto seguro."""
        if not self.is_downloading or not self.cancel_event:
            return
        self.cancel_requested = True
        self.current_stage = "cancelling"
        self.cancel_event.set()
        self.cancel_button.configure(state="disabled")
        self.status_value.set(
            "Cancelando... La petición actual puede tardar unos segundos en cerrarse."
        )

    def _clear_active_operation(self, final_stage: str) -> None:
        """Limpia señales internas sin modificar la carpeta seleccionada."""
        self.current_stage = final_stage
        self.connection_started_at = None
        self.connection_warning_level = 0
        self.cancel_event = None
        self.cancel_requested = False
        self._set_busy(False)

    def _set_busy(self, busy: bool) -> None:
        """Evita descargas simultáneas y cambios de datos durante una descarga."""
        self.is_downloading = busy
        self.download_button.configure(state="disabled" if busy else "normal")
        self.folder_button.configure(state="disabled" if busy else "normal")
        self.url_entry.configure(state="disabled" if busy else "normal")
        self.cancel_button.configure(
            state="normal" if busy and not self.cancel_requested else "disabled"
        )

    def _on_close(self) -> None:
        """Pide confirmación si el usuario intenta cerrar durante una descarga."""
        if self.is_downloading and not messagebox.askyesno(
            "Descarga en curso",
            "Hay una descarga en curso. ¿Quieres cerrar la aplicación?",
            parent=self.root,
        ):
            return
        if self.cancel_event:
            self.cancel_event.set()
        self.root.destroy()


def run() -> None:
    """Crea la ventana y entra en el bucle principal de Tkinter."""
    root = tk.Tk()
    KenjiMusicDownloaderGUI(root)
    root.mainloop()


if __name__ == "__main__":
    run()
