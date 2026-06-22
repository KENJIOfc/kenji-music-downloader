"""Preparación, descarga y lanzamiento seguro de actualizaciones de la app."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import socket
import ssl
import subprocess
import sys
from tempfile import NamedTemporaryFile
from threading import Event
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from src.error_log import log_error, log_info
from src.updates import ReleaseAsset, SemanticVersion, UpdateResult
from src.user_settings import get_settings_path


UPDATE_DOWNLOAD_TIMEOUT_SECONDS = 30.0
MAX_MANIFEST_BYTES = 128 * 1024
MAX_UPDATE_BYTES = 1_500 * 1024 * 1024
DOWNLOAD_CHUNK_BYTES = 1024 * 1024
OFFICIAL_REPOSITORY_PATH = "/kenjiofc/kenji-music-downloader/releases/download/"
SHA256_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")
MANIFEST_ASSET_NAME = "update.json"


class UpdatePackageError(RuntimeError):
    """La release no contiene un paquete instalable y seguro."""


class UpdateDownloadError(RuntimeError):
    """La actualización no pudo descargarse."""


class UpdateIntegrityError(UpdateDownloadError):
    """El contenido descargado no coincide con el hash publicado."""


class UpdateCancelledError(UpdateDownloadError):
    """El usuario canceló la descarga antes de instalar."""


class UpdateInstallError(RuntimeError):
    """No se pudo preparar o iniciar el helper de instalación."""


@dataclass(frozen=True, slots=True)
class UpdatePackage:
    """Asset de release seleccionado y metadatos de integridad."""

    version: str
    platform_key: str
    asset: ReleaseAsset
    package_kind: str
    expected_sha256: str | None = None
    notes: str = ""


@dataclass(frozen=True, slots=True)
class UpdateDownloadProgress:
    """Avance independiente de Tkinter para mantener la GUI fluida."""

    downloaded_bytes: int
    total_bytes: int | None
    percentage: float | None


@dataclass(frozen=True, slots=True)
class DownloadedUpdate:
    """Paquete completo listo para entregarse al helper."""

    package: UpdatePackage
    path: Path
    calculated_sha256: str
    hash_verified: bool


@dataclass(frozen=True, slots=True)
class InstallationContext:
    """Ubicación y estrategia de la instalación que está ejecutándose."""

    mode: str
    platform_key: str
    install_directory: Path
    main_executable: Path
    helper_executable: Path | None
    appimage_target: Path | None = None
    supported: bool = True
    error_message: str = ""


ProgressCallback = Callable[[UpdateDownloadProgress], None]


def _is_official_asset_url(value: str) -> bool:
    parsed = urlparse(value)
    return (
        parsed.scheme == "https"
        and parsed.netloc.lower() == "github.com"
        and parsed.path.lower().startswith(OFFICIAL_REPOSITORY_PATH)
    )


def detect_platform_key(
    system_name: str | None = None,
    machine_name: str | None = None,
) -> str:
    """Normaliza Windows/Linux x64 a las claves usadas por update.json."""
    system_value = (system_name or platform.system()).strip().lower()
    machine_value = (machine_name or platform.machine()).strip().lower()
    if machine_value not in {"amd64", "x86_64", "x64"}:
        raise UpdatePackageError(
            "No hay paquete de actualización compatible con esta arquitectura."
        )
    if system_value == "windows":
        return "windows-x64"
    if system_value == "linux":
        return "linux-x64"
    raise UpdatePackageError(
        "No hay paquete de actualización disponible para este sistema operativo."
    )


def _asset_kind(asset_name: str, platform_key: str) -> str:
    lower_name = asset_name.lower()
    if platform_key == "windows-x64" and lower_name.endswith(".zip"):
        return "zip"
    if platform_key == "linux-x64":
        if lower_name.endswith(".appimage"):
            return "appimage"
        if lower_name.endswith(".tar.gz"):
            return "tar.gz"
        if lower_name.endswith(".zip"):
            return "zip"
    raise UpdatePackageError("El tipo de paquete de actualización no es compatible.")


def _expected_asset_names(version: str, platform_key: str) -> tuple[str, ...]:
    normalized_version = str(SemanticVersion.parse(version))
    prefix = f"KenjiMusicDownloader-v{normalized_version}"
    if platform_key == "windows-x64":
        return (f"{prefix}-Windows-x64.zip",)
    return (
        f"{prefix}-Linux-x64.AppImage",
        f"{prefix}-Linux-x64.tar.gz",
        f"{prefix}-Linux-x64.zip",
    )


def select_release_asset(
    result: UpdateResult,
    system_name: str | None = None,
    machine_name: str | None = None,
) -> tuple[str, ReleaseAsset, str]:
    """Elige por nombre exacto el asset oficial para el sistema actual."""
    if not result.success or not result.latest_version:
        raise UpdatePackageError("La información de la release no es válida.")
    platform_key = detect_platform_key(system_name, machine_name)
    by_name = {asset.name: asset for asset in result.assets}
    for expected_name in _expected_asset_names(result.latest_version, platform_key):
        asset = by_name.get(expected_name)
        if asset is None:
            continue
        if not _is_official_asset_url(asset.download_url):
            raise UpdatePackageError(
                "El asset de actualización no pertenece al repositorio oficial."
            )
        return platform_key, asset, _asset_kind(asset.name, platform_key)
    raise UpdatePackageError(
        "No hay paquete de actualización disponible para este sistema operativo."
    )


def _read_limited_json(response, maximum_bytes: int) -> object:
    raw_data = response.read(maximum_bytes + 1)
    if len(raw_data) > maximum_bytes:
        raise UpdatePackageError("El manifest de actualización es demasiado grande.")
    try:
        return json.loads(raw_data.decode("utf-8-sig"))
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise UpdatePackageError("update.json no contiene JSON válido.") from error


def fetch_update_manifest(
    result: UpdateResult,
    opener=None,
    timeout: float = UPDATE_DOWNLOAD_TIMEOUT_SECONDS,
) -> object | None:
    """Descarga el manifest opcional exclusivamente desde la release oficial."""
    manifest_asset = next(
        (asset for asset in result.assets if asset.name.lower() == MANIFEST_ASSET_NAME),
        None,
    )
    if manifest_asset is None:
        return None
    if not _is_official_asset_url(manifest_asset.download_url):
        raise UpdatePackageError("La URL de update.json no pertenece al repositorio oficial.")

    request = Request(
        manifest_asset.download_url,
        headers={"User-Agent": f"Kenji-Music-Downloader/{result.current_version}"},
    )
    open_request = opener or urlopen
    try:
        with open_request(request, timeout=max(1.0, float(timeout))) as response:
            return _read_limited_json(response, MAX_MANIFEST_BYTES)
    except UpdatePackageError:
        raise
    except HTTPError as error:
        raise UpdatePackageError(
            f"No se pudo descargar update.json: HTTP {error.code}."
        ) from error
    except (URLError, socket.timeout, TimeoutError, ssl.SSLError, OSError) as error:
        raise UpdatePackageError(
            "No se pudo descargar update.json desde GitHub Releases."
        ) from error


def _package_from_manifest(
    result: UpdateResult,
    manifest: object,
    platform_key: str,
) -> UpdatePackage:
    if not isinstance(manifest, dict):
        raise UpdatePackageError("update.json debe contener un objeto JSON.")
    manifest_version = manifest.get("version")
    if not isinstance(manifest_version, str) or not result.latest_version:
        raise UpdatePackageError("update.json no contiene una versión válida.")
    if SemanticVersion.parse(manifest_version) != SemanticVersion.parse(
        result.latest_version
    ):
        raise UpdatePackageError(
            "La versión de update.json no coincide con la release publicada."
        )

    assets = manifest.get("assets")
    platform_data = assets.get(platform_key) if isinstance(assets, dict) else None
    if not isinstance(platform_data, dict):
        raise UpdatePackageError(
            "update.json no contiene un paquete para este sistema operativo."
        )
    asset_name = platform_data.get("name")
    if (
        not isinstance(asset_name, str)
        or Path(asset_name).name != asset_name
        or asset_name not in _expected_asset_names(result.latest_version, platform_key)
    ):
        raise UpdatePackageError("update.json contiene un nombre de asset inválido.")

    asset = next((item for item in result.assets if item.name == asset_name), None)
    if asset is None or not _is_official_asset_url(asset.download_url):
        raise UpdatePackageError(
            "El asset indicado por update.json no existe en la release oficial."
        )

    raw_sha256 = platform_data.get("sha256")
    expected_sha256: str | None = None
    if raw_sha256 is not None:
        if not isinstance(raw_sha256, str) or SHA256_PATTERN.fullmatch(raw_sha256) is None:
            raise UpdatePackageError("update.json contiene un SHA-256 inválido.")
        expected_sha256 = raw_sha256.lower()
    notes = manifest.get("notes")
    return UpdatePackage(
        version=str(SemanticVersion.parse(result.latest_version)),
        platform_key=platform_key,
        asset=asset,
        package_kind=_asset_kind(asset.name, platform_key),
        expected_sha256=expected_sha256,
        notes=notes if isinstance(notes, str) else result.release_notes,
    )


def prepare_update_package(
    result: UpdateResult,
    system_name: str | None = None,
    machine_name: str | None = None,
    opener=None,
) -> UpdatePackage:
    """Resuelve manifest y asset sin descargar todavía el paquete grande."""
    platform_key, asset, package_kind = select_release_asset(
        result,
        system_name,
        machine_name,
    )
    manifest = fetch_update_manifest(result, opener=opener)
    if manifest is not None:
        package = _package_from_manifest(result, manifest, platform_key)
    else:
        package = UpdatePackage(
            version=str(SemanticVersion.parse(result.latest_version or "")),
            platform_key=platform_key,
            asset=asset,
            package_kind=package_kind,
            notes=result.release_notes,
        )
    log_info(
        "Actualizaciones",
        f"Asset seleccionado: {package.asset.name} ({package.platform_key}).",
    )
    log_info("Actualizaciones", f"URL del asset: {package.asset.download_url}")
    return package


def get_updates_directory(system_name: str | None = None) -> Path:
    """Usa APPDATA en Windows y XDG_DATA_HOME en Linux."""
    system_value = (system_name or platform.system()).strip().lower()
    if system_value == "windows":
        return get_settings_path().parent / "updates"
    data_home = Path(
        os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")
    )
    return data_home / "KenjiMusicDownloader" / "updates"


def _cleanup_partial_files(updates_directory: Path) -> None:
    for candidate in updates_directory.glob("*.part"):
        try:
            candidate.unlink()
        except OSError:
            pass


def _cleanup_old_update_files(updates_directory: Path, keep: Path) -> None:
    """Elimina paquetes y helpers de versiones anteriores solo dentro de updates."""
    patterns = (
        "KenjiMusicDownloader-v*-Windows-x64.zip",
        "KenjiMusicDownloader-v*-Linux-x64.zip",
        "KenjiMusicDownloader-v*-Linux-x64.tar.gz",
        "KenjiMusicDownloader-v*-Linux-x64.AppImage",
        "KenjiUpdateInstaller-v*",
    )
    for pattern in patterns:
        for candidate in updates_directory.glob(pattern):
            if candidate == keep:
                continue
            try:
                candidate.unlink()
            except OSError:
                pass


def download_update(
    package: UpdatePackage,
    progress_callback: ProgressCallback | None = None,
    cancel_event: Event | None = None,
    opener=None,
    updates_directory: Path | None = None,
) -> DownloadedUpdate:
    """Descarga en streaming, calcula SHA-256 y publica progreso real."""
    if not _is_official_asset_url(package.asset.download_url):
        raise UpdateDownloadError(
            "La URL de descarga no pertenece al repositorio oficial."
        )
    target_directory = updates_directory or get_updates_directory()
    try:
        target_directory.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise UpdateDownloadError(
            "No se pudo crear la carpeta local de actualizaciones."
        ) from error
    _cleanup_partial_files(target_directory)

    final_path = target_directory / package.asset.name
    partial_path = final_path.with_name(final_path.name + ".part")
    _cleanup_old_update_files(target_directory, final_path)
    request = Request(
        package.asset.download_url,
        headers={"User-Agent": f"Kenji-Music-Downloader/{package.version}"},
    )
    open_request = opener or urlopen
    calculated = hashlib.sha256()
    downloaded = 0
    log_info("Actualizaciones", f"Inicio de descarga: {package.asset.name}")
    try:
        partial_path.unlink(missing_ok=True)
        with open_request(
            request,
            timeout=UPDATE_DOWNLOAD_TIMEOUT_SECONDS,
        ) as response:
            raw_length = response.headers.get("Content-Length")
            total = int(raw_length) if raw_length and str(raw_length).isdigit() else None
            if total is not None and total > MAX_UPDATE_BYTES:
                raise UpdateDownloadError(
                    "El paquete de actualización supera el tamaño máximo permitido."
                )
            with partial_path.open("xb") as target:
                while True:
                    if cancel_event and cancel_event.is_set():
                        raise UpdateCancelledError("La actualización fue cancelada.")
                    chunk = response.read(DOWNLOAD_CHUNK_BYTES)
                    if not chunk:
                        break
                    downloaded += len(chunk)
                    if downloaded > MAX_UPDATE_BYTES:
                        raise UpdateDownloadError(
                            "La descarga superó el tamaño máximo permitido."
                        )
                    target.write(chunk)
                    calculated.update(chunk)
                    if progress_callback:
                        progress_callback(
                            UpdateDownloadProgress(
                                downloaded_bytes=downloaded,
                                total_bytes=total,
                                percentage=(downloaded * 100 / total) if total else None,
                            )
                        )
        if downloaded == 0:
            raise UpdateDownloadError("El paquete de actualización llegó vacío.")

        calculated_sha256 = calculated.hexdigest()
        log_info("Actualizaciones", f"SHA-256 calculado: {calculated_sha256}")
        if package.expected_sha256:
            log_info(
                "Actualizaciones",
                f"SHA-256 esperado: {package.expected_sha256}",
            )
            if calculated_sha256 != package.expected_sha256:
                raise UpdateIntegrityError(
                    "La verificación de integridad falló. La actualización no se instalará."
                )
        partial_path.replace(final_path)
        log_info("Actualizaciones", f"Descarga completada: {final_path}")
        return DownloadedUpdate(
            package=package,
            path=final_path,
            calculated_sha256=calculated_sha256,
            hash_verified=package.expected_sha256 is not None,
        )
    except (UpdateDownloadError, UpdateCancelledError) as error:
        partial_path.unlink(missing_ok=True)
        log_error("Actualizaciones", str(error), error)
        raise
    except HTTPError as error:
        partial_path.unlink(missing_ok=True)
        message = f"GitHub respondió con el error HTTP {error.code} al descargar."
        log_error("Actualizaciones", message, error)
        raise UpdateDownloadError(message) from error
    except (URLError, socket.timeout, TimeoutError, ssl.SSLError) as error:
        partial_path.unlink(missing_ok=True)
        message = "No se pudo descargar la actualización. Revisa tu conexión."
        log_error("Actualizaciones", message, error)
        raise UpdateDownloadError(message) from error
    except OSError as error:
        partial_path.unlink(missing_ok=True)
        message = "No se pudo guardar la actualización en la carpeta local."
        log_error("Actualizaciones", message, error)
        raise UpdateDownloadError(message) from error


def detect_installation_context() -> InstallationContext:
    """Distingue desarrollo, PyInstaller y AppImage sin rutas fijas."""
    platform_key = detect_platform_key()
    if not getattr(sys, "frozen", False):
        project_directory = Path(__file__).resolve().parent.parent
        return InstallationContext(
            mode="development",
            platform_key=platform_key,
            install_directory=project_directory,
            main_executable=Path(sys.executable).resolve(),
            helper_executable=None,
            supported=False,
            error_message=(
                "La instalación automática no reemplaza un árbol de código en modo "
                "desarrollo. Prueba esta función desde el ejecutable empaquetado."
            ),
        )

    if platform_key == "linux-x64" and os.environ.get("APPIMAGE"):
        appimage_path = Path(os.environ["APPIMAGE"]).expanduser().resolve()
        helper = _find_packaged_helper(appimage_path.parent, platform_key)
        return InstallationContext(
            mode="appimage",
            platform_key=platform_key,
            install_directory=appimage_path.parent,
            main_executable=appimage_path,
            helper_executable=helper,
            appimage_target=appimage_path,
            supported=helper is not None,
            error_message="No se encontró el helper de actualización dentro del paquete."
            if helper is None
            else "",
        )

    main_executable = Path(sys.executable).resolve()
    helper = _find_packaged_helper(main_executable.parent, platform_key)
    return InstallationContext(
        mode="archive",
        platform_key=platform_key,
        install_directory=main_executable.parent,
        main_executable=main_executable,
        helper_executable=helper,
        supported=helper is not None,
        error_message="No se encontró KenjiUpdateInstaller junto a la aplicación."
        if helper is None
        else "",
    )


def _find_packaged_helper(
    install_directory: Path,
    platform_key: str,
) -> Path | None:
    filename = (
        "KenjiUpdateInstaller.exe"
        if platform_key == "windows-x64"
        else "KenjiUpdateInstaller"
    )
    candidates = [install_directory / filename]
    bundle_directory = getattr(sys, "_MEIPASS", None)
    if bundle_directory:
        candidates.append(Path(bundle_directory) / filename)
    return next((path.resolve() for path in candidates if path.is_file()), None)


def ensure_installation_writable(context: InstallationContext) -> None:
    """Comprueba permisos sin elevar privilegios ni modificar archivos existentes."""
    if not context.supported:
        raise UpdateInstallError(context.error_message)
    try:
        with NamedTemporaryFile(
            prefix=".kenji-update-write-",
            suffix=".tmp",
            dir=context.install_directory,
        ):
            pass
    except OSError as error:
        raise UpdateInstallError(
            "No se puede actualizar automáticamente porque la carpeta actual no "
            "permite escritura. Extrae la app en una carpeta de usuario, como "
            "Descargas o Documentos."
        ) from error


def get_update_result_path() -> Path:
    return get_updates_directory() / "last_update_result.json"


def consume_update_result(result_path: Path | None = None) -> dict | None:
    """Lee una vez el resultado dejado por el helper al reiniciar."""
    path = result_path or get_update_result_path()
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else None
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    finally:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass


def launch_update_installer(
    downloaded: DownloadedUpdate,
    context: InstallationContext | None = None,
    parent_pid: int | None = None,
    popen=None,
) -> None:
    """Copia y lanza el helper; nunca intenta reemplazar la app abierta."""
    installation = context or detect_installation_context()
    ensure_installation_writable(installation)
    helper = installation.helper_executable
    if helper is None:
        raise UpdateInstallError("No se encontró el helper de actualización.")

    updates_directory = downloaded.path.parent
    helper_suffix = ".exe" if installation.platform_key == "windows-x64" else ""
    helper_copy = updates_directory / (
        f"KenjiUpdateInstaller-v{downloaded.package.version}{helper_suffix}"
    )
    for old_helper in updates_directory.glob("KenjiUpdateInstaller-v*"):
        if old_helper != helper_copy:
            try:
                old_helper.unlink()
            except OSError:
                pass
    try:
        shutil.copy2(helper, helper_copy)
        if installation.platform_key == "linux-x64":
            helper_copy.chmod(helper_copy.stat().st_mode | 0o111)
    except OSError as error:
        raise UpdateInstallError(
            "No se pudo preparar el helper de actualización."
        ) from error

    command = [
        str(helper_copy),
        "--package",
        str(downloaded.path),
        "--kind",
        downloaded.package.package_kind,
        "--install-dir",
        str(installation.install_directory),
        "--main-name",
        installation.main_executable.name,
        "--parent-pid",
        str(parent_pid or os.getpid()),
        "--version",
        downloaded.package.version,
        "--result-path",
        str(get_update_result_path()),
    ]
    if installation.appimage_target:
        command.extend(["--appimage-target", str(installation.appimage_target)])

    process_launcher = popen or subprocess.Popen
    kwargs: dict[str, object] = {
        "cwd": str(updates_directory),
        "close_fds": True,
        "shell": False,
    }
    if installation.platform_key == "windows-x64":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    else:
        kwargs["start_new_session"] = True
    try:
        process_launcher(command, **kwargs)
    except OSError as error:
        log_error("Actualizaciones", "No se pudo iniciar el helper.", error)
        raise UpdateInstallError(
            "No se pudo iniciar el instalador de la actualización."
        ) from error
    log_info("Actualizaciones", f"Helper iniciado: {helper_copy}")
