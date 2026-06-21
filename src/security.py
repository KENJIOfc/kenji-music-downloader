"""Validación y normalización segura de enlaces de YouTube."""

import re
from urllib.parse import parse_qs, urlsplit


class InvalidYouTubeURLError(ValueError):
    """Indica que el texto recibido no es un enlace permitido."""


# Los identificadores de video de YouTube tienen once caracteres.
_VIDEO_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{11}$")
_YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
}
_SHORT_HOSTS = {"youtu.be", "www.youtu.be"}
_MAX_URL_LENGTH = 2_048


def _validate_video_id(video_id: str | None) -> str:
    """Comprueba y devuelve un identificador de video válido."""
    if not video_id or not _VIDEO_ID_PATTERN.fullmatch(video_id):
        raise InvalidYouTubeURLError(
            "El enlace no contiene un identificador de video válido."
        )
    return video_id


def validate_and_normalize_youtube_url(raw_url: str) -> str:
    """Valida una URL permitida y devuelve una URL canónica sin datos sobrantes.

    Solo se aceptan videos individuales de youtube.com, music.youtube.com y
    youtu.be. La normalización descarta parámetros de listas y seguimiento.
    """
    url = raw_url.strip()
    if not url:
        raise InvalidYouTubeURLError("No se escribió ningún enlace.")
    if len(url) > _MAX_URL_LENGTH:
        raise InvalidYouTubeURLError("El enlace es demasiado largo.")
    if any(character.isspace() for character in url):
        raise InvalidYouTubeURLError("El enlace no puede contener espacios.")

    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError as error:
        raise InvalidYouTubeURLError("El enlace tiene un formato incorrecto.") from error

    if parsed.scheme.lower() not in {"http", "https"}:
        raise InvalidYouTubeURLError("El enlace debe comenzar con http:// o https://.")
    if parsed.username or parsed.password:
        raise InvalidYouTubeURLError("El enlace no puede incluir credenciales.")
    if port not in {None, 80, 443}:
        raise InvalidYouTubeURLError("El enlace utiliza un puerto no permitido.")

    host = (parsed.hostname or "").lower().rstrip(".")
    video_id: str | None = None

    if host in _SHORT_HOSTS:
        # En youtu.be, el primer segmento de la ruta es el identificador.
        path_parts = [part for part in parsed.path.split("/") if part]
        if len(path_parts) != 1:
            raise InvalidYouTubeURLError("El enlace corto de YouTube no es válido.")
        video_id = path_parts[0]
    elif host in _YOUTUBE_HOSTS:
        path_parts = [part for part in parsed.path.split("/") if part]
        if parsed.path.rstrip("/") == "/watch":
            # parse_qs devuelve listas porque un parámetro puede repetirse.
            video_id = parse_qs(parsed.query, keep_blank_values=True).get("v", [None])[0]
        elif len(path_parts) == 2 and path_parts[0] in {"shorts", "live"}:
            video_id = path_parts[1]
        else:
            raise InvalidYouTubeURLError(
                "Solo se aceptan enlaces a videos individuales de YouTube."
            )
    else:
        raise InvalidYouTubeURLError(
            "El enlace debe pertenecer a YouTube, YouTube Music o youtu.be."
        )

    safe_video_id = _validate_video_id(video_id)
    return f"https://www.youtube.com/watch?v={safe_video_id}"

