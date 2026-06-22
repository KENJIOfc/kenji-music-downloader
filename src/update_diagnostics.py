"""Diagnóstico no destructivo del actualizador usando GitHub Releases."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import platform
from tempfile import TemporaryDirectory

from src.config import APP_VERSION
from src.error_log import log_error, log_info
from src.update_installer import (
    UpdateInstallationFailure,
    find_payload_root,
    safe_extract_tar,
    safe_extract_zip,
    validate_payload_files,
)
from src.update_manager import (
    UpdateDownloadError,
    UpdateDownloadProgress,
    UpdatePackageError,
    detect_platform_key,
    download_update,
    prepare_update_package,
)
from src.updates import GITHUB_API_URL, UpdateResult, check_for_updates


@dataclass(frozen=True, slots=True)
class UpdateDryRunResult:
    """Resumen comprobable de una prueba que nunca modifica la instalación."""

    system_name: str
    platform_key: str
    asset_name: str
    expected_sha256: str
    calculated_sha256: str
    extracted_files: tuple[str, ...]


def _main_executable_name(platform_key: str) -> str:
    return (
        "KenjiMusicDownloader.exe"
        if platform_key == "windows-x64"
        else "KenjiMusicDownloader"
    )


def run_update_dry_run(
    result: UpdateResult,
    working_directory: Path,
    system_name: str | None = None,
    machine_name: str | None = None,
    manifest_opener=None,
    download_opener=None,
    progress_callback=None,
) -> UpdateDryRunResult:
    """Descarga, verifica y extrae temporalmente sin iniciar el helper."""
    platform_key = detect_platform_key(system_name, machine_name)
    detected_system = "Windows" if platform_key == "windows-x64" else "Linux"
    log_info(
        "Prueba actualizador",
        f"Sistema detectado: {detected_system} ({platform_key}).",
    )

    # Usa exactamente la misma prioridad y fallback que la actualización real.
    package = prepare_update_package(
        result,
        system_name=system_name,
        machine_name=machine_name,
        opener=manifest_opener,
    )

    root = Path(working_directory).resolve()
    download_directory = root / "download"
    extraction_directory = root / "extracted"
    root.mkdir(parents=True, exist_ok=True)
    log_info("Prueba actualizador", f"Asset elegido: {package.asset.name}.")
    log_info(
        "Prueba actualizador",
        f"Ruta de descarga temporal: {download_directory / package.asset.name}",
    )
    log_info(
        "Prueba actualizador",
        f"SHA-256 esperado: {package.expected_sha256}",
    )

    downloaded = download_update(
        package,
        progress_callback=progress_callback,
        opener=download_opener,
        updates_directory=download_directory,
    )
    log_info(
        "Prueba actualizador",
        f"SHA-256 calculado: {downloaded.calculated_sha256}",
    )

    if package.package_kind == "zip":
        safe_extract_zip(downloaded.path, extraction_directory)
    elif package.package_kind == "tar.gz":
        safe_extract_tar(downloaded.path, extraction_directory)
    else:
        raise UpdatePackageError(
            "El modo dry-run actual requiere un paquete ZIP o TAR.GZ."
        )

    main_name = _main_executable_name(platform_key)
    payload_root = find_payload_root(extraction_directory, main_name)
    validate_payload_files(payload_root, main_name)
    extracted_files = tuple(
        sorted(path.name for path in payload_root.iterdir() if path.is_file())
    )
    log_info(
        "Prueba actualizador",
        "Extracción temporal correcta: " + ", ".join(extracted_files),
    )
    log_info(
        "Prueba actualizador",
        "Prueba completada; no se realizaron cambios en la instalación actual.",
    )
    return UpdateDryRunResult(
        system_name=detected_system,
        platform_key=platform_key,
        asset_name=package.asset.name,
        expected_sha256=package.expected_sha256 or "",
        calculated_sha256=downloaded.calculated_sha256,
        extracted_files=extracted_files,
    )


def _platform_override(value: str) -> tuple[str | None, str | None]:
    if value == "windows":
        return "Windows", "AMD64"
    if value == "linux":
        return "Linux", "x86_64"
    return None, None


def _print_progress(progress: UpdateDownloadProgress) -> None:
    if progress.percentage is None:
        print(f"Descargando actualización: {progress.downloaded_bytes} bytes", flush=True)
    else:
        print(
            f"Descargando actualización: {progress.percentage:.1f}%",
            flush=True,
        )


def _parse_arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prueba el actualizador sin reemplazar la aplicación.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Obligatorio: confirma que no se instalará ningún archivo.",
    )
    parser.add_argument(
        "--platform",
        choices=("auto", "windows", "linux"),
        default="auto",
        help="Usa el sistema actual o simula la selección de un asset.",
    )
    parser.add_argument(
        "--expect-version",
        default=None,
        help="Falla si la última release no coincide con esta versión.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    arguments = _parse_arguments(argv)
    if not arguments.dry_run:
        print("Debes indicar --dry-run. No se realizó ninguna operación.")
        return 2

    system_name, machine_name = _platform_override(arguments.platform)
    visible_system = system_name or platform.system()
    log_info("Prueba actualizador", f"URL de release consultada: {GITHUB_API_URL}")
    print(f"Consultando GitHub Releases para {visible_system}…")
    try:
        result = check_for_updates(APP_VERSION)
        if not result.success:
            raise UpdatePackageError(result.error_message)
        if arguments.expect_version and result.latest_version != arguments.expect_version:
            raise UpdatePackageError(
                "La última release no coincide con la versión esperada: "
                f"{result.latest_version or 'desconocida'}."
            )
        with TemporaryDirectory(prefix="kenji-update-dry-run-") as temporary:
            diagnostic = run_update_dry_run(
                result,
                Path(temporary),
                system_name=system_name,
                machine_name=machine_name,
                progress_callback=_print_progress,
            )
    except (
        UpdatePackageError,
        UpdateDownloadError,
        UpdateInstallationFailure,
        OSError,
    ) as error:
        log_error("Prueba actualizador", str(error), error)
        print(f"ERROR: {error}")
        print("No se realizaron cambios en la instalación actual.")
        return 1
    except Exception as error:
        log_error("Prueba actualizador", "Falló el diagnóstico.", error)
        print("ERROR: Ocurrió un error inesperado durante el diagnóstico.")
        print("No se realizaron cambios en la instalación actual.")
        return 1

    print()
    print("Prueba de actualización completada correctamente.")
    print(f"Sistema detectado: {diagnostic.system_name}.")
    print(f"Asset seleccionado: {diagnostic.asset_name}")
    print("SHA-256 verificado correctamente.")
    print("Extracción temporal correcta.")
    print("No se realizaron cambios en la instalación actual.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
