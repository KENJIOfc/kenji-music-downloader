"""Interfaz gráfica de Kenji Music Downloader construida con Tkinter."""

from pathlib import Path
import platform
import queue
import threading
from time import perf_counter
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import webbrowser

from src.audio_formats import (
    AUDIO_FORMATS,
    AUDIO_QUALITIES,
    AudioFormat,
    AudioQuality,
    get_audio_format,
    get_audio_format_from_label,
    get_audio_quality,
    get_audio_quality_from_label,
)
from src.diagnostics import ToolCheckResult, verify_tools
from src.download_history import (
    DownloadHistoryEntry,
    HistoryError,
    add_history_entry,
    clear_download_history,
    load_download_history,
    remove_history_entry,
)
from src.error_log import ErrorLogReadError, log_error, log_info, read_error_log
from src.config import (
    APP_DESCRIPTION,
    APP_NAME,
    APP_VERSION,
    DOWNLOADS_DIRECTORY,
    ConfigurationError,
    prepare_environment,
    prepare_output_directory,
)
from src.platform_utils import (
    OpenDirectoryError,
    OpenFileError,
    open_directory,
    open_file,
)
from src.downloader import (
    AudioDownloader,
    AudioDownloadError,
    DownloadCancelledError,
    DownloadProgress,
    TimingMetric,
)
from src.security import InvalidYouTubeURLError, validate_and_normalize_youtube_url
from src.tool_manager import (
    ToolInstallationError,
    install_ffmpeg_tools,
    missing_ffmpeg_tools,
)
from src.updates import GITHUB_RELEASES_URL, UpdateResult, check_for_updates
from src.update_manager import (
    DownloadedUpdate,
    UpdateCancelledError,
    UpdateDownloadError,
    UpdateDownloadProgress,
    UpdateInstallError,
    UpdatePackage,
    UpdatePackageError,
    consume_update_result,
    detect_installation_context,
    download_update,
    ensure_installation_writable,
    launch_update_installer,
    prepare_update_package,
    select_release_asset,
)
from src.user_settings import (
    DEFAULT_THEME,
    SettingsError,
    UserSettings,
    VALID_THEMES,
    load_user_settings,
    save_user_settings,
)


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
THEME_PALETTES = {
    "light": {
        "background": "#f4f6f9",
        "surface": "#ffffff",
        "foreground": "#1f2937",
        "muted": "#5f6b7a",
        "accent": "#2563eb",
        "selected": "#dbeafe",
        "border": "#cbd5e1",
    },
    "dark": {
        "background": "#171a21",
        "surface": "#232832",
        "foreground": "#f3f4f6",
        "muted": "#b8c0cc",
        "accent": "#60a5fa",
        "selected": "#334a68",
        "border": "#46505f",
    },
}
WINDOW_SIZES_BY_SYSTEM = {
    "Windows": ((1000, 720), (850, 600)),
    "Linux": ((920, 680), (820, 580)),
}
DEFAULT_WINDOW_SIZES = ((960, 700), (820, 580))
SCREEN_EDGE_MARGINS = (40, 80)
WINDOW_RESIZABLE = (False, False)
HISTORY_VISIBLE_ROWS = 3


def window_sizes_for_system(
    system_name: str | None = None,
) -> tuple[tuple[int, int], tuple[int, int]]:
    """Devuelve los tamaños inicial y mínimo adecuados para cada plataforma."""
    return WINDOW_SIZES_BY_SYSTEM.get(
        system_name or platform.system(),
        DEFAULT_WINDOW_SIZES,
    )


def fit_window_to_screen(
    initial_size: tuple[int, int],
    minimum_size: tuple[int, int],
    screen_size: tuple[int, int],
) -> tuple[tuple[int, int], tuple[int, int]]:
    """Ajusta la ventana a pantallas pequeñas sin ocultar controles importantes."""
    max_width = max(640, screen_size[0] - SCREEN_EDGE_MARGINS[0])
    max_height = max(480, screen_size[1] - SCREEN_EDGE_MARGINS[1])
    fitted_size = (
        min(initial_size[0], max_width),
        min(initial_size[1], max_height),
    )
    fitted_minimum = (
        min(minimum_size[0], fitted_size[0]),
        min(minimum_size[1], fitted_size[1]),
    )
    return fitted_size, fitted_minimum


