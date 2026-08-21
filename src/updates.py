"""Consulta segura y no destructiva de actualizaciones en GitHub Releases."""

from __future__ import annotations

import json
import re
import socket
import ssl
from dataclasses import dataclass
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from src.config import APP_VERSION


GITHUB_API_URL = (
    "https://api.github.com/repos/KENJIOFC/kenji-music-downloader/releases/latest"
)
GITHUB_RELEASES_URL = "https://github.com/KENJIOFC/kenji-music-downloader/releases"
UPDATE_TIMEOUT_SECONDS = 8.0
MAX_RESPONSE_BYTES = 1_000_000
_VERSION_PATTERN = re.compile(r"^[vV]?(\d+)\.(\d+)\.(\d+)$")


class InvalidVersionError(ValueError):
    """Indica que una versión no tiene el formato major.minor.patch."""


@dataclass(frozen=True, order=True, slots=True)
class SemanticVersion:
    """Versión semántica mínima comparable sin dependencias externas."""

    major: int
    minor: int
    patch: int

    @classmethod
    def parse(cls, value: str) -> "SemanticVersion":
        """Acepta 1.2.3 o v1.2.3 e ignora espacios exteriores."""
        match = _VERSION_PATTERN.fullmatch(str(value).strip())
        if match is None:
            raise InvalidVersionError(
                f"Formato de versión inválido: {value!r}. Se esperaba v1.2.3."
            )
        return cls(*(int(component) for component in match.groups()))

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"


@dataclass(frozen=True, slots=True)
class ReleaseAsset:
    """Metadatos listos para una futura descarga manual o automática."""

    name: str
    download_url: str
    size: int | None = None
    content_type: str = ""


@dataclass(frozen=True, slots=True)
class UpdateResult:
    """Resultado completo y estable consumido por la interfaz."""

    success: bool
    update_available: bool
    current_version: str
    latest_version: str | None = None
    release_url: str = GITHUB_RELEASES_URL
    release_name: str = ""
    release_notes: str = ""
    published_at: str = ""
    assets: tuple[ReleaseAsset, ...] = ()
    error_message: str = ""
    error_type: str = ""


def compare_versions(left: str, right: str) -> int:
    """Devuelve 1 si left es mayor, -1 si es menor y 0 si son iguales."""
    left_version = SemanticVersion.parse(left)
    right_version = SemanticVersion.parse(right)
    return (left_version > right_version) - (left_version < right_version)


def _failure(current_version: str, error_type: str, message: str) -> UpdateResult:
    return UpdateResult(
        success=False,
        update_available=False,
        current_version=str(current_version).removeprefix("v").removeprefix("V"),
        error_type=error_type,
        error_message=message,
    )


def _safe_release_url(value: object) -> str:
    """Acepta únicamente páginas HTTPS del repositorio oficial."""
    if not isinstance(value, str):
        return GITHUB_RELEASES_URL
    parsed = urlparse(value)
    expected_prefix = "/KENJIOFC/kenji-music-downloader/releases"
    if (
        parsed.scheme == "https"
        and parsed.netloc.lower() == "github.com"
        and parsed.path.startswith(expected_prefix)
    ):
        return value
    return GITHUB_RELEASES_URL


def _parse_assets(value: object) -> tuple[ReleaseAsset, ...]:
    """Extrae assets válidos sin iniciar ninguna descarga."""
    if not isinstance(value, list):
        return ()

    assets: list[ReleaseAsset] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        download_url = item.get("browser_download_url")
        if not isinstance(name, str) or not isinstance(download_url, str):
            continue
        parsed_url = urlparse(download_url)
        if parsed_url.scheme != "https" or parsed_url.netloc.lower() != "github.com":
            continue
        raw_size = item.get("size")
        size = raw_size if isinstance(raw_size, int) and raw_size >= 0 else None
        content_type = item.get("content_type")
        assets.append(
            ReleaseAsset(
                name=name,
                download_url=download_url,
                size=size,
                content_type=content_type if isinstance(content_type, str) else "",
            )
        )
    return tuple(assets)


