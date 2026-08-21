"""Interfaz gráfica de Yūgen Audio construida con Tkinter."""

import os
from pathlib import Path
import platform
import queue
import re
import shutil
import sys
import threading
from time import perf_counter


def _get_tcl_tk_cache_directory() -> Path:
    if not getattr(sys, "frozen", False):
        return (
            Path(__file__).resolve().parent.parent
            / "build"
            / "tcl_tk_runtime_cache"
        )
    if os.name == "nt":
        base = Path(
            os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")
        )
        return base / "YugenAudio" / "tcl-tk-runtime"
    base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return base / "yugen-audio" / "tcl-tk-runtime"


def _patch_tcl_tk_scripts(tcl_root: Path) -> None:
    replacements = (
        (tcl_root / "tcl8.6" / "init.tcl", r"package require -exact Tcl\s+8\.6\.12", "package require Tcl 8.6"),
        (tcl_root / "tk8.6" / "tk.tcl", r"package require -exact Tk\s+8\.6\.12", "package require Tk 8.6"),
    )
    for script_path, pattern, replacement in replacements:
        text = script_path.read_text(encoding="utf-8")
        script_path.write_text(
            re.sub(pattern, replacement, text),
            encoding="utf-8",
        )


def _compatible_tcl_tk_root(source_root: Path) -> Path:
    init_script = source_root / "tcl8.6" / "init.tcl"
    tk_script = source_root / "tk8.6" / "tk.tcl"
    try:
        needs_patch = (
            "package require -exact Tcl" in init_script.read_text(encoding="utf-8")
            or "package require -exact Tk" in tk_script.read_text(encoding="utf-8")
        )
    except OSError:
        return source_root
    if not needs_patch:
        return source_root

    cache_directory = _get_tcl_tk_cache_directory()
    cached_root = cache_directory / "tcl"
    marker_path = cache_directory / "source.txt"
    source_marker = str(source_root.resolve())
    try:
        marker_matches = (
            marker_path.is_file()
            and marker_path.read_text(encoding="utf-8") == source_marker
        )
        cache_is_ready = (
            (cached_root / "tcl8.6" / "init.tcl").is_file()
            and (cached_root / "tk8.6" / "tk.tcl").is_file()
            and marker_matches
        )
        if not cache_is_ready:
            if cache_directory.exists():
                shutil.rmtree(cache_directory)
            cache_directory.mkdir(parents=True, exist_ok=True)
            shutil.copytree(source_root, cached_root)
            _patch_tcl_tk_scripts(cached_root)
            marker_path.write_text(source_marker, encoding="utf-8")
    except OSError:
        return source_root
    return cached_root


def _configure_tcl_tk_environment() -> None:
    """Ayuda a Tkinter cuando Python o PyInstaller no ubican Tcl/Tk solos."""
    candidate_roots = []
    bundled_directory = getattr(sys, "_MEIPASS", None)
    if bundled_directory:
        candidate_roots.append(Path(bundled_directory) / "tcl")
        candidate_roots.append(
            Path(sys.executable).resolve().parent / "_internal" / "tcl"
        )
    candidate_roots.extend(
        (
            Path(getattr(sys, "base_prefix", sys.prefix)) / "tcl",
            Path(sys.prefix) / "tcl",
        )
    )

    for root in candidate_roots:
        tcl_directory = root / "tcl8.6"
        tk_directory = root / "tk8.6"
        if (tcl_directory / "init.tcl").is_file() and (
            tk_directory / "tk.tcl"
        ).is_file():
            compatible_root = _compatible_tcl_tk_root(root)
            os.environ["TCL_LIBRARY"] = str(compatible_root / "tcl8.6")
            os.environ["TK_LIBRARY"] = str(compatible_root / "tk8.6")
            return


_configure_tcl_tk_environment()

import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog, messagebox, ttk
import webbrowser

try:
    from PIL import Image, ImageTk
except ImportError:  # pragma: no cover - fallback para entornos sin Pillow.
    Image = None
    ImageTk = None

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
from src.error_log import (
    ErrorLogClearError,
    ErrorLogReadError,
    clear_internal_logs,
    log_error,
    log_info,
    read_error_log,
)
from src.config import (
    APP_DESCRIPTION,
    APP_FULL_NAME,
    APP_NAME,
    APP_TAGLINE,
    APP_VERSION,
    DOWNLOADS_DIRECTORY,
    SUPPORT_DISCORD_URL,
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
        "background": "#eaf5ff",
        "surface": "#f8fbff",
        "panel": "#edf8ff",
        "panel_alt": "#dff2ff",
        "foreground": "#0b1f33",
        "muted": "#456179",
        "accent": "#0078d4",
        "accent_2": "#00b7ff",
        "selected": "#cceeff",
        "border": "#7bcfff",
        "glow": "#00a8ff",
        "success": "#128a38",
        "error": "#cc2444",
        "warning": "#c77700",
    },
    "dark": {
        "background": "#050B16",
        "surface": "#081321",
        "panel": "#0A1625",
        "panel_alt": "#0E1C2E",
        "foreground": "#F2F6FF",
        "muted": "#AAB8CB",
        "accent": "#00CFFF",
        "accent_2": "#168BFF",
        "selected": "#0B2742",
        "border": "#162A40",
        "glow": "#34E7FF",
        "success": "#20C77A",
        "error": "#FF5D6C",
        "warning": "#FFD166",
    },
}
NEON_PANEL_STYLE = "Neon.TLabelframe"
NEON_PANEL_LABEL_STYLE = "Neon.TLabelframe.Label"
NEON_SECTION_LABEL_STYLE = "SectionTitle.TLabel"
NEON_TITLE_STYLE = "BrandTitle.TLabel"
NEON_SUBTITLE_STYLE = "BrandSubtitle.TLabel"
NEON_MUTED_STYLE = "Muted.TLabel"
NEON_VALUE_STYLE = "Value.TLabel"
NEON_PERCENT_STYLE = "Percent.TLabel"
PRIMARY_BUTTON_STYLE = "Primary.TButton"
SECONDARY_BUTTON_STYLE = "Secondary.TButton"
DANGER_BUTTON_STYLE = "Danger.TButton"
NEON_PROGRESS_STYLE = "Neon.Horizontal.TProgressbar"
SIDEBAR_BUTTON_STYLE = "Sidebar.TButton"
SIDEBAR_ACTIVE_BUTTON_STYLE = "SidebarActive.TButton"
YUGEN_CARD_STYLE = "YugenCard.TLabelframe"
YUGEN_CARD_LABEL_STYLE = "YugenCard.TLabelframe.Label"
FONT_FAMILY_CANDIDATES = (
    "Rajdhani Medium",
    "Rajdhani",
    "Orbitron",
    "Eurostile",
    "Bahnschrift",
    "Segoe UI Semibold",
    "Segoe UI",
    "Noto Sans",
    "DejaVu Sans",
    "Arial",
)
WINDOW_SIZES_BY_SYSTEM = {
    "Windows": ((1050, 760), (860, 620)),
    "Linux": ((960, 700), (820, 600)),
}
DEFAULT_WINDOW_SIZES = ((1000, 720), (820, 600))
SCREEN_EDGE_MARGINS = (40, 80)
WINDOW_RESIZABLE = (False, False)
HISTORY_VISIBLE_ROWS = 4


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


def choose_font_family(
    available_families: tuple[str, ...] | list[str] | set[str] | None = None,
) -> str:
    """Elige Rajdhani si existe o una alternativa moderna y legible."""
    families = set(available_families or ())
    normalized = {family.lower(): family for family in families}
    for candidate in FONT_FAMILY_CANDIDATES:
        if candidate.lower() in normalized:
            return normalized[candidate.lower()]
    return "TkDefaultFont"


