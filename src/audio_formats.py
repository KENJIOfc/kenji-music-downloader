"""Formatos de audio disponibles para la interfaz y el descargador."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AudioFormat:
    """Describe cómo mostrar y convertir un formato de salida."""

    key: str
    display_name: str
    selector_label: str
    yt_dlp_codec: str
    extension: str
    supports_bitrate: bool = True


@dataclass(frozen=True, slots=True)
class AudioQuality:
    """Calidad seleccionable para formatos con compresión."""

    key: str
    selector_label: str
    bitrate_kbps: int


AUDIO_FORMATS = (
    AudioFormat(
        key="mp3",
        display_name="MP3",
        selector_label="MP3 - Compatible/recomendado",
        yt_dlp_codec="mp3",
        extension="mp3",
    ),
    AudioFormat(
        key="m4a",
        display_name="M4A",
        selector_label="M4A - Buena calidad y buen peso",
        yt_dlp_codec="m4a",
        extension="m4a",
    ),
    AudioFormat(
        key="opus",
        display_name="OPUS",
        selector_label="OPUS - Ligero y buena calidad",
        yt_dlp_codec="opus",
        extension="opus",
    ),
    AudioFormat(
        key="wav",
        display_name="WAV",
        selector_label="WAV - Sin compresión / para edición",
        yt_dlp_codec="wav",
        extension="wav",
        supports_bitrate=False,
    ),
    AudioFormat(
        key="flac",
        display_name="FLAC",
        selector_label="FLAC - Alta calidad sin pérdida",
        yt_dlp_codec="flac",
        extension="flac",
        supports_bitrate=False,
    ),
    AudioFormat(
        key="ogg",
        display_name="OGG",
        selector_label="OGG - Formato alternativo",
        yt_dlp_codec="vorbis",
        extension="ogg",
    ),
)

DEFAULT_AUDIO_FORMAT_KEY = "mp3"
AUDIO_QUALITIES = (
    AudioQuality("low", "Baja - 128 kbps", 128),
    AudioQuality("medium", "Media - 192 kbps", 192),
    AudioQuality("high", "Alta - 256 kbps", 256),
    AudioQuality("maximum", "Máxima - 320 kbps", 320),
)
DEFAULT_AUDIO_QUALITY_KEY = "medium"
_FORMATS_BY_KEY = {audio_format.key: audio_format for audio_format in AUDIO_FORMATS}
_FORMATS_BY_LABEL = {
    audio_format.selector_label: audio_format for audio_format in AUDIO_FORMATS
}
_QUALITIES_BY_KEY = {quality.key: quality for quality in AUDIO_QUALITIES}
_QUALITIES_BY_LABEL = {quality.selector_label: quality for quality in AUDIO_QUALITIES}


def get_audio_format(key: str) -> AudioFormat:
    """Devuelve un formato permitido o produce un error controlado."""
    try:
        return _FORMATS_BY_KEY[key.lower()]
    except (AttributeError, KeyError) as error:
        raise ValueError(f"Formato de audio no compatible: {key}") from error


def get_audio_format_from_label(label: str) -> AudioFormat:
    """Traduce la etiqueta de solo lectura elegida en la interfaz."""
    try:
        return _FORMATS_BY_LABEL[label]
    except KeyError as error:
        raise ValueError(f"Formato de audio no compatible: {label}") from error


def get_audio_quality(key: str) -> AudioQuality:
    """Devuelve una calidad permitida o produce un error controlado."""
    try:
        return _QUALITIES_BY_KEY[key.lower()]
    except (AttributeError, KeyError) as error:
        raise ValueError(f"Calidad de audio no compatible: {key}") from error


def get_audio_quality_from_label(label: str) -> AudioQuality:
    """Traduce la etiqueta visible del selector a una calidad segura."""
    try:
        return _QUALITIES_BY_LABEL[label]
    except KeyError as error:
        raise ValueError(f"Calidad de audio no compatible: {label}") from error