def parse_release_payload(payload: object, current_version: str) -> UpdateResult:
    """Convierte la respuesta JSON de GitHub en un resultado controlado."""
    if not isinstance(payload, dict):
        return _failure(
            current_version,
            "invalid_response",
            "No se pudo leer correctamente la información de actualizaciones desde GitHub.",
        )

    tag_name = payload.get("tag_name")
    if not isinstance(tag_name, str) or not tag_name.strip():
        return _failure(
            current_version,
            "missing_tag",
            "La release de GitHub no contiene un tag_name válido.",
        )

    try:
        local_version = SemanticVersion.parse(current_version)
        remote_version = SemanticVersion.parse(tag_name)
    except InvalidVersionError as error:
        return _failure(current_version, "invalid_version", str(error))

    release_name = payload.get("name")
    release_notes = payload.get("body")
    published_at = payload.get("published_at")
    return UpdateResult(
        success=True,
        update_available=remote_version > local_version,
        current_version=str(local_version),
        latest_version=str(remote_version),
        release_url=_safe_release_url(payload.get("html_url")),
        release_name=release_name if isinstance(release_name, str) else "",
        release_notes=release_notes if isinstance(release_notes, str) else "",
        published_at=published_at if isinstance(published_at, str) else "",
        assets=_parse_assets(payload.get("assets")),
    )


def check_for_updates(
    current_version: str = APP_VERSION,
    timeout: float = UPDATE_TIMEOUT_SECONDS,
    opener: Callable[..., object] = urlopen,
) -> UpdateResult:
    """Consulta la última release sin descargar ni modificar archivos."""
    request = Request(
        GITHUB_API_URL,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"Yugen-Audio/{current_version}",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )

    try:
        with opener(request, timeout=max(1.0, float(timeout))) as response:
            raw_payload = response.read(MAX_RESPONSE_BYTES + 1)
        if len(raw_payload) > MAX_RESPONSE_BYTES:
            return _failure(
                current_version,
                "response_too_large",
                "La respuesta de GitHub es demasiado grande para procesarla con seguridad.",
            )
        payload = json.loads(raw_payload.decode("utf-8"))
    except HTTPError as error:
        if error.code == 404:
            return _failure(
                current_version,
                "no_releases",
                "No se encontraron versiones publicadas en GitHub Releases.",
            )
        if error.code == 403:
            return _failure(
                current_version,
                "rate_limit",
                "GitHub rechazó temporalmente la consulta o se alcanzó el límite de la API.",
            )
        return _failure(
            current_version,
            "http_error",
            f"GitHub respondió con el error HTTP {error.code}.",
        )
    except (socket.timeout, TimeoutError):
        return _failure(
            current_version,
            "timeout",
            "La consulta de actualizaciones superó el tiempo de espera.",
        )
    except ssl.SSLError:
        return _failure(
            current_version,
            "ssl_error",
            "No se pudo establecer una conexión segura con GitHub.",
        )
    except URLError as error:
        reason = error.reason
        if isinstance(reason, (socket.timeout, TimeoutError)):
            error_type = "timeout"
            message = "La consulta de actualizaciones superó el tiempo de espera."
        elif isinstance(reason, ssl.SSLError):
            error_type = "ssl_error"
            message = "No se pudo establecer una conexión segura con GitHub."
        else:
            error_type = "connection_error"
            message = "No se pudo conectar con GitHub para buscar actualizaciones."
        return _failure(current_version, error_type, message)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return _failure(
            current_version,
            "invalid_json",
            "No se pudo leer correctamente la información de actualizaciones desde GitHub.",
        )
    except (OSError, ValueError, TypeError) as error:
        return _failure(
            current_version,
            "unexpected_error",
            f"Ocurrió un error inesperado al consultar GitHub: {error}",
        )
    except Exception:
        return _failure(
            current_version,
            "unexpected_error",
            "Ocurrió un error inesperado al consultar GitHub.",
        )

    return parse_release_payload(payload, current_version)