class YugenImageStore:
    """Carga assets una sola vez y genera tamaños seguros para Tkinter.

    Pillow se usa si está instalado para mantener calidad con Lanczos. Si falta,
    se conserva un fallback con PhotoImage para que la app no falle al abrir.
    """

    def __init__(self) -> None:
        self._pil_originals: dict[Path, object] = {}
        self._prepared_cache: dict[tuple[Path, bool], object] = {}
        self._photo_cache: dict[tuple[Path, int, int, str, str, bool], tk.PhotoImage] = {}

    def _open_original(self, path: Path):
        if Image is None:
            return None
        resolved = Path(path)
        image = self._pil_originals.get(resolved)
        if image is None and resolved.is_file():
            image = Image.open(resolved).convert("RGBA")
            self._pil_originals[resolved] = image
        return image

    def _prepare_image(self, path: Path, trim: bool):
        """Prepara una copia RGBA y recorta fondos neutros solo cuando aplica."""
        original = self._open_original(path)
        if original is None:
            return None

        cache_key = (Path(path), trim)
        cached = self._prepared_cache.get(cache_key)
        if cached is not None:
            return cached

        prepared = original.copy().convert("RGBA")
        if trim:
            corner = prepared.getpixel((0, 0))[:3]

            def is_neutral_background(red: int, green: int, blue: int, alpha: int) -> bool:
                if alpha < 8:
                    return True
                neutral = (
                    abs(red - green) <= 18
                    and abs(red - blue) <= 18
                    and abs(green - blue) <= 18
                )
                close_to_corner = (
                    abs(red - corner[0])
                    + abs(green - corner[1])
                    + abs(blue - corner[2])
                ) <= 85
                luma = (red + green + blue) / 3
                # Los fondos de algunos PNG son grises con variación suave.
                # Conservamos trazos muy oscuros y volvemos transparente el
                # resto de grises neutros para evitar rectángulos visibles.
                return neutral and (close_to_corner or luma > 32)

            get_pixel_data = getattr(prepared, "get_flattened_data", prepared.getdata)
            cleaned_pixels = []
            for red, green, blue, alpha in get_pixel_data():
                if is_neutral_background(red, green, blue, alpha):
                    cleaned_pixels.append((red, green, blue, 0))
                else:
                    cleaned_pixels.append((red, green, blue, alpha))
            prepared.putdata(cleaned_pixels)

            alpha_box = prepared.getchannel("A").getbbox()
            if alpha_box is not None:
                prepared = prepared.crop(alpha_box)

        self._prepared_cache[cache_key] = prepared
        return prepared

    @staticmethod
    def _crop_offset(extra: int, anchor: str) -> int:
        """Calcula un desplazamiento de recorte para imágenes tipo cover."""
        if extra <= 0:
            return 0
        if anchor in {"left", "top"}:
            return 0
        if anchor in {"right", "bottom"}:
            return extra
        return extra // 2

    def get(
        self,
        path: Path,
        size: tuple[int, int],
        mode: str = "contain",
        *,
        anchor: str = "center",
        trim: bool = False,
    ) -> tk.PhotoImage | None:
        """Devuelve una PhotoImage redimensionada proporcionalmente."""
        width = max(1, int(size[0]))
        height = max(1, int(size[1]))
        key = (Path(path), width, height, mode, anchor, trim)
        if key in self._photo_cache:
            return self._photo_cache[key]

        original = self._prepare_image(path, trim)
        if original is None:
            try:
                if path.is_file():
                    # Sin Pillow no redimensionamos imágenes grandes para no deformar
                    # la interfaz; usamos un lienzo transparente como degradación segura.
                    photo = tk.PhotoImage(width=width, height=height)
                    self._photo_cache[key] = photo
                    return photo
            except tk.TclError as error:
                log_error("Assets", f"No se pudo cargar la imagen {path}.", error)
            return None

        source_width, source_height = original.size
        if source_width <= 0 or source_height <= 0:
            return None

        if mode == "cover":
            scale = max(width / source_width, height / source_height)
        elif mode == "fit_width":
            scale = width / source_width
        else:
            scale = min(width / source_width, height / source_height)
        resized_size = (
            max(1, int(source_width * scale)),
            max(1, int(source_height * scale)),
        )
        resized = original.resize(resized_size, Image.Resampling.LANCZOS)
        if mode == "cover":
            left = self._crop_offset(resized_size[0] - width, anchor)
            top = self._crop_offset(resized_size[1] - height, anchor)
            canvas = resized.crop((left, top, left + width, top + height))
        elif mode == "fit_width":
            canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
            left = 0
            # El banner original tiene luna/silueta arriba-derecha y olas abajo.
            # Tomamos un recorte alto moderado, no centrado agresivamente, para
            # conservar más composición original.
            top = min(0, (height - resized_size[1]) // 2)
            if resized_size[1] > height:
                crop_top = max(0, min(resized_size[1] - height, int((resized_size[1] - height) * 0.18)))
                resized = resized.crop((0, crop_top, width, crop_top + height))
                top = 0
            canvas.alpha_composite(resized, (left, top))
        else:
            canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
            horizontal_extra = width - resized_size[0]
            vertical_extra = height - resized_size[1]
            if anchor == "right":
                left = max(0, horizontal_extra)
            elif anchor == "left":
                left = 0
            else:
                left = horizontal_extra // 2
            if anchor == "bottom":
                top = max(0, vertical_extra)
            elif anchor == "top":
                top = 0
            else:
                top = vertical_extra // 2
            canvas.alpha_composite(resized, (left, top))
        photo = ImageTk.PhotoImage(canvas)
        self._photo_cache[key] = photo
        return photo

    def crop_width(
        self,
        path: Path,
        size: tuple[int, int],
        visible_ratio: float,
        *,
        trim: bool = True,
    ) -> tk.PhotoImage | None:
        """Crea textura horizontal recortada para el progreso real."""
        width = max(1, int(size[0]))
        height = max(1, int(size[1]))
        ratio = max(0.0, min(1.0, visible_ratio))
        visible_width = max(1, int(width * ratio))
        key = (Path(path), visible_width, height, f"crop-{ratio:.3f}", "left", trim)
        if key in self._photo_cache:
            return self._photo_cache[key]

        original = self._prepare_image(path, trim)
        if original is None:
            return self.get(path, (visible_width, height), "cover")
        source_width, source_height = original.size
        scale = max(width / source_width, height / source_height)
        resized = original.resize(
            (
                max(1, int(source_width * scale)),
                max(1, int(source_height * scale)),
            ),
            Image.Resampling.LANCZOS,
        )
        top = self._crop_offset(resized.height - height, "center")
        full_bar = resized.crop((0, top, width, top + height))
        cropped = full_bar.crop((0, 0, visible_width, height))
        photo = ImageTk.PhotoImage(cropped)
        self._photo_cache[key] = photo
        return photo


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
        self.update_notes_widget: tk.Text | None = None
        self.support_dialog: tk.Toplevel | None = None
        self.update_installing = False
        self.style = ttk.Style(self.root)
        self.ui_font_family = choose_font_family(tkfont.families(self.root))
        self.managed_menus: list[tk.Menu] = []
        self.history_item_entries: dict[str, DownloadHistoryEntry] = {}
        # Las referencias se guardan en la instancia para que Tk no libere imágenes.
        self.images = YugenImageStore()
        self.window_icon_image: tk.PhotoImage | None = None
        self.yugen_photo_refs: dict[str, tk.PhotoImage] = {}
        self.header_canvas: tk.Canvas | None = None
        self.sidebar_canvas: tk.Canvas | None = None
        self.progress_canvas: tk.Canvas | None = None
        self.progress_percentage = 0.0
        self.progress_target_percentage = 0.0
        self.progress_animation_job: str | None = None
        self.progress_indeterminate_active = False
        self.progress_indeterminate_offset = 0
        self.thumbnail_label: ttk.Label | None = None
        self.details_panel: ttk.LabelFrame | None = None
        self.details_decoration_label: ttk.Label | None = None
        self.details_decoration_resize_job: str | None = None

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
        self._set_window_icon()
        self.root.geometry(f"{window_size[0]}x{window_size[1]}")
        self.root.minsize(*fitted_minimum)
        self.root.maxsize(*window_size)
        # Esto deshabilita maximizar y conserva minimizar/cerrar.
        self.root.resizable(*WINDOW_RESIZABLE)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _load_photo_image(self, image_path: Path) -> tk.PhotoImage | None:
        """Carga una imagen PNG si existe, sin impedir que la app abra."""
        try:
            if image_path.is_file():
                return tk.PhotoImage(file=str(image_path))
        except tk.TclError as error:
            log_error("Assets", f"No se pudo cargar la imagen {image_path}.", error)
        return None

    def _set_window_icon(self) -> None:
        """Configura el icono de ventana en Windows y Linux usando los assets."""
        if platform.system() == "Windows" and YUGEN_WINDOW_ICON_PATH.is_file():
            try:
                self.root.iconbitmap(default=str(YUGEN_WINDOW_ICON_PATH))
                return
            except tk.TclError as error:
                log_error("Icono", "No se pudo aplicar yugen_audio.ico.", error)

        self.window_icon_image = self._load_photo_image(YUGEN_WINDOW_ICON_PREVIEW_PATH)
        if self.window_icon_image is not None:
            try:
                self.root.iconphoto(True, self.window_icon_image)
            except tk.TclError as error:
                log_error("Icono", "No se pudo aplicar el icono PNG.", error)

    def _build_widgets(self) -> None:
        """Crea la nueva interfaz visual Yūgen sin cambiar callbacks internos."""
        shell = ttk.Frame(self.root, style="Root.TFrame")
        shell.pack(fill="both", expand=True)
        shell.columnconfigure(1, weight=1)
        shell.rowconfigure(0, weight=1)

        sidebar = ttk.Frame(shell, width=110, padding=(8, 14), style="Sidebar.TFrame")
        sidebar.grid(row=0, column=0, sticky="ns")
        sidebar.grid_propagate(False)
        sidebar.rowconfigure(6, weight=1)

        ttk.Label(sidebar, text="MENU", style="SidebarIcon.TLabel").grid(
            row=0, column=0, pady=(0, 22)
        )
        self._build_sidebar_button(sidebar, "Descarga", self._scroll_to_top, True).grid(
            row=1, column=0, sticky="ew", pady=(0, 10)
        )
        self._build_sidebar_button(
            sidebar, "Historial", self._scroll_to_history, False
        ).grid(row=2, column=0, sticky="ew", pady=(0, 10))
        self._build_sidebar_button(
            sidebar, "Ajustes", self._show_settings_info, False
        ).grid(row=3, column=0, sticky="ew", pady=(0, 10))
        self._build_sidebar_button(sidebar, "Acerca de", self._show_about, False).grid(
            row=4, column=0, sticky="ew", pady=(0, 10)
        )

        self.sidebar_canvas = tk.Canvas(
            sidebar,
            width=94,
            height=180,
            borderwidth=0,
            highlightthickness=0,
        )
        self.sidebar_canvas.grid(row=6, column=0, sticky="s", pady=(12, 6))
        self.sidebar_canvas.bind("<Configure>", lambda _event: self._draw_sidebar())
        ttk.Label(sidebar, text=f"Yūgen\nv{APP_VERSION}", style="SidebarFooter.TLabel").grid(
            row=7, column=0, sticky="s"
        )

        scroll_host = ttk.Frame(shell, style="Root.TFrame")
        scroll_host.grid(row=0, column=1, sticky="nsew")
        scroll_host.columnconfigure(0, weight=1)
        scroll_host.rowconfigure(0, weight=1)

        self.main_canvas = tk.Canvas(scroll_host, borderwidth=0, highlightthickness=0)
        self.main_canvas.grid(row=0, column=0, sticky="nsew")
        self.main_scrollbar = ttk.Scrollbar(
            scroll_host,
            orient="vertical",
            command=self.main_canvas.yview,
        )
        self.main_scrollbar.grid(row=0, column=1, sticky="ns")
        self.main_canvas.configure(yscrollcommand=self.main_scrollbar.set)

        container = ttk.Frame(
            self.main_canvas,
            padding=(14, 12, 14, 10),
            style="Main.TFrame",
        )
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

        self.header_canvas = tk.Canvas(
            container,
            height=255,
            borderwidth=0,
            highlightthickness=1,
        )
        self.header_canvas.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        self.header_canvas.bind(
            "<Configure>",
            lambda _event: self._draw_header_decoration(),
            add="+",
        )

        form_panel = ttk.LabelFrame(
            container,
            text="  FUENTE Y CONFIGURACIÓN  ",
            padding=(14, 12, 14, 12),
            style=YUGEN_CARD_STYLE,
        )
        form_panel.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        form_panel.columnconfigure(0, weight=1)
        form_panel.columnconfigure(1, weight=0)

        fields = ttk.Frame(form_panel, style="Panel.TFrame")
        fields.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        fields.columnconfigure(0, weight=1)

        ttk.Label(fields, text="Enlace de YouTube", style=NEON_SECTION_LABEL_STYLE).grid(
            row=0, column=0, sticky="w"
        )
        url_row = ttk.Frame(fields, style="Panel.TFrame")
        url_row.grid(row=1, column=0, sticky="ew", pady=(5, 10))
        url_row.columnconfigure(0, weight=1)
        self.url_entry = ttk.Entry(url_row, textvariable=self.url_value)
        self.url_entry.grid(row=0, column=0, sticky="ew", ipady=5)
        self.paste_button = ttk.Button(
            url_row,
            text="Pegar",
            command=self._paste_link,
            width=12,
            style=PRIMARY_BUTTON_STYLE,
        )
        self.paste_button.grid(row=0, column=1, padx=(8, 0), ipady=3)
        self.clear_button = ttk.Button(
            url_row,
            text="Limpiar",
            command=self._clear_interface,
            width=12,
            style=SECONDARY_BUTTON_STYLE,
        )
        self.clear_button.grid(row=0, column=2, padx=(6, 0), ipady=3)

        ttk.Label(fields, text="Carpeta de salida", style=NEON_SECTION_LABEL_STYLE).grid(
            row=2, column=0, sticky="w"
        )
        folder_row = ttk.Frame(fields, style="Panel.TFrame")
        folder_row.grid(row=3, column=0, sticky="ew", pady=(5, 10))
        folder_row.columnconfigure(0, weight=1)
        self.output_entry = ttk.Entry(
            folder_row,
            textvariable=self.output_value,
            state="readonly",
        )
        self.output_entry.grid(row=0, column=0, sticky="ew", ipady=5)
        self.folder_button = ttk.Button(
            folder_row,
            text="...",
            command=self._select_output_directory,
            width=4,
            style=SECONDARY_BUTTON_STYLE,
        )
        self.folder_button.grid(row=0, column=1, padx=(8, 0), ipady=3)
        self.open_folder_button = ttk.Button(
            folder_row,
            text="Abrir",
            command=self._open_output_directory,
            width=7,
            style=SECONDARY_BUTTON_STYLE,
        )
        self.open_folder_button.grid(row=0, column=2, padx=(5, 0), ipady=3)

        selectors = ttk.Frame(form_panel, style="Panel.TFrame")
        selectors.grid(row=0, column=1, sticky="nsew", padx=(0, 14))
        selectors.columnconfigure(0, weight=1)
        ttk.Label(selectors, text="Formato", style=NEON_SECTION_LABEL_STYLE).grid(
            row=0, column=0, sticky="w"
        )
        self.format_selector = ttk.Combobox(
            selectors,
            textvariable=self.format_value,
            values=[audio_format.selector_label for audio_format in AUDIO_FORMATS],
            state="readonly",
            width=24,
        )
        self.format_selector.grid(row=1, column=0, sticky="ew", pady=(6, 18), ipady=4)
        ttk.Label(selectors, text="Calidad de audio", style=NEON_SECTION_LABEL_STYLE).grid(
            row=2, column=0, sticky="w"
        )
        self.quality_selector = ttk.Combobox(
            selectors,
            textvariable=self.quality_value,
            values=[quality.selector_label for quality in AUDIO_QUALITIES],
            state="readonly",
            width=24,
        )
        self.quality_selector.grid(row=3, column=0, sticky="ew", pady=(6, 0), ipady=4)
        self.format_selector.bind("<<ComboboxSelected>>", self._preference_changed)
        self.quality_selector.bind("<<ComboboxSelected>>", self._preference_changed)

        download_card = ttk.Frame(form_panel, padding=(12, 10), style="DownloadCard.TFrame")
        download_card.grid(row=0, column=2, sticky="ns")
        download_card.grid_propagate(False)
        download_card.configure(width=176, height=188)
        self.download_icon_label = ttk.Label(download_card, style="DownloadCard.TLabel")
        self.download_icon_label.grid(row=0, column=0, pady=(0, 6))
        self.download_button = ttk.Button(
            download_card,
            text="INICIAR\nDESCARGA",
            command=self._start_download,
            width=16,
            style=PRIMARY_BUTTON_STYLE,
        )
        self.download_button.grid(row=1, column=0, ipady=5)

        progress_panel = ttk.LabelFrame(
            container,
            text="  PROGRESO  ",
            padding=(14, 10, 14, 10),
            style=YUGEN_CARD_STYLE,
        )
        progress_panel.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        progress_panel.columnconfigure(0, weight=1)
        self.progress_canvas = tk.Canvas(
            progress_panel,
            height=28,
            borderwidth=0,
            highlightthickness=1,
        )
        self.progress_canvas.grid(row=0, column=0, sticky="ew", padx=(0, 16))
        self.progress_canvas.bind("<Configure>", lambda _event: self._draw_yugen_progress())
        ttk.Label(
            progress_panel,
            textvariable=self.percentage_value,
            width=7,
            style=NEON_PERCENT_STYLE,
        ).grid(row=0, column=1, padx=(0, 18))
        ttk.Label(progress_panel, text="Tiempo restante", style=NEON_MUTED_STYLE).grid(
            row=0, column=2, sticky="e"
        )
        ttk.Label(progress_panel, textvariable=self.eta_value, style=NEON_VALUE_STYLE).grid(
            row=0, column=3, padx=(8, 0), sticky="e"
        )
        self.progress_bar = ttk.Progressbar(
            progress_panel,
            mode="determinate",
            maximum=100,
            style=NEON_PROGRESS_STYLE,
        )

        details_container = ttk.Frame(container, style="Main.TFrame")
        details_container.grid(row=3, column=0, sticky="ew", pady=(0, 10))
        details_container.columnconfigure(1, weight=1)
        details_container.rowconfigure(0, weight=1)

        thumb_card = ttk.Frame(details_container, padding=0, style="MediaCard.TFrame")
        thumb_card.grid(row=0, column=0, sticky="nw", padx=(0, 14))
        thumb_card.grid_propagate(False)
        thumb_card.configure(width=268, height=201)
        self.thumbnail_label = ttk.Label(thumb_card, style="MediaCard.TLabel")
        self.thumbnail_label.grid(row=0, column=0)

        details = ttk.LabelFrame(
            details_container,
            text="  DETALLES DEL PROCESO  ",
            padding=(20, 16, 20, 16),
            style=YUGEN_CARD_STYLE,
        )
        details.grid(row=0, column=1, sticky="nsew")
        details.columnconfigure(0, weight=0)
        details.columnconfigure(1, weight=1)
        details.rowconfigure(0, weight=1)
        details.rowconfigure(7, weight=1)
        self.details_panel = details

        ttk.Label(details, text="Estado", style=NEON_SECTION_LABEL_STYLE).grid(
            row=1, column=0, sticky="w", pady=(0, 6)
        )
        ttk.Label(details, textvariable=self.status_value, style=NEON_VALUE_STYLE).grid(
            row=1, column=1, sticky="w", padx=(18, 210), pady=(0, 6)
        )
        ttk.Label(details, text="Video", style=NEON_MUTED_STYLE).grid(
            row=2, column=0, sticky="w", pady=(0, 6)
        )
        ttk.Label(
            details,
            textvariable=self.video_title_value,
            style=NEON_MUTED_STYLE,
            wraplength=430,
        ).grid(row=2, column=1, sticky="w", padx=(18, 210), pady=(0, 6))
        ttk.Label(details, text="Tamaño", style=NEON_MUTED_STYLE).grid(
            row=3, column=0, sticky="w", pady=(0, 6)
        )
        ttk.Label(details, textvariable=self.size_value, style=NEON_MUTED_STYLE).grid(
            row=3, column=1, sticky="w", padx=(18, 210), pady=(0, 6)
        )
        ttk.Label(details, text="Velocidad", style=NEON_MUTED_STYLE).grid(
            row=4, column=0, sticky="w", pady=(0, 6)
        )
        ttk.Label(details, textvariable=self.speed_value, style=NEON_MUTED_STYLE).grid(
            row=4, column=1, sticky="w", padx=(18, 210), pady=(0, 6)
        )
        ttk.Label(details, text="Tiempo restante", style=NEON_MUTED_STYLE).grid(
            row=5, column=0, sticky="w", pady=(0, 6)
        )
        ttk.Label(details, textvariable=self.eta_value, style=NEON_MUTED_STYLE).grid(
            row=5, column=1, sticky="w", padx=(18, 210), pady=(0, 6)
        )
        ttk.Label(details, text="Tiempos", style=NEON_MUTED_STYLE).grid(
            row=6, column=0, sticky="nw"
        )
        ttk.Label(
            details,
            textvariable=self.timings_value,
            style=NEON_MUTED_STYLE,
            wraplength=430,
        ).grid(row=6, column=1, sticky="w", padx=(18, 210))
        self.details_decoration_label = ttk.Label(details, style="Decoration.TLabel")
        self.details_decoration_label.place(
            relx=1.0,
            rely=1.0,
            anchor="se",
            x=-2,
            y=-2,
        )
        details.bind(
            "<Configure>",
            self._schedule_details_decoration_refresh,
            add="+",
        )

        history_frame = ttk.LabelFrame(
            container,
            text="  HISTORIAL DE DESCARGAS  ",
            padding=(12, 9, 12, 10),
            style=YUGEN_CARD_STYLE,
        )
        history_frame.grid(row=4, column=0, sticky="ew", pady=(0, 10))
        history_frame.columnconfigure(0, weight=1)
        history_frame.rowconfigure(0, weight=1)
        self.history_frame = history_frame

        history_columns = ("number", "name", "format", "quality", "status", "path")
        self.history_tree = ttk.Treeview(
            history_frame,
            columns=history_columns,
            show="headings",
            height=HISTORY_VISIBLE_ROWS,
        )
        history_headings = {
            "number": "#",
            "name": "Título",
            "format": "Formato",
            "quality": "Calidad",
            "status": "Estado",
            "path": "Carpeta",
        }
        history_widths = {
            "number": 42,
            "name": 320,
            "format": 85,
            "quality": 120,
            "status": 120,
            "path": 360,
        }
        for column in history_columns:
            self.history_tree.heading(column, text=history_headings[column])
            self.history_tree.column(
                column,
                width=history_widths[column],
                minwidth=42,
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
        self.history_tree.bind("<<TreeviewSelect>>", self._history_selection_changed)
        self.history_tree.bind("<Double-1>", self._history_double_click)
        self.history_tree.bind("<Button-3>", self._show_history_context_menu)

        history_actions = ttk.Frame(history_frame, style="Panel.TFrame")
        history_actions.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        history_actions.columnconfigure(0, weight=1)
        history_actions.columnconfigure(5, weight=1)

        ttk.Button(
            history_actions,
            text="Abrir carpeta de descargas",
            command=self._open_output_directory,
            width=27,
            style=SECONDARY_BUTTON_STYLE,
        ).grid(row=0, column=0, sticky="w")
        ttk.Button(
            history_actions,
            text="Abrir seleccionado",
            command=self._open_selected_history_file,
            width=20,
            style=SECONDARY_BUTTON_STYLE,
        ).grid(row=0, column=1, padx=(8, 0))
        ttk.Button(
            history_actions,
            text="Abrir su carpeta",
            command=self._open_selected_history_folder,
            width=18,
            style=SECONDARY_BUTTON_STYLE,
        ).grid(row=0, column=2, padx=(8, 0))
        ttk.Button(
            history_actions,
            text="Copiar ruta",
            command=self._copy_selected_history_path,
            width=16,
            style=SECONDARY_BUTTON_STYLE,
        ).grid(row=0, column=3, padx=(8, 0))
        ttk.Button(
            history_actions,
            text="Eliminar entrada",
            command=self._delete_selected_history_entry,
            width=18,
            style=DANGER_BUTTON_STYLE,
        ).grid(row=0, column=4, padx=(8, 0))

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

        actions = ttk.Frame(container, style="Main.TFrame")
        actions.grid(row=5, column=0, sticky="ew")
        actions.columnconfigure(0, weight=1)
        actions.columnconfigure(4, weight=1)

        self.cancel_button = ttk.Button(
            actions,
            text="Cancelar",
            command=self._cancel_download,
            state="disabled",
            width=18,
            style=SECONDARY_BUTTON_STYLE,
        )
        self.cancel_button.grid(row=0, column=1, padx=(0, 8), ipady=4)

        self.open_file_button = ttk.Button(
            actions,
            text="Abrir archivo",
            command=self._open_last_downloaded_file,
            state="disabled",
            width=18,
            style=SECONDARY_BUTTON_STYLE,
        )
        self.open_file_button.grid(row=0, column=2, padx=(8, 0), ipady=4)

        ttk.Label(container, text=f"v{APP_VERSION}", style="Version.TLabel").grid(
            row=6,
            column=0,
            pady=(8, 0),
        )
        self._refresh_static_yugen_images()
        self._draw_yugen_progress()
        self.url_entry.focus_set()

    def _build_sidebar_button(
        self,
        parent: ttk.Frame,
        text: str,
        command,
        active: bool,
    ) -> ttk.Button:
        """Crea botones compactos de navegación sin modificar funciones internas."""
        return ttk.Button(
            parent,
            text=text,
            command=command,
            style=SIDEBAR_ACTIVE_BUTTON_STYLE if active else SIDEBAR_BUTTON_STYLE,
            width=10,
        )

    def _draw_header_decoration(self) -> None:
        """Dibuja el encabezado Yūgen con banner y recursos reales."""
        canvas = self.header_canvas
        if canvas is None:
            return

        palette = THEME_PALETTES.get(self.theme_value.get(), THEME_PALETTES["dark"])
        try:
            width = max(canvas.winfo_width(), 760)
            height = max(canvas.winfo_height(), 245)
        except tk.TclError:
            return

        canvas.delete("all")
        canvas.configure(background=palette["background"], highlightbackground=palette["border"])
        banner = self.images.get(
            YUGEN_HERO_BANNER_PATH,
            (width, height),
            "fit_width",
            anchor="right",
        )
        if banner is not None:
            self.yugen_photo_refs["hero_banner"] = banner
            canvas.create_image(0, 0, image=banner, anchor="nw")
        else:
            canvas.create_rectangle(0, 0, width, height, fill=palette["surface"], outline="")

        # Capa oscura ligera para que el texto de la izquierda siempre sea legible.
        canvas.create_rectangle(0, 0, int(width * 0.58), height, fill="#050B16", stipple="gray50", outline="")
        canvas.create_rectangle(0, 0, int(width * 0.36), height, fill="#050B16", stipple="gray25", outline="")
        canvas.create_rectangle(0, 0, width - 1, height - 1, outline=palette["accent"], width=1)

        emblem_size = min(178, max(140, int(height * 0.70)))
        emblem_x = 32
        emblem_y = max(18, (height - emblem_size) // 2)
        emblem = self.images.get(
            YUGEN_EMBLEM_PATH,
            (emblem_size, emblem_size),
            "contain",
            trim=True,
        )
        if emblem is not None:
            self.yugen_photo_refs["header_emblem"] = emblem
            canvas.create_image(emblem_x, emblem_y, image=emblem, anchor="nw")

        plaque_height = min(height - 36, 198)
        plaque = self.images.get(
            YUGEN_PLAQUE_PATH,
            (64, plaque_height),
            "contain",
            trim=True,
        )
        if plaque is not None:
            self.yugen_photo_refs["header_plaque"] = plaque
            canvas.create_image(width - 78, (height - plaque_height) // 2, image=plaque, anchor="nw")

        text_x = emblem_x + emblem_size + 40
        title_y = max(36, int(height * 0.24))
        equalizer_has_pixels = True
        if Image is not None:
            prepared_equalizer = self.images._prepare_image(YUGEN_HEADER_EQUALIZER_PATH, True)
            equalizer_has_pixels = (
                prepared_equalizer is not None
                and prepared_equalizer.getchannel("A").getbbox() is not None
            )
        equalizer = self.images.get(
            YUGEN_HEADER_EQUALIZER_PATH,
            (300, 38),
            "contain",
            trim=True,
        ) if equalizer_has_pixels else None
        if equalizer is not None:
            self.yugen_photo_refs["header_equalizer"] = equalizer
            canvas.create_image(text_x, title_y + 126, image=equalizer, anchor="nw")
        else:
            self._draw_header_equalizer(canvas, text_x, title_y + 132, palette)

        canvas.create_text(
            text_x,
            title_y,
            text="Yūgen Audio",
            fill=palette["foreground"],
            font=(self.ui_font_family, 40, "bold"),
            anchor="nw",
        )
        canvas.create_text(
            text_x + 10,
            title_y + 54,
            text="Music Downloader",
            fill=palette["accent"],
            font=(self.ui_font_family, 20, "bold"),
            anchor="nw",
        )
        canvas.create_text(
            text_x + 10,
            title_y + 92,
            text=APP_TAGLINE,
            fill=palette["muted"],
            font=(self.ui_font_family, 12),
            anchor="nw",
        )

    def _draw_header_equalizer(self, canvas: tk.Canvas, x: int, y: int, palette: dict[str, str]) -> None:
        """Dibuja una línea decorativa mínima si el PNG del ecualizador está vacío."""
        line_width = 260
        canvas.create_line(x, y, x + line_width, y, fill=palette["accent"], width=1)
        for offset in (78, 142, 198):
            canvas.create_oval(
                x + offset - 2,
                y - 2,
                x + offset + 2,
                y + 2,
                fill=palette["accent_2"],
                outline="",
            )
        base_x = x + line_width + 10
        for index, bar_height in enumerate((8, 13, 19, 26, 17, 11)):
            bar_x = base_x + index * 6
            canvas.create_rectangle(
                bar_x,
                y - bar_height // 2,
                bar_x + 2,
                y + bar_height // 2,
                fill=palette["accent"],
                outline="",
            )

    def _draw_sidebar(self) -> None:
        """Coloca la decoración vertical de olas en la barra lateral."""
        canvas = self.sidebar_canvas
        if canvas is None:
            return
        palette = THEME_PALETTES.get(self.theme_value.get(), THEME_PALETTES["dark"])
        width = max(canvas.winfo_width(), 80)
        height = max(canvas.winfo_height(), 160)
        canvas.delete("all")
        canvas.configure(background=palette["background"])
        waves = self.images.get(
            YUGEN_SIDEBAR_WAVES_PATH,
            (width, height),
            "cover",
            anchor="bottom",
            trim=True,
        )
        if waves is not None:
            self.yugen_photo_refs["sidebar_waves"] = waves
            canvas.create_image(0, 0, image=waves, anchor="nw")
        canvas.create_oval(
            width // 2 - 5,
            height - 30,
            width // 2 + 5,
            height - 20,
            fill=palette["accent"],
            outline="",
        )

    def _draw_yugen_progress(self) -> None:
        """Pinta la barra de progreso con textura de pincelada azul."""
        canvas = self.progress_canvas
        if canvas is None:
            return
        palette = THEME_PALETTES.get(self.theme_value.get(), THEME_PALETTES["dark"])
        width = max(canvas.winfo_width(), 260)
        height = max(canvas.winfo_height(), 26)
        canvas.delete("all")
        canvas.configure(background=palette["panel"], highlightbackground=palette["border"])
        pad = 3
        canvas.create_rectangle(
            pad,
            pad,
            width - pad,
            height - pad,
            outline=palette["border"],
            fill=palette["background"],
        )
        ratio = max(0.0, min(1.0, self.progress_percentage / 100.0))
        bar_width = width - pad * 2
        bar_height = height - pad * 2

        if self.progress_indeterminate_active:
            segment_width = max(38, int(bar_width * 0.25))
            travel = max(1, bar_width + segment_width)
            left = pad + (self.progress_indeterminate_offset % travel) - segment_width
            canvas.create_rectangle(
                max(pad, left),
                pad,
                min(width - pad, left + segment_width),
                height - pad,
                fill=palette["accent_2"],
                outline="",
                stipple="gray50",
            )
        elif ratio > 0:
            brush = self.images.crop_width(
                YUGEN_PROGRESS_BRUSH_PATH,
                (bar_width, bar_height),
                ratio,
                trim=True,
            )
            if brush is not None:
                self.yugen_photo_refs["progress_brush"] = brush
                canvas.create_image(pad, pad, image=brush, anchor="nw")
            else:
                fill_width = max(1, int(bar_width * ratio))
                canvas.create_rectangle(
                    pad,
                    pad,
                    pad + fill_width,
                    height - pad,
                    fill=palette["accent_2"],
                    outline="",
                )

    def _animate_progress_to_target(self) -> None:
        """Suaviza visualmente el avance sin inventar porcentajes reales."""
        self.progress_animation_job = None
        delta = self.progress_target_percentage - self.progress_percentage
        if abs(delta) <= 0.35:
            self.progress_percentage = self.progress_target_percentage
            self._draw_yugen_progress()
            return

        self.progress_percentage += delta * 0.35
        self._draw_yugen_progress()
        try:
            self.progress_animation_job = self.root.after(
                16,
                self._animate_progress_to_target,
            )
        except tk.TclError:
            self.progress_animation_job = None

    def _start_progress_animation(self) -> None:
        """Arranca la animación determinada si no hay una pendiente."""
        if self.progress_animation_job is None:
            self._animate_progress_to_target()

    def _animate_indeterminate_progress(self) -> None:
        """Mueve una franja discreta cuando yt-dlp aún no reporta porcentaje."""
        if not self.progress_indeterminate_active:
            return
        self.progress_indeterminate_offset += 10
        self._draw_yugen_progress()
        try:
            self.root.after(55, self._animate_indeterminate_progress)
        except tk.TclError:
            self.progress_indeterminate_active = False

    def _refresh_static_yugen_images(self) -> None:
        """Carga imágenes pequeñas que no dependen del tamaño de ventana."""
        download_icon = self.images.get(
            YUGEN_DOWNLOAD_BUTTON_PATH,
            (112, 112),
            "contain",
            trim=True,
        )
        if download_icon is not None:
            self.yugen_photo_refs["download_button"] = download_icon
            self.download_icon_label.configure(image=download_icon)

        placeholder = self.images.get(
            YUGEN_CONCERT_PLACEHOLDER_PATH,
            (268, 201),
            "cover",
        )
        if placeholder is not None and self.thumbnail_label is not None:
            self.yugen_photo_refs["concert_placeholder"] = placeholder
            self.thumbnail_label.configure(image=placeholder)

        self._refresh_details_decoration()

    def _schedule_details_decoration_refresh(
        self,
        _event: tk.Event | None = None,
    ) -> None:
        """Recalcula la decoración con debounce al cambiar tamaño del panel."""
        if self.details_decoration_resize_job is not None:
            try:
                self.root.after_cancel(self.details_decoration_resize_job)
            except tk.TclError:
                pass
        try:
            self.details_decoration_resize_job = self.root.after(
                80,
                self._refresh_details_decoration,
            )
        except tk.TclError:
            self.details_decoration_resize_job = None

    def _refresh_details_decoration(self) -> None:
        """Mantiene la decoración pegada abajo/derecha sin afectar el layout."""
        if self.details_panel is None or self.details_decoration_label is None:
            return

        try:
            panel_width = max(1, self.details_panel.winfo_width())
            panel_height = max(1, self.details_panel.winfo_height())
        except tk.TclError:
            return

        prepared = self.images._prepare_image(YUGEN_DETAILS_DECORATION_PATH, True)
        if prepared is None:
            return

        source_width, source_height = prepared.size
        if source_width <= 0 or source_height <= 0:
            return

        target_width = max(180, min(340, int(panel_width * 0.38)))
        max_height = max(48, int(panel_height * 0.30))
        target_height = max(1, int(source_height * target_width / source_width))
        if target_height > max_height:
            target_height = max_height
            target_width = max(1, int(source_width * target_height / source_height))

        decoration = self.images.get(
            YUGEN_DETAILS_DECORATION_PATH,
            (target_width, target_height),
            "contain",
            trim=True,
        )
        if decoration is None:
            return

        self.yugen_photo_refs["details_decoration"] = decoration
        self.details_decoration_label.configure(image=decoration)
        self.details_decoration_label.place_configure(
            relx=1.0,
            rely=1.0,
            anchor="se",
            x=-2,
            y=-2,
        )
        self.details_decoration_resize_job = None

    def _scroll_to_top(self) -> None:
        """Mueve el scroll a la descarga sin cambiar estado de la app."""
        self.main_canvas.yview_moveto(0.0)

    def _scroll_to_history(self) -> None:
        """Mueve el scroll hacia el historial si el canvas ya está listo."""
        try:
            self.history_frame.update_idletasks()
            y = self.history_frame.winfo_y()
            total = max(1, self.main_container.winfo_height())
            self.main_canvas.yview_moveto(min(1.0, y / total))
        except tk.TclError:
            self.main_canvas.yview_moveto(1.0)

    def _show_settings_info(self) -> None:
        """Acceso lateral simple a opciones que siguen estando en el menú."""
        messagebox.showinfo(
            "Ajustes",
            "Las herramientas, el tema, actualizaciones y registros están en el menú Herramientas/Ayuda.",
            parent=self.root,
        )

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
        tools_menu.add_command(
            label="Limpiar registros",
            command=self._clear_internal_logs,
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
        help_menu.add_command(
            label="Contacto / Soporte",
            command=self._show_support_dialog,
        )
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

        font_family = getattr(self, "ui_font_family", "TkDefaultFont")
        default_font = (font_family, 10)
        medium_font = (font_family, 10, "bold")
        section_font = (font_family, 11, "bold")
        button_font = (font_family, 10, "bold")
        tree_font = (font_family, 9)
        tree_heading_font = (font_family, 10, "bold")
        self.root.option_add("*Font", default_font)

        self.root.configure(background=palette["background"])
        self.main_canvas.configure(background=palette["background"])
        self.style.configure(
            ".",
            background=palette["background"],
            foreground=palette["foreground"],
            font=default_font,
        )
        self.style.configure(
            "TFrame",
            background=palette["background"],
        )
        self.style.configure("Root.TFrame", background=palette["background"])
        self.style.configure("Main.TFrame", background=palette["background"])
        self.style.configure("Sidebar.TFrame", background=palette["background"])
        self.style.configure("SidebarIcon.TLabel", background=palette["background"], foreground=palette["foreground"], font=(font_family, 20, "bold"))
        self.style.configure("SidebarFooter.TLabel", background=palette["background"], foreground=palette["muted"], font=(font_family, 10, "bold"), justify="center")
        self.style.configure("DownloadCard.TFrame", background=palette["panel"], borderwidth=1, relief="solid")
        self.style.configure("DownloadCard.TLabel", background=palette["panel"])
        self.style.configure("MediaCard.TFrame", background=palette["panel"], borderwidth=1, relief="solid")
        self.style.configure("MediaCard.TLabel", background=palette["panel"])
        self.style.configure("Decoration.TLabel", background=palette["surface"])
        self.style.configure(
            "Header.TFrame",
            background=palette["surface"],
            borderwidth=1,
            relief="solid",
        )
        self.style.configure("Header.TLabel", background=palette["surface"])
        self.style.configure("Panel.TFrame", background=palette["surface"])
        self.style.configure(
            "Inner.TFrame",
            background=palette["panel"],
            borderwidth=1,
            relief="solid",
        )
        self.style.configure(
            "TLabel",
            background=palette["background"],
            foreground=palette["foreground"],
        )
        self.style.configure(
            NEON_TITLE_STYLE,
            background=palette["surface"],
            foreground=palette["foreground"],
            font=(font_family, 30, "bold"),
        )
        self.style.configure(
            "BrandSubtitleLarge.TLabel",
            background=palette["surface"],
            foreground=palette["accent"],
            font=(font_family, 17, "bold"),
        )
        self.style.configure(
            NEON_SUBTITLE_STYLE,
            background=palette["surface"],
            foreground=palette["muted"],
            font=(font_family, 10),
        )
        self.style.configure(
            NEON_SECTION_LABEL_STYLE,
            background=palette["surface"],
            foreground=palette["accent"],
            font=section_font,
        )
        self.style.configure(
            NEON_MUTED_STYLE,
            background=palette["surface"],
            foreground=palette["muted"],
        )
        self.style.configure(
            NEON_VALUE_STYLE,
            background=palette["surface"],
            foreground=palette["accent"],
            font=medium_font,
        )
        self.style.configure(
            NEON_PERCENT_STYLE,
            background=palette["background"],
            foreground=palette["accent"],
            font=(font_family, 22, "bold"),
        )
        self.style.configure(
            "Version.TLabel",
            background=palette["background"],
            foreground=palette["accent"],
            font=(font_family, 10, "bold"),
        )
        self.style.configure(
            "SupportLink.TLabel",
            background=palette["background"],
            foreground=palette["accent"],
        )
        self.style.configure(
            "TLabelframe",
            background=palette["surface"],
            bordercolor=palette["border"],
        )
        self.style.configure(
            "TLabelframe.Label",
            background=palette["surface"],
            foreground=palette["foreground"],
        )
        self.style.configure(
            NEON_PANEL_STYLE,
            background=palette["surface"],
            bordercolor=palette["border"],
            lightcolor=palette["border"],
            darkcolor=palette["selected"],
        )
        self.style.configure(
            NEON_PANEL_LABEL_STYLE,
            background=palette["surface"],
            foreground=palette["accent"],
            font=section_font,
        )
        self.style.configure(
            YUGEN_CARD_STYLE,
            background=palette["surface"],
            bordercolor=palette["border"],
            lightcolor=palette["accent"],
            darkcolor=palette["border"],
        )
        self.style.configure(
            YUGEN_CARD_LABEL_STYLE,
            background=palette["surface"],
            foreground=palette["accent"],
            font=(font_family, 10, "bold"),
        )
        self.style.configure(
            "TButton",
            padding=(7, 3),
            background=palette["surface"],
            foreground=palette["foreground"],
            font=button_font,
        )
        self.style.map(
            "TButton",
            background=[("active", palette["selected"])],
            foreground=[("disabled", palette["muted"])],
        )
        self.style.configure(
            SECONDARY_BUTTON_STYLE,
            padding=(8, 4),
            background=palette["surface"],
            foreground=palette["foreground"],
            bordercolor=palette["border"],
            lightcolor=palette["border"],
            darkcolor=palette["selected"],
            font=button_font,
        )
        self.style.map(
            SECONDARY_BUTTON_STYLE,
            background=[
                ("active", palette["selected"]),
                ("disabled", palette["surface"]),
            ],
            foreground=[("disabled", palette["muted"])],
        )
        self.style.configure(
            SIDEBAR_BUTTON_STYLE,
            padding=(6, 8),
            background=palette["background"],
            foreground=palette["muted"],
            bordercolor=palette["border"],
            font=(font_family, 10, "bold"),
            justify="center",
        )
        self.style.map(
            SIDEBAR_BUTTON_STYLE,
            background=[("active", palette["selected"])],
            foreground=[("active", palette["foreground"])],
        )
        self.style.configure(
            SIDEBAR_ACTIVE_BUTTON_STYLE,
            padding=(6, 8),
            background=palette["selected"],
            foreground=palette["foreground"],
            bordercolor=palette["accent"],
            font=(font_family, 10, "bold"),
            justify="center",
        )
        self.style.map(
            SIDEBAR_ACTIVE_BUTTON_STYLE,
            background=[("active", palette["selected"])],
            foreground=[("active", palette["accent"])],
        )
        self.style.configure(
            PRIMARY_BUTTON_STYLE,
            padding=(9, 4),
            background=palette["accent_2"],
            foreground="#ffffff",
            bordercolor=palette["glow"],
            lightcolor=palette["glow"],
            darkcolor=palette["accent"],
            font=(font_family, 11, "bold"),
        )
        self.style.map(
            PRIMARY_BUTTON_STYLE,
            background=[
                ("active", palette["accent"]),
                ("disabled", palette["surface"]),
            ],
            foreground=[("disabled", palette["muted"])],
        )
        self.style.configure(
            DANGER_BUTTON_STYLE,
            padding=(8, 4),
            background=palette["surface"],
            foreground=palette["error"],
            bordercolor=palette["error"],
            font=button_font,
        )
        self.style.map(
            DANGER_BUTTON_STYLE,
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
            font=tree_font,
            rowheight=23,
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
            font=tree_heading_font,
            padding=(5, 3),
        )
        self.style.configure(
            "Horizontal.TProgressbar",
            background=palette["accent"],
            troughcolor=palette["surface"],
        )
        self.style.configure(
            NEON_PROGRESS_STYLE,
            background=palette["accent"],
            troughcolor=palette["panel_alt"],
            bordercolor=palette["border"],
            lightcolor=palette["glow"],
            darkcolor=palette["accent_2"],
        )

        for menu in self.managed_menus:
            try:
                menu.configure(
                    background=palette["surface"],
                    foreground=palette["foreground"],
                    activebackground=palette["selected"],
                    activeforeground=palette["foreground"],
                    font=default_font,
                )
            except tk.TclError:
                pass

        success_color = palette["success"]
        error_color = palette["error"]
        self.history_tree.tag_configure("completed", foreground=success_color)
        self.history_tree.tag_configure("cancelled", foreground=palette["muted"])
        self.history_tree.tag_configure("error", foreground=error_color)

        if self.header_canvas is not None:
            self._draw_header_decoration()
        if self.sidebar_canvas is not None:
            self._draw_sidebar()
        if self.progress_canvas is not None:
            self._draw_yugen_progress()
        self._refresh_static_yugen_images()

        if self.support_dialog and self.support_dialog.winfo_exists():
            self.support_dialog.configure(background=palette["background"])

        if save_preference:
            self._save_preferences(show_error=True)

    def _refresh_history_tree(self) -> None:
        """Sincroniza la tabla visible con el historial almacenado."""
        for item_id in self.history_tree.get_children():
            self.history_tree.delete(item_id)
        self.history_item_entries.clear()

        for index, entry in enumerate(self.history_entries):
            item_id = f"history-{index}"
            folder = str(Path(entry.path).parent) if entry.path else "—"
            self.history_tree.insert(
                "",
                "end",
                iid=item_id,
                values=(
                    index + 1,
                    entry.name,
                    entry.output_format,
                    entry.quality,
                    entry.status_label,
                    folder,
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

    def _clear_internal_logs(self) -> None:
        """Limpia solo logs técnicos; no toca historial, ajustes ni descargas."""
        if not messagebox.askyesno(
            "Limpiar registros",
            "¿Seguro que quieres limpiar los registros internos? "
            "Esto no eliminará tus descargas, tu historial ni tu configuración.",
            parent=self.root,
        ):
            return

        try:
            clear_internal_logs()
        except ErrorLogClearError as error:
            log_error("Registros", str(error), error)
            messagebox.showerror(
                "Limpiar registros",
                "No se pudieron limpiar los registros internos. "
                "Revisa los permisos de la carpeta de la aplicación.",
                parent=self.root,
            )
            return

        messagebox.showinfo(
            "Limpiar registros",
            "Registros limpiados correctamente.",
            parent=self.root,
        )

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

    def _show_support_dialog(self) -> None:
        """Muestra el contacto oficial sin depender de servicios adicionales."""
        if self.support_dialog and self.support_dialog.winfo_exists():
            self.support_dialog.lift()
            self.support_dialog.focus_force()
            return

        dialog = tk.Toplevel(self.root)
        self.support_dialog = dialog
        dialog.title("Contacto / Soporte")
        dialog.geometry("560x230")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.protocol("WM_DELETE_WINDOW", self._close_support_dialog)
        palette = THEME_PALETTES[self.theme_value.get()]
        dialog.configure(background=palette["background"])

        container = ttk.Frame(dialog, padding=18)
        container.pack(fill="both", expand=True)
        ttk.Label(
            container,
            text="Contacto / Soporte",
            font=("TkDefaultFont", 14, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            container,
            text=(
                "Para soporte, dudas o reportar problemas puedes contactarme "
                "por Discord."
            ),
            wraplength=510,
        ).pack(anchor="w", pady=(10, 8))
        ttk.Label(
            container,
            text=SUPPORT_DISCORD_URL,
            style="SupportLink.TLabel",
        ).pack(anchor="w", pady=(0, 18))

        buttons = ttk.Frame(container)
        buttons.pack(fill="x")
        ttk.Button(
            buttons,
            text="Abrir Discord",
            command=self._open_support_link,
            width=16,
        ).pack(side="left")
        ttk.Button(
            buttons,
            text="Copiar enlace",
            command=self._copy_support_link,
            width=16,
        ).pack(side="left", padx=(8, 0))
        ttk.Button(
            buttons,
            text="Cerrar",
            command=self._close_support_dialog,
            width=12,
        ).pack(side="right")

    def _close_support_dialog(self) -> None:
        """Cierra únicamente la ventana informativa de soporte."""
        if self.support_dialog and self.support_dialog.winfo_exists():
            self.support_dialog.destroy()
        self.support_dialog = None

    def _open_support_link(self) -> None:
        """Abre exclusivamente la URL oficial y constante de soporte."""
        try:
            opened = webbrowser.open(SUPPORT_DISCORD_URL, new=2)
            if not opened:
                raise OSError("El sistema no confirmó la apertura del navegador.")
        except Exception as error:
            log_error("Soporte", "No se pudo abrir el enlace de Discord.", error)
            messagebox.showerror(
                "No se pudo abrir Discord",
                "No se pudo abrir el enlace en el navegador predeterminado.",
                parent=self.support_dialog or self.root,
            )

    def _copy_support_link(self) -> None:
        """Copia la URL como texto, sin ejecutarla ni interpretarla."""
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(SUPPORT_DISCORD_URL)
            self.root.update_idletasks()
        except tk.TclError as error:
            log_error("Soporte", "No se pudo copiar el enlace de Discord.", error)
            messagebox.showerror(
                "No se pudo copiar",
                "No se pudo copiar el enlace al portapapeles.",
                parent=self.support_dialog or self.root,
            )
            return
        messagebox.showinfo(
            "Enlace copiado",
            "El enlace de Discord se copió al portapapeles.",
            parent=self.support_dialog or self.root,
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

        package_text = "Paquete: no disponible"
        size_text = "Tamaño: no disponible"
        try:
            _platform_key, asset, _kind = select_release_asset(result)
            package_text = f"Paquete: {asset.name}"
            if asset.size is not None:
                size_text = f"Tamaño: {format_bytes(asset.size)}"
        except UpdatePackageError:
            asset = None
        ttk.Label(
            container,
            text=f"{package_text}\n{size_text}",
        ).pack(anchor="w", pady=(0, 8))
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
        self.update_notes_widget = notes

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
        self.update_notes_widget = None

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
        self.update_dialog_status_value.set(
            f"Paquete seleccionado: {package.asset.name}"
        )
        if package.notes and self.update_notes_widget:
            self.update_notes_widget.configure(state="normal")
            self.update_notes_widget.delete("1.0", tk.END)
            self.update_notes_widget.insert("1.0", package.notes[:6_000])
            self.update_notes_widget.configure(state="disabled")
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
                self.progress_indeterminate_active = True
                self.progress_indeterminate_offset = 0
                self._animate_indeterminate_progress()
            self.percentage_value.set("—")
            self.progress_percentage = 0.0
            self._draw_yugen_progress()
            return

        if self.progress_is_indeterminate:
            self.progress_bar.stop()
            self.progress_bar.configure(mode="determinate")
            self.progress_is_indeterminate = False
        self.progress_indeterminate_active = False

        bounded_percentage = max(0.0, min(100.0, percentage))
        self.progress_bar["value"] = bounded_percentage
        self.percentage_value.set(f"{bounded_percentage:.0f} %")
        self.progress_target_percentage = bounded_percentage
        if bounded_percentage <= 0:
            if self.progress_animation_job is not None:
                try:
                    self.root.after_cancel(self.progress_animation_job)
                except tk.TclError:
                    pass
                self.progress_animation_job = None
            self.progress_percentage = 0.0
            self._draw_yugen_progress()
            return
        self._start_progress_animation()

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