INITIAL_WINDOW_SIZE, MINIMUM_WINDOW_SIZE = window_sizes_for_system()


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
        self.last_downloaded_path: Path | None = None
        self.active_audio_format: AudioFormat | None = None
        self.active_audio_quality: AudioQuality | None = None
        self.active_download_name = "Descarga sin título"
        self.tools_check_running = False
        self.tool_install_running = False
        self.update_check_running = False
        self.update_check_manual = False
        self.update_operation_running = False
        self.update_started_automatically = False
        self.update_cancel_event: threading.Event | None = None
        self.pending_update_result: UpdateResult | None = None
        self.pending_update_package: UpdatePackage | None = None
        self.downloaded_update: DownloadedUpdate | None = None
        self.update_dialog: tk.Toplevel | None = None
        self.update_installing = False
        self.style = ttk.Style(self.root)
        self.managed_menus: list[tk.Menu] = []
        self.history_item_entries: dict[str, DownloadHistoryEntry] = {}

        saved_settings = load_user_settings()
        saved_format = get_audio_format(saved_settings.output_format)
        saved_quality = get_audio_quality(saved_settings.audio_quality)

        self.url_value = tk.StringVar()
        saved_output_directory = saved_settings.output_directory
        try:
            saved_output_directory = str(
                prepare_output_directory(Path(saved_output_directory))
            )
        except ConfigurationError as error:
            # La ventana sigue abriendo y permite elegir otra carpeta.
            log_error("Carpeta de salida", str(error), error)

        self.output_value = tk.StringVar(value=saved_output_directory)
        self.format_value = tk.StringVar(value=saved_format.selector_label)
        self.quality_value = tk.StringVar(value=saved_quality.selector_label)
        self.theme_value = tk.StringVar(value=saved_settings.theme)
        self.auto_check_updates_value = tk.BooleanVar(
            value=saved_settings.auto_check_updates
        )
        self.auto_download_updates_value = tk.BooleanVar(
            value=saved_settings.auto_download_updates
        )
        self.allow_auto_install_updates_value = tk.BooleanVar(
            value=saved_settings.allow_auto_install_updates
        )
        self.update_dialog_status_value = tk.StringVar(value="")
        self.update_dialog_progress_value = tk.DoubleVar(value=0.0)
        self.status_value = tk.StringVar(value="Listo para descargar.")
        self.percentage_value = tk.StringVar(value="0 %")
        self.video_title_value = tk.StringVar(value="Esperando información...")
        self.size_value = tk.StringVar(value="0 B / —")
        self.speed_value = tk.StringVar(value="—")
        self.eta_value = tk.StringVar(value="—")
        self.timings_value = tk.StringVar(value="Esperando una descarga...")

        try:
            self.history_entries = load_download_history()
        except HistoryError as error:
            self.history_entries = []
            log_error("Historial", str(error), error)

        self._configure_window()
        self._build_widgets()
        self._build_menu()
        self._apply_theme(saved_settings.theme, save_preference=False)
        self._refresh_history_tree()
        self.root.after_idle(self._update_main_scroll_region)
        self.root.after(EVENT_POLL_INTERVAL_MS, self._process_events)
        self.root.after(
            CONNECTION_MONITOR_INTERVAL_MS,
            self._monitor_connection_delay,
        )
        self.root.after(1_500, self._start_startup_update_check)
        self.root.after(700, self._show_last_update_result)

    def _configure_window(self) -> None:
        """Configura tamaño, título y comportamiento general de la ventana."""
        initial_size, minimum_size = window_sizes_for_system()
        window_size, fitted_minimum = fit_window_to_screen(
            initial_size,
            minimum_size,
            (self.root.winfo_screenwidth(), self.root.winfo_screenheight()),
        )
        self.root.title(APP_NAME)
        self.root.geometry(f"{window_size[0]}x{window_size[1]}")
        self.root.minsize(*fitted_minimum)
        self.root.maxsize(*window_size)
        # Esto deshabilita maximizar y conserva minimizar/cerrar.
        self.root.resizable(*WINDOW_RESIZABLE)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_widgets(self) -> None:
        """Crea los controles usando únicamente componentes estándar de Tkinter."""
        scroll_host = ttk.Frame(self.root)
        scroll_host.pack(fill="both", expand=True)
        scroll_host.columnconfigure(0, weight=1)
        scroll_host.rowconfigure(0, weight=1)

        # El lienzo mantiene accesibles las secciones inferiores en pantallas bajas.
        self.main_canvas = tk.Canvas(
            scroll_host,
            borderwidth=0,
            highlightthickness=0,
        )
        self.main_canvas.grid(row=0, column=0, sticky="nsew")
        self.main_scrollbar = ttk.Scrollbar(
            scroll_host,
            orient="vertical",
            command=self.main_canvas.yview,
        )
        self.main_scrollbar.grid(row=0, column=1, sticky="ns")
        self.main_canvas.configure(yscrollcommand=self.main_scrollbar.set)

        container = ttk.Frame(self.main_canvas, padding=(14, 9, 14, 8))
        self.main_container = container
        self.main_canvas_window = self.main_canvas.create_window(
            (0, 0),
            window=container,
            anchor="nw",
        )
        container.bind("<Configure>", self._update_main_scroll_region, add="+")
        self.main_canvas.bind("<Configure>", self._resize_scroll_content, add="+")
        self.root.bind_all("<MouseWheel>", self._on_main_mousewheel, add="+")
        self.root.bind_all("<Button-4>", self._on_main_mousewheel, add="+")
        self.root.bind_all("<Button-5>", self._on_main_mousewheel, add="+")
        container.columnconfigure(0, weight=1)

        title = ttk.Label(
            container,
            text=APP_NAME,
            font=("TkDefaultFont", 17, "bold"),
        )
        title.grid(row=0, column=0, columnspan=3, sticky="w")

        subtitle = ttk.Label(
            container,
            text="Descarga el audio de un video individual de YouTube.",
        )
        subtitle.grid(row=1, column=0, columnspan=3, sticky="w", pady=(2, 8))

        ttk.Label(container, text="Enlace de YouTube:").grid(
            row=2, column=0, columnspan=3, sticky="w"
        )
        url_row = ttk.Frame(container)
        url_row.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(3, 8))
        url_row.columnconfigure(0, weight=1)
        self.url_entry = ttk.Entry(url_row, textvariable=self.url_value)
        self.url_entry.grid(row=0, column=0, sticky="ew")
        self.paste_button = ttk.Button(
            url_row,
            text="Pegar enlace",
            command=self._paste_link,
            width=14,
        )
        self.paste_button.grid(row=0, column=1, padx=(7, 0))
        self.clear_button = ttk.Button(
            url_row,
            text="Limpiar",
            command=self._clear_interface,
            width=12,
        )
        self.clear_button.grid(row=0, column=2, padx=(5, 0))

        ttk.Label(container, text="Carpeta de salida:").grid(
            row=4, column=0, columnspan=3, sticky="w"
        )
        self.output_entry = ttk.Entry(
            container,
            textvariable=self.output_value,
            state="readonly",
        )
        self.output_entry.grid(row=5, column=0, sticky="ew", pady=(3, 9))

        self.folder_button = ttk.Button(
            container,
            text="Elegir carpeta...",
            command=self._select_output_directory,
            width=16,
        )
        self.folder_button.grid(row=5, column=1, padx=(7, 0), pady=(3, 9))

        self.open_folder_button = ttk.Button(
            container,
            text="Abrir carpeta",
            command=self._open_output_directory,
            width=14,
        )
        self.open_folder_button.grid(row=5, column=2, padx=(5, 0), pady=(3, 9))

        selectors = ttk.Frame(container)
        selectors.grid(row=6, column=0, columnspan=3, sticky="ew", pady=(0, 9))
        selectors.columnconfigure(0, weight=1)
        selectors.columnconfigure(1, weight=1)
        ttk.Label(selectors, text="Formato de salida:").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(selectors, text="Calidad de audio:").grid(
            row=0, column=1, sticky="w", padx=(12, 0)
        )
        self.format_selector = ttk.Combobox(
            selectors,
            textvariable=self.format_value,
            values=[audio_format.selector_label for audio_format in AUDIO_FORMATS],
            state="readonly",
        )
        self.format_selector.grid(
            row=1,
            column=0,
            sticky="ew",
            pady=(3, 0),
        )
        self.quality_selector = ttk.Combobox(
            selectors,
            textvariable=self.quality_value,
            values=[quality.selector_label for quality in AUDIO_QUALITIES],
            state="readonly",
        )
        self.quality_selector.grid(
            row=1,
            column=1,
            sticky="ew",
            padx=(12, 0),
            pady=(3, 0),
        )
        self.format_selector.bind("<<ComboboxSelected>>", self._preference_changed)
        self.quality_selector.bind("<<ComboboxSelected>>", self._preference_changed)

        progress_row = ttk.Frame(container)
        progress_row.grid(row=7, column=0, columnspan=3, sticky="ew")
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

        details = ttk.LabelFrame(container, text="Detalles del proceso", padding=7)
        details.grid(row=8, column=0, columnspan=3, sticky="ew", pady=(8, 9))
        details.columnconfigure(1, weight=1)
        details.columnconfigure(3, weight=1)
        details.columnconfigure(5, weight=1)

        ttk.Label(details, text="Estado actual:").grid(row=0, column=0, sticky="nw")
        ttk.Label(details, textvariable=self.status_value, wraplength=560).grid(
            row=0, column=1, columnspan=5, sticky="w", padx=(8, 0)
        )

        ttk.Label(details, text="Video:").grid(row=1, column=0, sticky="nw", pady=(3, 0))
        ttk.Label(
            details,
            textvariable=self.video_title_value,
            wraplength=560,
        ).grid(row=1, column=1, columnspan=5, sticky="w", padx=(6, 0), pady=(3, 0))

        ttk.Label(details, text="Tamaño:").grid(row=2, column=0, sticky="w", pady=(4, 0))
        ttk.Label(details, textvariable=self.size_value).grid(
            row=2, column=1, sticky="w", padx=(6, 14), pady=(4, 0)
        )
        ttk.Label(details, text="Velocidad:").grid(row=2, column=2, sticky="w", pady=(4, 0))
        ttk.Label(details, textvariable=self.speed_value).grid(
            row=2, column=3, sticky="w", padx=(6, 14), pady=(4, 0)
        )
        ttk.Label(details, text="Tiempo restante:").grid(
            row=2, column=4, sticky="w", pady=(4, 0)
        )
        ttk.Label(details, textvariable=self.eta_value).grid(
            row=2, column=5, sticky="w", padx=(6, 0), pady=(4, 0)
        )

        ttk.Label(details, text="Tiempos:").grid(
            row=3, column=0, sticky="nw", pady=(4, 0)
        )
        ttk.Label(
            details,
            textvariable=self.timings_value,
            wraplength=580,
        ).grid(row=3, column=1, columnspan=5, sticky="w", padx=(6, 0), pady=(4, 0))

        history_frame = ttk.LabelFrame(
            container,
            text="Historial de descargas (últimas 20)",
            padding=6,
        )
        history_frame.grid(
            row=9,
            column=0,
            columnspan=3,
            sticky="ew",
            pady=(0, 8),
        )
        history_frame.columnconfigure(0, weight=1)
        history_frame.rowconfigure(0, weight=1)

        history_columns = ("name", "format", "quality", "status", "path")
        self.history_tree = ttk.Treeview(
            history_frame,
            columns=history_columns,
            show="headings",
            height=HISTORY_VISIBLE_ROWS,
        )
        history_headings = {
            "name": "Archivo / canción",
            "format": "Formato",
            "quality": "Calidad",
            "status": "Estado",
            "path": "Ruta",
        }
        history_widths = {
            "name": 280,
            "format": 80,
            "quality": 105,
            "status": 105,
            "path": 460,
        }
        for column in history_columns:
            self.history_tree.heading(column, text=history_headings[column])
            self.history_tree.column(
                column,
                width=history_widths[column],
                minwidth=65,
                stretch=False,
            )
        self.history_tree.grid(row=0, column=0, sticky="nsew")

        history_scroll = ttk.Scrollbar(
            history_frame,
            orient="vertical",
            command=self.history_tree.yview,
        )
        history_scroll.grid(row=0, column=1, sticky="ns")
        horizontal_scroll = ttk.Scrollbar(
            history_frame,
            orient="horizontal",
            command=self.history_tree.xview,
        )
        horizontal_scroll.grid(row=1, column=0, sticky="ew")
        self.history_tree.configure(
            yscrollcommand=history_scroll.set,
            xscrollcommand=horizontal_scroll.set,
        )
        self.history_tree.bind(
            "<<TreeviewSelect>>",
            self._history_selection_changed,
        )
        self.history_tree.bind("<Double-1>", self._history_double_click)
        self.history_tree.bind("<Button-3>", self._show_history_context_menu)

        history_actions = ttk.Frame(history_frame)
        history_actions.grid(row=2, column=0, columnspan=2, pady=(5, 0))

        ttk.Button(
            history_actions,
            text="Abrir seleccionado",
            command=self._open_selected_history_file,
            width=17,
        ).grid(row=0, column=0, padx=(0, 3))
        ttk.Button(
            history_actions,
            text="Abrir su carpeta",
            command=self._open_selected_history_folder,
            width=17,
        ).grid(row=0, column=1, padx=3)
        ttk.Button(
            history_actions,
            text="Copiar ruta",
            command=self._copy_selected_history_path,
            width=17,
        ).grid(row=0, column=2, padx=3)
        ttk.Button(
            history_actions,
            text="Eliminar entrada",
            command=self._delete_selected_history_entry,
            width=17,
        ).grid(row=0, column=3, padx=(3, 0))

        self.history_context_menu = tk.Menu(self.root, tearoff=False)
        self.history_context_menu.add_command(
            label="Abrir archivo",
            command=self._open_selected_history_file,
        )
        self.history_context_menu.add_command(
            label="Abrir carpeta",
            command=self._open_selected_history_folder,
        )
        self.history_context_menu.add_command(
            label="Copiar ruta",
            command=self._copy_selected_history_path,
        )
        self.history_context_menu.add_separator()
        self.history_context_menu.add_command(
            label="Eliminar entrada del historial",
            command=self._delete_selected_history_entry,
        )

        actions = ttk.Frame(container)
        actions.grid(row=10, column=0, columnspan=3, sticky="ew")
        actions.columnconfigure(0, weight=1)
        actions.columnconfigure(4, weight=1)

        self.download_button = ttk.Button(
            actions,
            text="Descargar audio",
            command=self._start_download,
            width=20,
        )
        self.download_button.grid(row=0, column=1)

        self.cancel_button = ttk.Button(
            actions,
            text="Cancelar",
            command=self._cancel_download,
            state="disabled",
            width=14,
        )
        self.cancel_button.grid(row=0, column=2, padx=(10, 0))

        self.open_file_button = ttk.Button(
            actions,
            text="Abrir archivo",
            command=self._open_last_downloaded_file,
            state="disabled",
            width=14,
        )
        self.open_file_button.grid(row=0, column=3, padx=(8, 0))

        ttk.Label(container, text=f"v{APP_VERSION}").grid(
            row=11,
            column=0,
            columnspan=3,
            pady=(7, 0),
        )
        self.url_entry.focus_set()

    def _update_main_scroll_region(self, _event: tk.Event | None = None) -> None:
        """Mantiene actualizado el recorrido vertical del contenido principal."""
        region = self.main_canvas.bbox("all")
        if region is not None:
            self.main_canvas.configure(scrollregion=region)

    def _resize_scroll_content(self, event: tk.Event) -> None:
        """Usa el ancho visible sin dejar que el contenido salga de la ventana."""
        self.main_canvas.itemconfigure(self.main_canvas_window, width=event.width)
        self._update_main_scroll_region()

    def _on_main_mousewheel(self, event: tk.Event) -> str | None:
        """Desplaza la interfaz con la rueda tanto en Windows como en Linux/X11."""
        try:
            if event.widget.winfo_toplevel() is not self.root:
                return None
            widget_class = event.widget.winfo_class()
        except (AttributeError, tk.TclError):
            return None

        # Treeview y Combobox conservan su desplazamiento nativo.
        if widget_class in {"Treeview", "TCombobox"}:
            return None

        if getattr(event, "num", None) == 4:
            direction = -1
        elif getattr(event, "num", None) == 5:
            direction = 1
        else:
            delta = getattr(event, "delta", 0)
            if not delta:
                return None
            direction = -1 if delta > 0 else 1

        self.main_canvas.yview_scroll(direction, "units")
        return "break"

    def _build_menu(self) -> None:
        """Crea un menú pequeño con acciones equivalentes a los botones."""
        menu_bar = tk.Menu(self.root)

        file_menu = tk.Menu(menu_bar, tearoff=False)
        file_menu.add_command(
            label="Abrir carpeta de salida",
            command=self._open_output_directory,
        )
        file_menu.add_separator()
        file_menu.add_command(label="Salir", command=self._on_close)
        menu_bar.add_cascade(label="Archivo", menu=file_menu)

        tools_menu = tk.Menu(menu_bar, tearoff=False)
        tools_menu.add_command(label="Limpiar", command=self._clear_interface)
        tools_menu.add_command(
            label="Limpiar historial",
            command=self._clear_history,
        )
        tools_menu.add_separator()
        tools_menu.add_command(
            label="Verificar herramientas",
            command=self._start_tools_check,
        )
        tools_menu.add_command(
            label="Instalar herramientas necesarias",
            command=self._start_tool_install,
        )
        tools_menu.add_separator()

        theme_menu = tk.Menu(tools_menu, tearoff=False)
        theme_menu.add_radiobutton(
            label="Claro",
            value="light",
            variable=self.theme_value,
            command=self._theme_changed,
        )
        theme_menu.add_radiobutton(
            label="Oscuro",
            value="dark",
            variable=self.theme_value,
            command=self._theme_changed,
        )
        tools_menu.add_cascade(label="Tema", menu=theme_menu)
        menu_bar.add_cascade(label="Herramientas", menu=tools_menu)

        help_menu = tk.Menu(menu_bar, tearoff=False)
        help_menu.add_command(
            label="Buscar actualizaciones...",
            command=self._start_manual_update_check,
        )
        help_menu.add_checkbutton(
            label="Buscar actualizaciones al iniciar",
            variable=self.auto_check_updates_value,
            command=self._startup_update_preference_changed,
        )
        help_menu.add_checkbutton(
            label="Descargar actualizaciones automáticamente",
            variable=self.auto_download_updates_value,
            command=self._startup_update_preference_changed,
        )
        help_menu.add_checkbutton(
            label="Permitir instalación automática",
            variable=self.allow_auto_install_updates_value,
            command=self._startup_update_preference_changed,
        )
        help_menu.add_command(
            label="Ver registro de errores",
            command=self._show_error_log,
        )
        help_menu.add_separator()
        help_menu.add_command(label="Acerca de", command=self._show_about)
        menu_bar.add_cascade(label="Ayuda", menu=help_menu)

        self.managed_menus = [
            menu_bar,
            file_menu,
            tools_menu,
            theme_menu,
            help_menu,
            self.history_context_menu,
        ]
        self.root.configure(menu=menu_bar)

    def _theme_changed(self) -> None:
        """Aplica y guarda el tema seleccionado desde el menú."""
        self._apply_theme(self.theme_value.get(), save_preference=True)

    def _apply_theme(self, theme: str, save_preference: bool) -> None:
        """Configura una paleta estable usando solamente estilos de ttk."""
        normalized_theme = theme if theme in VALID_THEMES else DEFAULT_THEME
        palette = THEME_PALETTES[normalized_theme]
        self.theme_value.set(normalized_theme)

        try:
            self.style.theme_use("clam")
        except tk.TclError:
            pass

        self.root.configure(background=palette["background"])
        self.main_canvas.configure(background=palette["background"])
        self.style.configure(
            ".",
            background=palette["background"],
            foreground=palette["foreground"],
        )
        self.style.configure(
            "TFrame",
            background=palette["background"],
        )
        self.style.configure(
            "TLabel",
            background=palette["background"],
            foreground=palette["foreground"],
        )
        self.style.configure(
            "TLabelframe",
            background=palette["background"],
            bordercolor=palette["border"],
        )
        self.style.configure(
            "TLabelframe.Label",
            background=palette["background"],
            foreground=palette["foreground"],
        )
        self.style.configure(
            "TButton",
            padding=(7, 3),
            background=palette["surface"],
            foreground=palette["foreground"],
        )
        self.style.map(
            "TButton",
            background=[("active", palette["selected"])],
            foreground=[("disabled", palette["muted"])],
        )
        self.style.configure(
            "TEntry",
            fieldbackground=palette["surface"],
            foreground=palette["foreground"],
            bordercolor=palette["border"],
        )
        self.style.configure(
            "TCombobox",
            fieldbackground=palette["surface"],
            background=palette["surface"],
            foreground=palette["foreground"],
            arrowcolor=palette["foreground"],
        )
        self.style.map(
            "TCombobox",
            fieldbackground=[("readonly", palette["surface"])],
            foreground=[("readonly", palette["foreground"])],
        )
        self.style.configure(
            "Treeview",
            background=palette["surface"],
            fieldbackground=palette["surface"],
            foreground=palette["foreground"],
            bordercolor=palette["border"],
            rowheight=22,
        )
        self.style.map(
            "Treeview",
            background=[("selected", palette["selected"])],
            foreground=[("selected", palette["foreground"])],
        )
        self.style.configure(
            "Treeview.Heading",
            background=palette["selected"],
            foreground=palette["foreground"],
            padding=(5, 3),
        )
        self.style.configure(
            "Horizontal.TProgressbar",
            background=palette["accent"],
            troughcolor=palette["surface"],
        )

        for menu in self.managed_menus:
            try:
                menu.configure(
                    background=palette["surface"],
                    foreground=palette["foreground"],
                    activebackground=palette["selected"],
                    activeforeground=palette["foreground"],
                )
            except tk.TclError:
                pass

        success_color = "#4ade80" if normalized_theme == "dark" else "#15803d"
        error_color = "#f87171" if normalized_theme == "dark" else "#dc2626"
        self.history_tree.tag_configure("completed", foreground=success_color)
        self.history_tree.tag_configure("cancelled", foreground=palette["muted"])
        self.history_tree.tag_configure("error", foreground=error_color)

        if save_preference:
            self._save_preferences(show_error=True)

    def _refresh_history_tree(self) -> None:
        """Sincroniza la tabla visible con el historial almacenado."""
        for item_id in self.history_tree.get_children():
            self.history_tree.delete(item_id)
        self.history_item_entries.clear()

        for index, entry in enumerate(self.history_entries):
            item_id = f"history-{index}"
            self.history_tree.insert(
                "",
                "end",
                iid=item_id,
                values=(
                    entry.name,
                    entry.output_format,
                    entry.quality,
                    entry.status_label,
                    entry.path or "—",
                ),
                tags=(entry.status,),
            )
            self.history_item_entries[item_id] = entry
        self._update_open_file_button_state()

    def _get_selected_history_entry(
        self,
        show_message: bool = True,
    ) -> DownloadHistoryEntry | None:
        """Obtiene la entrada real asociada a la fila seleccionada."""
        selected_items = self.history_tree.selection()
        entry = (
            self.history_item_entries.get(selected_items[0])
            if selected_items
            else None
        )
        if entry is None and show_message:
            messagebox.showinfo(
                "Historial",
                "Selecciona una descarga del historial.",
                parent=self.root,
            )
        return entry

    def _history_entry_file_path(
        self,
        entry: DownloadHistoryEntry,
    ) -> Path | None:
        """Valida que la ruta almacenada siga apuntando a un archivo real."""
        file_path = Path(entry.path).expanduser() if entry.path else None
        if file_path is None or not file_path.is_file():
            message = "El archivo ya no existe en la ruta guardada."
            log_error("Historial", message)
            messagebox.showerror("Archivo no disponible", message, parent=self.root)
            return None
        return file_path

    def _open_history_entry_file(self, entry: DownloadHistoryEntry) -> None:
        """Abre un archivo validado desde una entrada del historial."""
        file_path = self._history_entry_file_path(entry)
        if file_path is None:
            return
        try:
            open_file(file_path)
        except OpenFileError as error:
            log_error("Abrir archivo", str(error), error)
            messagebox.showerror(
                "No se pudo abrir el archivo",
                str(error),
                parent=self.root,
            )

    def _open_selected_history_file(self) -> None:
        """Abre la descarga elegida en la tabla."""
        entry = self._get_selected_history_entry()
        if entry is not None:
            self._open_history_entry_file(entry)

    def _open_selected_history_folder(self) -> None:
        """Abre la carpeta que contiene la descarga seleccionada."""
        entry = self._get_selected_history_entry()
        if entry is None:
            return
        file_path = self._history_entry_file_path(entry)
        if file_path is None:
            return
        try:
            open_directory(file_path.parent)
        except OpenDirectoryError as error:
            log_error("Abrir carpeta", str(error), error)
            messagebox.showerror(
                "No se pudo abrir la carpeta",
                str(error),
                parent=self.root,
            )

    def _copy_selected_history_path(self) -> None:
        """Copia al portapapeles la ruta completa de la descarga elegida."""
        entry = self._get_selected_history_entry()
        if entry is None:
            return
        file_path = self._history_entry_file_path(entry)
        if file_path is None:
            return
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(str(file_path.resolve()))
            self.root.update_idletasks()
        except tk.TclError as error:
            log_error("Portapapeles", "No se pudo copiar la ruta.", error)
            messagebox.showerror(
                "No se pudo copiar",
                "No se pudo copiar la ruta al portapapeles.",
                parent=self.root,
            )
            return

        messagebox.showinfo(
            "Ruta copiada",
            "La ruta completa se copió al portapapeles.",
            parent=self.root,
        )

    def _delete_selected_history_entry(self) -> None:
        """Borra solo la entrada seleccionada, nunca el archivo de audio."""
        entry = self._get_selected_history_entry()
        if entry is None:
            return
        if not messagebox.askyesno(
            "Eliminar entrada",
            "¿Eliminar esta entrada del historial? El archivo real se conservará.",
            parent=self.root,
        ):
            return

        try:
            self.history_entries = remove_history_entry(
                self.history_entries,
                entry,
            )
            self._refresh_history_tree()
        except HistoryError as error:
            log_error("Historial", str(error), error)
            messagebox.showerror("Historial", str(error), parent=self.root)

    def _history_selection_changed(self, _event: tk.Event | None = None) -> None:
        """Activa Abrir archivo cuando hay una fila utilizable seleccionada."""
        self._update_open_file_button_state()

    def _update_open_file_button_state(self) -> None:
        """Conserva disponible el botón si hay selección o una última descarga."""
        has_selection = bool(self.history_tree.selection())
        has_last_download = self.last_downloaded_path is not None
        self.open_file_button.configure(
            state="normal" if has_selection or has_last_download else "disabled"
        )

    def _history_double_click(self, event: tk.Event) -> str | None:
        """Abre con doble clic la fila situada bajo el puntero."""
        item_id = self.history_tree.identify_row(event.y)
        if not item_id:
            return None
        self.history_tree.selection_set(item_id)
        self.history_tree.focus(item_id)
        self._open_selected_history_file()
        return "break"

    def _show_history_context_menu(self, event: tk.Event) -> str | None:
        """Selecciona la fila bajo el cursor y muestra sus acciones."""
        item_id = self.history_tree.identify_row(event.y)
        if not item_id:
            return None
        self.history_tree.selection_set(item_id)
        self.history_tree.focus(item_id)
        try:
            self.history_context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.history_context_menu.grab_release()
        return "break"

    def _record_history(self, status: str, output_path: Path | None = None) -> None:
        """Añade el resultado actual al historial sin afectar la descarga."""
        audio_format = self.active_audio_format
        audio_quality = self.active_audio_quality
        if audio_format is None or audio_quality is None:
            return

        if output_path is not None:
            name = output_path.name
            path = str(output_path)
        else:
            name = self.active_download_name
            path = ""

        quality = (
            f"{audio_quality.bitrate_kbps} kbps"
            if audio_format.supports_bitrate
            else "Sin pérdida"
        )
        entry = DownloadHistoryEntry.create(
            name=name,
            output_format=audio_format.display_name,
            quality=quality,
            status=status,
            path=path,
        )
        try:
            self.history_entries = add_history_entry(self.history_entries, entry)
            self._refresh_history_tree()
        except HistoryError as error:
            log_error("Historial", str(error), error)

    def _clear_history(self) -> None:
        """Elimina solo el registro, nunca los archivos descargados."""
        if not self.history_entries:
            messagebox.showinfo(
                "Historial",
                "El historial ya está vacío.",
                parent=self.root,
            )
            return
        if not messagebox.askyesno(
            "Limpiar historial",
            "¿Quieres borrar el historial? Los archivos descargados se conservarán.",
            parent=self.root,
        ):
            return

        try:
            clear_download_history()
            self.history_entries = []
            self._refresh_history_tree()
        except HistoryError as error:
            log_error("Historial", str(error), error)
            messagebox.showerror("Historial", str(error), parent=self.root)

    def _open_last_downloaded_file(self) -> None:
        """Prioriza la fila seleccionada y usa después la última descarga."""
        selected_entry = self._get_selected_history_entry(show_message=False)
        if selected_entry is not None:
            self._open_history_entry_file(selected_entry)
            return

        if self.last_downloaded_path is None:
            messagebox.showinfo(
                "Abrir archivo",
                "No hay un archivo descargado disponible para abrir.",
                parent=self.root,
            )
            return
        if not self.last_downloaded_path.is_file():
            message = "El archivo ya no existe en la ruta guardada."
            log_error("Abrir archivo", message)
            self.last_downloaded_path = None
            self._update_open_file_button_state()
            messagebox.showerror(
                "Archivo no disponible",
                message,
                parent=self.root,
            )
            return
        try:
            open_file(self.last_downloaded_path)
        except OpenFileError as error:
            self.last_downloaded_path = None
            self._update_open_file_button_state()
            log_error("Abrir archivo", str(error), error)
            messagebox.showerror(
                "No se pudo abrir el archivo",
                str(error),
                parent=self.root,
            )

    def _start_tools_check(self) -> None:
        """Ejecuta la verificación en segundo plano para no congelar la ventana."""
        if self.tools_check_running or self.tool_install_running:
            return
        self.tools_check_running = True
        self.status_value.set("Verificando herramientas y conexión...")
        output_directory = Path(self.output_value.get().strip() or DOWNLOADS_DIRECTORY)

        worker = threading.Thread(
            target=self._tools_check_worker,
            args=(output_directory,),
            daemon=True,
        )
        worker.start()

    def _tools_check_worker(self, output_directory: Path) -> None:
        """Realiza el diagnóstico fuera del hilo principal de Tkinter."""
        try:
            results = verify_tools(output_directory)
        except Exception as error:
            log_error("Diagnóstico", "Falló la verificación de herramientas.", error)
            self.events.put(("tools_check_error", str(error)))
        else:
            self.events.put(("tools_check_result", results))

    def _show_tools_check(self, results: list[ToolCheckResult]) -> None:
        """Presenta todos los resultados en un único cuadro entendible."""
        self.tools_check_running = False
        self.status_value.set("Verificación de herramientas completada.")
        message = "\n".join(result.display_line() for result in results)
        for result in results:
            if not result.available:
                log_error(
                    "Verificación de herramientas",
                    f"{result.label}: {result.detail}",
                )
        if all(result.available for result in results):
            messagebox.showinfo("Verificar herramientas", message, parent=self.root)
            return

        missing_labels = {
            result.label for result in results if not result.available
        }
        missing_conversion_tools = missing_labels.intersection({"ffmpeg", "ffprobe"})
        if missing_conversion_tools:
            prompt = (
                f"{message}\n\n"
                "FFmpeg y FFprobe son necesarios para convertir audio a MP3, "
                "M4A, FLAC, OGG, WAV u OPUS.\n\n"
                "¿Quieres descargarlos e instalarlos automáticamente solo para "
                "esta aplicación?"
            )
            if messagebox.askyesno(
                "Herramientas necesarias",
                prompt,
                parent=self.root,
            ):
                self._start_tool_install(confirmed=True)
            return

        messagebox.showwarning("Verificar herramientas", message, parent=self.root)

    def _start_tool_install(self, confirmed: bool = False) -> None:
        """Solicita confirmación y arranca la instalación fuera del hilo gráfico."""
        if self.is_downloading:
            messagebox.showwarning(
                "Descarga en curso",
                "Espera a que termine o cancela la descarga antes de instalar herramientas.",
                parent=self.root,
            )
            return
        if self.tool_install_running:
            self.status_value.set("La instalación de herramientas ya está en curso...")
            return

        missing = missing_ffmpeg_tools()
        if not missing:
            messagebox.showinfo(
                "Herramientas necesarias",
                "Todas las herramientas necesarias ya están disponibles.",
                parent=self.root,
            )
            return

        if not confirmed:
            names = " y ".join(name.upper() for name in missing)
            confirmed = messagebox.askyesno(
                "Instalar herramientas necesarias",
                f"No se encontró {names}.\n\n"
                "¿Quieres descargar FFmpeg y FFprobe e instalarlos en la "
                "carpeta local de la aplicación?",
                parent=self.root,
            )
        if not confirmed:
            return

        self.tool_install_running = True
        self.download_button.configure(state="disabled")
        self.status_value.set("Descargando FFmpeg…")
        worker = threading.Thread(target=self._tool_install_worker, daemon=True)
        worker.start()

    def _tool_install_worker(self) -> None:
        """Descarga y extrae herramientas sin tocar widgets de Tkinter."""
        try:
            installed = install_ffmpeg_tools(
                status_callback=lambda text: self.events.put(
                    ("tool_install_status", text)
                )
            )
        except ToolInstallationError as error:
            self.events.put(("tool_install_error", str(error)))
        except Exception as error:
            log_error(
                "Instalación de herramientas",
                "Ocurrió un error inesperado durante la instalación.",
                error,
            )
            self.events.put(
                (
                    "tool_install_error",
                    "No se pudieron instalar las herramientas. Revisa el registro de errores.",
                )
            )
        else:
            self.events.put(("tool_install_success", installed))

    def _finish_tool_install(self, installed: dict[str, Path]) -> None:
        """Confirma la instalación y vuelve a comprobar las herramientas."""
        self.tool_install_running = False
        self.download_button.configure(state="normal")
        self.status_value.set("Instalación completada.")
        paths = "\n".join(f"{name}: {path}" for name, path in installed.items())
        messagebox.showinfo(
            "Herramientas instaladas",
            f"Herramientas instaladas correctamente.\n\n{paths}",
            parent=self.root,
        )
        self._start_tools_check()

    def _finish_tool_install_error(self, message: str) -> None:
        """Restaura la interfaz después de un fallo controlado."""
        self.tool_install_running = False
        self.download_button.configure(state="normal")
        self.status_value.set("No se pudieron instalar las herramientas.")
        messagebox.showerror(
            "Instalación de herramientas",
            message,
            parent=self.root,
        )

    def _show_error_log(self) -> None:
        """Muestra el registro dentro de la aplicación sin depender de un editor."""
        try:
            content = read_error_log()
        except ErrorLogReadError as error:
            log_error("Registro de errores", str(error), error)
            messagebox.showerror("Registro de errores", str(error), parent=self.root)
            return

        if not content:
            messagebox.showinfo(
                "Registro de errores",
                "No hay errores registrados.",
                parent=self.root,
            )
            return

        window = tk.Toplevel(self.root)
        window.title("Registro de errores")
        window.geometry("820x520")
        window.transient(self.root)

        palette = THEME_PALETTES[self.theme_value.get()]
        log_text = tk.Text(
            window,
            wrap="word",
            background=palette["surface"],
            foreground=palette["foreground"],
            insertbackground=palette["foreground"],
            padx=12,
            pady=12,
        )
        scrollbar = ttk.Scrollbar(window, command=log_text.yview)
        log_text.configure(yscrollcommand=scrollbar.set)
        log_text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        log_text.insert("1.0", content[-100_000:])
        log_text.configure(state="disabled")

    def _paste_link(self) -> None:
        """Pega texto desde el portapapeles sin ejecutar ni interpretar su contenido."""
        try:
            clipboard_text = self.root.clipboard_get().strip()
        except tk.TclError:
            clipboard_text = ""

        if not clipboard_text:
            messagebox.showwarning(
                "Portapapeles vacío",
                "El portapapeles está vacío o no contiene texto.",
                parent=self.root,
            )
            return

        self.url_value.set(clipboard_text)
        self.url_entry.icursor(tk.END)

    def _clear_interface(self) -> None:
        """Reinicia la descarga visible sin olvidar carpeta ni preferencias."""
        if self.is_downloading:
            messagebox.showwarning(
                "Descarga en curso",
                "Cancela la descarga antes de limpiar la interfaz.",
                parent=self.root,
            )
            return

        self.url_value.set("")
        self._show_progress(0.0)
        self.status_value.set("Listo para descargar.")
        self.video_title_value.set("Esperando información...")
        self.size_value.set("0 B / —")
        self.speed_value.set("—")
        self.eta_value.set("—")
        self.timings.clear()
        self.timings_value.set("Esperando una descarga...")
        self.current_stage = "idle"
        self.connection_started_at = None
        self.connection_warning_level = 0
        self.url_entry.focus_set()

    def _open_output_directory(self) -> None:
        """Abre la carpeta seleccionada usando la función propia del sistema."""
        output_text = self.output_value.get().strip()
        if not output_text:
            messagebox.showerror(
                "Carpeta no válida",
                "Selecciona una carpeta de salida.",
                parent=self.root,
            )
            return

        try:
            output_directory = prepare_output_directory(Path(output_text))
        except ConfigurationError as error:
            log_error("Carpeta de salida", str(error), error)
            if messagebox.askyesno(
                "Carpeta no válida",
                f"{error}\n\n¿Quieres seleccionar otra carpeta?",
                parent=self.root,
            ):
                self._select_output_directory()
            return

        self.output_value.set(str(output_directory))

        try:
            open_directory(output_directory)
        except (OSError, OpenDirectoryError) as error:
            log_error("Abrir carpeta", str(error), error)
            messagebox.showerror(
                "No se pudo abrir la carpeta",
                str(error),
                parent=self.root,
            )

    def _show_about(self) -> None:
        """Muestra los datos centralizados de nombre, versión y descripción."""
        messagebox.showinfo(
            "Acerca de",
            f"{APP_NAME}\nVersión {APP_VERSION}\n\n{APP_DESCRIPTION}",
            parent=self.root,
        )

    def _startup_update_preference_changed(self) -> None:
        """Guarda las preferencias de actualización sin iniciar una instalación."""
        self._save_preferences(show_error=True)

    def _start_startup_update_check(self) -> None:
        """Inicia silenciosamente la consulta automática si está habilitada."""
        if self.auto_check_updates_value.get():
            self._start_update_check(manual=False)

    def _start_manual_update_check(self) -> None:
        """Inicia una consulta solicitada desde el menú Ayuda."""
        self._start_update_check(manual=True)

    def _start_update_check(self, manual: bool) -> None:
        """Coordina una única consulta en segundo plano."""
        if self.update_check_running:
            if manual:
                self.update_check_manual = True
                self.status_value.set("Ya se están buscando actualizaciones...")
            return

        self.update_check_running = True
        self.update_check_manual = manual
        if manual:
            self.status_value.set("Buscando actualizaciones...")

        worker = threading.Thread(
            target=self._update_check_worker,
            daemon=True,
        )
        worker.start()

    def _update_check_worker(self) -> None:
        """Consulta GitHub sin acceder a widgets desde el hilo secundario."""
        log_info("Actualizaciones", f"Inicio de búsqueda desde v{APP_VERSION}.")
        try:
            result = check_for_updates(APP_VERSION)
        except Exception as error:
            log_error(
                "Actualizaciones",
                "Ocurrió un error inesperado durante la consulta.",
                error,
            )
            result = UpdateResult(
                success=False,
                update_available=False,
                current_version=APP_VERSION,
                error_type="unexpected_error",
                error_message="No se pudo comprobar si hay actualizaciones.",
            )
        if result.success:
            log_info(
                "Actualizaciones",
                f"Versión encontrada: v{result.latest_version}.",
            )
        self.events.put(("update_check_result", result))

    def _finish_update_check(self, result: UpdateResult) -> None:
        """Muestra el resultado en el hilo principal según el origen de la consulta."""
        manual = self.update_check_manual
        self.update_check_running = False
        self.update_check_manual = False

        if not result.success:
            if result.error_type != "no_releases":
                log_error(
                    "Actualizaciones",
                    f"{result.error_type}: {result.error_message}",
                )
            if manual:
                self.status_value.set("No se pudo comprobar la actualización.")
                self._show_update_error(result)
            return

        if result.update_available:
            self.status_value.set("Nueva versión disponible.")
            self._show_update_dialog(result)
            if not manual and self.auto_download_updates_value.get():
                self.root.after(
                    150,
                    lambda: self._begin_update_preparation(automatic=True),
                )
            return

        if manual:
            self.status_value.set("La aplicación está actualizada.")
            messagebox.showinfo(
                "Actualizaciones",
                "Ya tienes la versión más reciente instalada.\n\n"
                f"Versión actual: v{result.current_version}",
                parent=self.root,
            )

    def _show_update_dialog(self, result: UpdateResult) -> None:
        """Presenta versión, notas, tamaño y acciones sin bloquear la ventana."""
        if self.update_dialog and self.update_dialog.winfo_exists():
            self.update_dialog.lift()
            return

        self.pending_update_result = result
        self.pending_update_package = None
        self.downloaded_update = None
        self.update_dialog_status_value.set("Actualización disponible.")
        self.update_dialog_progress_value.set(0.0)

        dialog = tk.Toplevel(self.root)
        self.update_dialog = dialog
        dialog.title("Actualización disponible")
        dialog.geometry("620x470")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.protocol("WM_DELETE_WINDOW", self._close_update_dialog)

        container = ttk.Frame(dialog, padding=18)
        container.pack(fill="both", expand=True)
        ttk.Label(
            container,
            text="Hay una nueva versión disponible",
            font=("TkDefaultFont", 14, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            container,
            text=(
                f"Versión actual: v{result.current_version}\n"
                f"Nueva versión: v{result.latest_version}"
            ),
        ).pack(anchor="w", pady=(10, 6))

        size_text = "Tamaño: no disponible"
        try:
            _platform_key, asset, _kind = select_release_asset(result)
            if asset.size is not None:
                size_text = f"Tamaño: {format_bytes(asset.size)}"
        except UpdatePackageError:
            asset = None
        ttk.Label(container, text=size_text).pack(anchor="w", pady=(0, 8))
        ttk.Label(container, text="Notas de versión:").pack(anchor="w")

        palette = THEME_PALETTES[self.theme_value.get()]
        notes = tk.Text(
            container,
            height=10,
            wrap="word",
            background=palette["surface"],
            foreground=palette["foreground"],
            insertbackground=palette["foreground"],
            padx=8,
            pady=8,
        )
        notes.pack(fill="both", expand=True, pady=(4, 10))
        notes.insert("1.0", (result.release_notes or "Sin notas publicadas.")[:6_000])
        notes.configure(state="disabled")

        self.update_progress_bar = ttk.Progressbar(
            container,
            variable=self.update_dialog_progress_value,
            maximum=100,
            mode="determinate",
        )
        self.update_progress_bar.pack(fill="x")
        ttk.Label(
            container,
            textvariable=self.update_dialog_status_value,
            wraplength=580,
        ).pack(anchor="w", pady=(6, 10))

        buttons = ttk.Frame(container)
        buttons.pack(fill="x")
        self.update_install_button = ttk.Button(
            buttons,
            text="Descargar e instalar",
            command=lambda: self._begin_update_preparation(automatic=False),
            state="normal" if asset else "disabled",
        )
        self.update_install_button.pack(side="left")
        self.update_github_button = ttk.Button(
            buttons,
            text="Ver en GitHub",
            command=lambda: self._open_release_page(result.release_url),
        )
        self.update_github_button.pack(side="left", padx=8)
        self.update_cancel_button = ttk.Button(
            buttons,
            text="Cancelar",
            command=self._cancel_update_operation,
        )
        self.update_cancel_button.pack(side="right")

        if asset is None:
            self.update_dialog_status_value.set(
                "No hay paquete de actualización disponible para este sistema operativo."
            )

    def _close_update_dialog(self) -> None:
        """Cierra el diálogo o solicita cancelar una descarga activa."""
        if self.update_operation_running:
            self._cancel_update_operation()
            return
        if self.update_dialog and self.update_dialog.winfo_exists():
            self.update_dialog.destroy()
        self.update_dialog = None

    def _begin_update_preparation(self, automatic: bool = False) -> None:
        """Resuelve manifest y permisos en un hilo antes de descargar."""
        if self.update_operation_running or not self.pending_update_result:
            return
        self.update_started_automatically = automatic
        self.update_operation_running = True
        self.update_cancel_event = threading.Event()
        self.update_dialog_status_value.set("Preparando actualización…")
        self.update_progress_bar.configure(mode="indeterminate")
        self.update_progress_bar.start(12)
        self.update_install_button.configure(state="disabled")
        worker = threading.Thread(
            target=self._update_prepare_worker,
            args=(self.pending_update_result,),
            daemon=True,
        )
        worker.start()

    def _update_prepare_worker(self, result: UpdateResult) -> None:
        try:
            package = prepare_update_package(result)
            context = detect_installation_context()
            ensure_installation_writable(context)
        except (UpdatePackageError, UpdateInstallError) as error:
            self.events.put(("update_operation_error", str(error)))
        except Exception as error:
            log_error("Actualizaciones", "Falló la preparación.", error)
            self.events.put(
                (
                    "update_operation_error",
                    "No fue posible preparar la actualización automática.",
                )
            )
        else:
            self.events.put(("update_package_ready", package))

    def _finish_update_package_ready(self, package: UpdatePackage) -> None:
        """Pide confirmación extra cuando la release no publica SHA-256."""
        if self.update_cancel_event and self.update_cancel_event.is_set():
            self._finish_update_cancelled()
            return
        self.pending_update_package = package
        self.update_progress_bar.stop()
        self.update_progress_bar.configure(mode="determinate")
        if not package.expected_sha256:
            continue_without_hash = messagebox.askyesno(
                "Integridad no verificada",
                "La release no incluye un SHA-256 fuerte para este paquete.\n\n"
                "La descarga sigue limitada al repositorio oficial, pero no se puede "
                "comprobar su hash publicado. ¿Quieres continuar?",
                parent=self.update_dialog or self.root,
            )
            if not continue_without_hash:
                self._finish_update_cancelled()
                return
        self._start_update_download(package)

    def _start_update_download(self, package: UpdatePackage) -> None:
        self.update_dialog_status_value.set("Descargando actualización…")
        self.update_dialog_progress_value.set(0.0)
        worker = threading.Thread(
            target=self._update_download_worker,
            args=(package, self.update_cancel_event),
            daemon=True,
        )
        worker.start()

    def _update_download_worker(
        self,
        package: UpdatePackage,
        cancel_event: threading.Event | None,
    ) -> None:
        try:
            downloaded = download_update(
                package,
                progress_callback=lambda progress: self.events.put(
                    ("update_download_progress", progress)
                ),
                cancel_event=cancel_event,
            )
        except UpdateCancelledError:
            self.events.put(("update_operation_cancelled", None))
        except (UpdateDownloadError, UpdatePackageError) as error:
            self.events.put(("update_operation_error", str(error)))
        except Exception as error:
            log_error("Actualizaciones", "Falló la descarga.", error)
            self.events.put(
                (
                    "update_operation_error",
                    "No se pudo descargar la actualización.",
                )
            )
        else:
            self.events.put(("update_download_complete", downloaded))

    def _show_update_download_progress(self, progress: UpdateDownloadProgress) -> None:
        """Actualiza porcentaje y bytes exclusivamente desde el hilo principal."""
        if progress.percentage is None:
            self.update_progress_bar.configure(mode="indeterminate")
            self.update_progress_bar.start(12)
            percentage_text = ""
        else:
            self.update_progress_bar.stop()
            self.update_progress_bar.configure(mode="determinate")
            self.update_dialog_progress_value.set(progress.percentage)
            percentage_text = f" {progress.percentage:.0f}%"
        total = format_bytes(progress.total_bytes)
        self.update_dialog_status_value.set(
            f"Descargando actualización…{percentage_text} "
            f"({format_bytes(progress.downloaded_bytes)} / {total})"
        )

    def _finish_update_download(self, downloaded: DownloadedUpdate) -> None:
        """Conserva el paquete y nunca instala sin una confirmación visible."""
        self.downloaded_update = downloaded
        self.update_operation_running = False
        self.update_cancel_event = None
        self.update_progress_bar.stop()
        self.update_progress_bar.configure(mode="determinate")
        self.update_dialog_progress_value.set(100.0)
        verified_text = "SHA-256 verificado" if downloaded.hash_verified else "sin SHA-256 publicado"
        self.update_dialog_status_value.set(
            f"Actualización descargada correctamente ({verified_text})."
        )
        self.update_install_button.configure(
            text="Instalar actualización",
            command=self._confirm_install_downloaded_update,
            state="normal",
        )
        if (
            not self.update_started_automatically
            or self.allow_auto_install_updates_value.get()
        ):
            self._confirm_install_downloaded_update()

    def _confirm_install_downloaded_update(self) -> None:
        """La instalación siempre requiere esta confirmación final."""
        if not self.downloaded_update:
            return
        should_install = messagebox.askyesno(
            "Instalar actualización",
            "La actualización se descargó correctamente.\n\n"
            "La aplicación se cerrará y reiniciará para instalarla. "
            "¿Quieres continuar ahora?",
            parent=self.update_dialog or self.root,
        )
        if not should_install:
            self.update_dialog_status_value.set(
                "Actualización descargada. Puedes instalarla cuando estés listo."
            )
            return
        try:
            self._save_preferences(show_error=True)
            launch_update_installer(self.downloaded_update)
        except UpdateInstallError as error:
            log_error("Actualizaciones", str(error), error)
            messagebox.showerror(
                "No se pudo instalar",
                f"{error}\n\nPuedes usar Ver en GitHub como alternativa.",
                parent=self.update_dialog or self.root,
            )
            return
        self.update_installing = True
        self.status_value.set("Reiniciando para instalar la actualización…")
        self.root.after(150, self.root.destroy)

    def _cancel_update_operation(self) -> None:
        if self.update_operation_running and self.update_cancel_event:
            self.update_cancel_event.set()
            self.update_dialog_status_value.set("Cancelando actualización…")
            self.update_cancel_button.configure(state="disabled")
            return
        self._close_update_dialog()

    def _finish_update_cancelled(self) -> None:
        self.update_operation_running = False
        self.update_cancel_event = None
        self.update_progress_bar.stop()
        self.update_progress_bar.configure(mode="determinate")
        self.update_dialog_progress_value.set(0.0)
        self.update_dialog_status_value.set("La actualización fue cancelada.")
        self.update_install_button.configure(state="normal")
        self.update_cancel_button.configure(state="normal")

    def _finish_update_operation_error(self, message: str) -> None:
        self.update_operation_running = False
        self.update_cancel_event = None
        self.update_progress_bar.stop()
        self.update_progress_bar.configure(mode="determinate")
        self.update_dialog_progress_value.set(0.0)
        self.update_dialog_status_value.set(message)
        self.update_install_button.configure(state="normal")
        self.update_cancel_button.configure(state="normal")
        messagebox.showerror(
            "No se pudo actualizar",
            f"{message}\n\nPuedes usar Ver en GitHub como alternativa.",
            parent=self.update_dialog or self.root,
        )

    def _show_last_update_result(self) -> None:
        """Muestra el resultado escrito por el helper después del reinicio."""
        result = consume_update_result()
        if not result:
            return
        message = str(result.get("message", "Resultado de actualización desconocido."))
        if result.get("success") is True:
            messagebox.showinfo("Actualización completada", message, parent=self.root)
        else:
            messagebox.showerror("Actualización no completada", message, parent=self.root)

    def _show_update_error(self, result: UpdateResult) -> None:
        """Traduce errores de la API a mensajes breves para búsqueda manual."""
        if result.error_type == "no_releases":
            message = (
                "No se encontraron versiones publicadas en GitHub Releases.\n\n"
                "Crea una release en GitHub para que la aplicación pueda "
                "comprobar actualizaciones."
            )
        elif result.error_type in {"connection_error", "timeout", "ssl_error"}:
            message = (
                "No se pudo comprobar si hay actualizaciones.\n\n"
                "Revisa tu conexión a internet e inténtalo de nuevo."
            )
        elif result.error_type == "rate_limit":
            message = (
                "GitHub limitó temporalmente las consultas de actualizaciones.\n\n"
                "Espera unos minutos e inténtalo de nuevo."
            )
        elif result.error_type == "invalid_version":
            message = (
                "La versión publicada en GitHub no tiene un formato válido.\n\n"
                "Usa un tag como v1.0.1."
            )
        elif result.error_type == "missing_tag":
            message = "La release publicada en GitHub no contiene un tag_name válido."
        else:
            message = (
                "No se pudo leer correctamente la información de actualizaciones "
                "desde GitHub."
            )
        messagebox.showerror("Actualizaciones", message, parent=self.root)

    def _open_release_page(self, release_url: str) -> None:
        """Abre únicamente la página validada por el módulo de actualizaciones."""
        url = release_url or GITHUB_RELEASES_URL
        try:
            opened = webbrowser.open(url, new=2)
            if not opened:
                raise OSError("El sistema no confirmó la apertura del navegador.")
        except Exception as error:
            log_error("Actualizaciones", "No se pudo abrir GitHub Releases.", error)
            messagebox.showerror(
                "No se pudo abrir el navegador",
                "No se pudo abrir GitHub Releases en el navegador predeterminado.",
                parent=self.root,
            )

    def _preference_changed(self, _event: tk.Event | None = None) -> None:
        """Guarda automáticamente los selectores al cambiar su valor."""
        self._save_preferences()

    def _save_preferences(self, show_error: bool = False) -> None:
        """Persiste únicamente valores validados y nunca datos de la descarga."""
        try:
            audio_format = get_audio_format_from_label(self.format_value.get())
            audio_quality = get_audio_quality_from_label(self.quality_value.get())
            save_user_settings(
                UserSettings(
                    output_directory=self.output_value.get().strip()
                    or str(DOWNLOADS_DIRECTORY),
                    output_format=audio_format.key,
                    audio_quality=audio_quality.key,
                    theme=self.theme_value.get(),
                    auto_check_updates=self.auto_check_updates_value.get(),
                    auto_download_updates=self.auto_download_updates_value.get(),
                    allow_auto_install_updates=(
                        self.allow_auto_install_updates_value.get()
                    ),
                )
            )
        except (ValueError, SettingsError) as error:
            log_error("Configuración", str(error), error)
            if show_error:
                messagebox.showwarning(
                    "Configuración no guardada",
                    str(error),
                    parent=self.root,
                )

    def _select_output_directory(self) -> None:
        """Abre el selector nativo y conserva la ruta como un objeto portable."""
        selected = filedialog.askdirectory(
            title="Seleccionar carpeta de salida",
            initialdir=self.output_value.get(),
            mustexist=False,
        )
        if selected:
            self.output_value.set(str(Path(selected)))
            self._save_preferences(show_error=True)

    def _start_download(self) -> None:
        """Valida los datos antes de crear el hilo que hará el trabajo pesado."""
        raw_url = self.url_value.get().strip()
        if not raw_url:
            messagebox.showerror(
                "Enlace no válido",
                "Por favor ingresa un enlace válido de YouTube.",
                parent=self.root,
            )
            return

        operation_started_at = perf_counter()
        validation_started_at = operation_started_at
        try:
            safe_url = validate_and_normalize_youtube_url(raw_url)
        except InvalidYouTubeURLError:
            messagebox.showerror(
                "Enlace no válido",
                "Por favor ingresa un enlace válido de YouTube.",
                parent=self.root,
            )
            return
        validation_seconds = perf_counter() - validation_started_at

        output_text = self.output_value.get().strip()
        if not output_text:
            messagebox.showerror(
                "Carpeta no válida",
                "Selecciona una carpeta donde guardar el audio.",
                parent=self.root,
            )
            return

        try:
            output_directory = prepare_output_directory(Path(output_text))
        except ConfigurationError as error:
            log_error("Carpeta de salida", str(error), error)
            if messagebox.askyesno(
                "Carpeta no válida",
                f"{error}\n\n¿Quieres seleccionar otra carpeta?",
                parent=self.root,
            ):
                self._select_output_directory()
            return

        self.output_value.set(str(output_directory))

        missing_tools = missing_ffmpeg_tools()
        if missing_tools:
            names = " y ".join(name.upper() for name in missing_tools)
            if messagebox.askyesno(
                "Herramientas necesarias",
                f"No se encontró {names}. No se puede convertir el audio sin estas "
                "herramientas.\n\n¿Quieres instalarlas ahora?",
                parent=self.root,
            ):
                self._start_tool_install(confirmed=True)
            return

        try:
            audio_format = get_audio_format_from_label(self.format_value.get())
            audio_quality = get_audio_quality_from_label(self.quality_value.get())
        except ValueError as error:
            messagebox.showerror("Formato no válido", str(error), parent=self.root)
            return

        self._save_preferences(show_error=True)
        self.active_audio_format = audio_format
        self.active_audio_quality = audio_quality
        self.active_download_name = "Descarga sin título"

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
            safe_url,
            output_directory,
            audio_format.key,
            audio_quality.key,
            operation_started_at,
            validation_seconds,
            self.cancel_event,
        )

    def _launch_download_worker(
        self,
        safe_url: str,
        output_directory: Path,
        output_format: str,
        audio_quality: str,
        operation_started_at: float,
        validation_seconds: float,
        cancel_event: threading.Event,
    ) -> None:
        """Inicia el trabajo después de que la ventana haya actualizado su estado."""

        worker = threading.Thread(
            target=self._download_worker,
            args=(
                safe_url,
                output_directory,
                output_format,
                audio_quality,
                operation_started_at,
                validation_seconds,
                cancel_event,
            ),
            daemon=True,
        )
        worker.start()

    def _download_worker(
        self,
        safe_url: str,
        output_directory: Path,
        output_format: str,
        audio_quality: str,
        operation_started_at: float,
        validation_seconds: float,
        cancel_event: threading.Event,
    ) -> None:
        """Ejecuta yt-dlp fuera del hilo gráfico y comunica resultados por una cola."""
        try:
            if cancel_event.is_set():
                raise DownloadCancelledError("La descarga fue cancelada.")
            self._publish_local_timing(
                TimingMetric(
                    key="validation",
                    label="Validación",
                    seconds=validation_seconds,
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
                output_format=output_format,
                audio_quality=audio_quality,
            )
            output_path = downloader.download_audio(safe_url)
        except DownloadCancelledError:
            result_event: GuiEvent = ("cancelled", None)
        except ConfigurationError as error:
            log_error("Configuración", str(error), error)
            result_event = ("error", str(error))
        except AudioDownloadError as error:
            log_error("Descarga o conversión", str(error), error)
            result_event = ("error", str(error))
        except Exception as error:
            log_error("Error inesperado", "Falló el proceso de descarga.", error)
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
                elif event_name == "success":
                    self._finish_success(Path(value))
                elif event_name == "cancelled":
                    self._finish_cancelled()
                elif event_name == "error":
                    self._finish_error(str(value))
                elif event_name == "tools_check_result" and isinstance(value, list):
                    self._show_tools_check(value)
                elif event_name == "tools_check_error":
                    self.tools_check_running = False
                    self.status_value.set("No se pudo completar la verificación.")
                    messagebox.showerror(
                        "Verificar herramientas",
                        "No se pudo completar la verificación. Revisa el registro de errores.",
                        parent=self.root,
                    )
                elif event_name == "tool_install_status":
                    self.status_value.set(str(value))
                elif event_name == "tool_install_success" and isinstance(value, dict):
                    self._finish_tool_install(value)
                elif event_name == "tool_install_error":
                    self._finish_tool_install_error(str(value))
                elif event_name == "update_check_result" and isinstance(
                    value, UpdateResult
                ):
                    self._finish_update_check(value)
                elif event_name == "update_package_ready" and isinstance(
                    value, UpdatePackage
                ):
                    self._finish_update_package_ready(value)
                elif event_name == "update_download_progress" and isinstance(
                    value, UpdateDownloadProgress
                ):
                    self._show_update_download_progress(value)
                elif event_name == "update_download_complete" and isinstance(
                    value, DownloadedUpdate
                ):
                    self._finish_update_download(value)
                elif event_name == "update_operation_cancelled":
                    self._finish_update_cancelled()
                elif event_name == "update_operation_error":
                    self._finish_update_operation_error(str(value))
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
        if message.startswith("Convirtiendo a "):
            stage = "converting"
        elif message.startswith("Guardando archivo "):
            stage = "saving"
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
            self.active_download_name = progress.title

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
        self.last_downloaded_path = output_path
        self._record_history("completed", output_path)
        self._show_progress(100.0)
        self._clear_active_operation("completed")
        self.open_file_button.configure(state="normal")
        self.status_value.set("Descarga completada.")
        self.speed_value.set("—")
        self.eta_value.set("00:00")
        format_name = output_path.suffix.removeprefix(".").upper()
        messagebox.showinfo(
            "Descarga completada",
            f"El archivo {format_name} se guardó en:\n{output_path}",
            parent=self.root,
        )

    def _finish_error(
        self,
        message: str,
        dialog_title: str = "No se pudo descargar",
    ) -> None:
        """Restaura la ventana y presenta un error entendible."""
        self._record_history("error")
        self._show_progress(0.0)
        self._clear_active_operation("error")
        self.status_value.set(message)
        messagebox.showerror(dialog_title, message, parent=self.root)

    def _finish_cancelled(self) -> None:
        """Finaliza una cancelación cooperativa y permite iniciar otra descarga."""
        self._record_history("cancelled")
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
        self.paste_button.configure(state="disabled" if busy else "normal")
        self.clear_button.configure(state="disabled" if busy else "normal")
        self.url_entry.configure(state="disabled" if busy else "normal")
        self.format_selector.configure(state="disabled" if busy else "readonly")
        self.quality_selector.configure(state="disabled" if busy else "readonly")
        self.cancel_button.configure(
            state="normal" if busy and not self.cancel_requested else "disabled"
        )

    def _on_close(self) -> None:
        """Pide confirmación si el usuario intenta cerrar durante una descarga."""
        if self.update_installing:
            self.root.destroy()
            return
        if self.update_operation_running:
            messagebox.showwarning(
                "Actualización en curso",
                "Cancela la actualización y espera a que termine antes de cerrar.",
                parent=self.root,
            )
            return
        if self.tool_install_running:
            messagebox.showwarning(
                "Instalación en curso",
                "Espera a que termine la instalación de herramientas antes de cerrar.",
                parent=self.root,
            )
            return
        if self.is_downloading and not messagebox.askyesno(
            "Descarga en curso",
            "Hay una descarga en curso. ¿Quieres cerrar la aplicación?",
            parent=self.root,
        ):
            return
        if self.cancel_event:
            self.cancel_event.set()
        self._save_preferences()
        self.root.destroy()


def run() -> None:
    """Crea la ventana y entra en el bucle principal de Tkinter."""
    root = tk.Tk()
    KenjiMusicDownloaderGUI(root)
    root.mainloop()


if __name__ == "__main__":
    run()
