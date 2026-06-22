"""Helper independiente que instala, revierte y reinicia la aplicación."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import subprocess
import sys
import tarfile
from tempfile import TemporaryDirectory
import time
from zipfile import BadZipFile, ZipFile

from src.error_log import log_error, log_info


MAX_ARCHIVE_MEMBERS = 5_000
MAX_EXTRACTED_BYTES = 1_500 * 1024 * 1024
COPY_CHUNK_BYTES = 1024 * 1024
PARENT_EXIT_TIMEOUT_SECONDS = 90


class UpdateInstallationFailure(RuntimeError):
    """Fallo controlado que debe provocar rollback."""


@dataclass(frozen=True, slots=True)
class BackupRecord:
    """Archivos que permiten revertir exactamente una sustitución parcial."""

    backup_directory: Path
    replaced_files: tuple[Path, ...]
    created_files: tuple[Path, ...]


def _safe_relative_path(member_name: str) -> Path:
    """Convierte nombres POSIX del archivo y rechaza rutas de escape."""
    normalized = member_name.replace("\\", "/")
    pure_path = PurePosixPath(normalized)
    if (
        not normalized
        or pure_path.is_absolute()
        or ".." in pure_path.parts
        or any(":" in part for part in pure_path.parts)
    ):
        raise UpdateInstallationFailure(
            "El paquete contiene una ruta insegura y no se instalará."
        )
    useful_parts = tuple(part for part in pure_path.parts if part not in {"", "."})
    if not useful_parts:
        raise UpdateInstallationFailure("El paquete contiene una ruta vacía.")
    return Path(*useful_parts)


def _destination_for(root: Path, member_name: str) -> tuple[Path, Path]:
    relative = _safe_relative_path(member_name)
    destination = (root / relative).resolve()
    try:
        destination.relative_to(root.resolve())
    except ValueError as error:
        raise UpdateInstallationFailure(
            "El paquete intentó escribir fuera de la carpeta temporal."
        ) from error
    return relative, destination


def _copy_stream_with_limit(source, target, current_total: int) -> int:
    """Cuenta bytes reales para impedir expansión mayor a la declarada."""
    total = current_total
    while True:
        chunk = source.read(COPY_CHUNK_BYTES)
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_EXTRACTED_BYTES:
            raise UpdateInstallationFailure(
                "El paquete supera el tamaño máximo extraído permitido."
            )
        target.write(chunk)
    return total


def safe_extract_zip(archive_path: Path, destination: Path) -> None:
    """Extrae ZIP sin symlinks, path traversal ni expansión ilimitada."""
    destination.mkdir(parents=True, exist_ok=True)
    total_size = 0
    try:
        with ZipFile(archive_path) as archive:
            members = archive.infolist()
            if len(members) > MAX_ARCHIVE_MEMBERS:
                raise UpdateInstallationFailure(
                    "El ZIP contiene demasiados archivos."
                )
            for member in members:
                _relative, output_path = _destination_for(destination, member.filename)
                unix_mode = member.external_attr >> 16
                if stat.S_ISLNK(unix_mode):
                    raise UpdateInstallationFailure(
                        "El ZIP contiene enlaces simbólicos no permitidos."
                    )
                if member.is_dir():
                    output_path.mkdir(parents=True, exist_ok=True)
                    continue
                total_size += member.file_size
                if total_size > MAX_EXTRACTED_BYTES:
                    raise UpdateInstallationFailure(
                        "El ZIP supera el tamaño máximo extraído permitido."
                    )
                output_path.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member) as source, output_path.open("xb") as target:
                    total_size = _copy_stream_with_limit(source, target, total_size - member.file_size)
                if unix_mode & 0o111:
                    output_path.chmod(output_path.stat().st_mode | 0o111)
    except BadZipFile as error:
        raise UpdateInstallationFailure(
            "El paquete descargado no es un ZIP válido."
        ) from error


def safe_extract_tar(archive_path: Path, destination: Path) -> None:
    """Extrae TAR.GZ admitiendo solo directorios y archivos regulares."""
    destination.mkdir(parents=True, exist_ok=True)
    total_size = 0
    try:
        with tarfile.open(archive_path, mode="r:gz") as archive:
            members = archive.getmembers()
            if len(members) > MAX_ARCHIVE_MEMBERS:
                raise UpdateInstallationFailure(
                    "El TAR.GZ contiene demasiados archivos."
                )
            for member in members:
                _relative, output_path = _destination_for(destination, member.name)
                if member.isdir():
                    output_path.mkdir(parents=True, exist_ok=True)
                    continue
                if not member.isfile():
                    raise UpdateInstallationFailure(
                        "El TAR.GZ contiene enlaces o tipos de archivo no permitidos."
                    )
                total_size += member.size
                if total_size > MAX_EXTRACTED_BYTES:
                    raise UpdateInstallationFailure(
                        "El TAR.GZ supera el tamaño máximo extraído permitido."
                    )
                source = archive.extractfile(member)
                if source is None:
                    raise UpdateInstallationFailure(
                        "No se pudo leer un archivo del TAR.GZ."
                    )
                output_path.parent.mkdir(parents=True, exist_ok=True)
                with source, output_path.open("xb") as target:
                    total_size = _copy_stream_with_limit(source, target, total_size - member.size)
                if member.mode & 0o111:
                    output_path.chmod(output_path.stat().st_mode | 0o111)
    except (tarfile.TarError, EOFError) as error:
        raise UpdateInstallationFailure(
            "El paquete descargado no es un TAR.GZ válido."
        ) from error


def find_payload_root(extracted_directory: Path, main_name: str) -> Path:
    """Exige exactamente un ejecutable principal dentro del paquete."""
    candidates = [
        path
        for path in extracted_directory.rglob(main_name)
        if path.is_file() and not path.is_symlink()
    ]
    if len(candidates) != 1:
        raise UpdateInstallationFailure(
            f"El paquete debe contener exactamente un archivo {main_name}."
        )
    return candidates[0].parent


def validate_payload_files(payload_directory: Path, main_name: str) -> None:
    """Acepta solo los dos binarios esperados y el README de la release."""
    helper_name = (
        "KenjiUpdateInstaller.exe"
        if main_name.lower().endswith(".exe")
        else "KenjiUpdateInstaller"
    )
    required = {main_name, helper_name}
    allowed = required | {"README.md"}
    names: set[str] = set()
    for path in payload_directory.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(payload_directory)
        if len(relative.parts) != 1 or relative.name not in allowed:
            raise UpdateInstallationFailure(
                f"El paquete contiene un archivo no permitido: {relative}"
            )
        names.add(relative.name)
    missing = required - names
    if missing:
        raise UpdateInstallationFailure(
            "El paquete no contiene todos los ejecutables esperados: "
            + ", ".join(sorted(missing))
        )


def _copy_for_replace(source: Path, destination: Path, replacer) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".update-new")
    temporary.unlink(missing_ok=True)
    try:
        shutil.copy2(source, temporary)
        replacer(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def rollback_installation(record: BackupRecord, install_directory: Path) -> None:
    """Elimina archivos nuevos y restaura copias previas de forma segura."""
    for relative in reversed(record.created_files):
        destination = install_directory / relative
        try:
            destination.unlink(missing_ok=True)
        except OSError:
            pass
    for relative in record.replaced_files:
        backup = record.backup_directory / relative
        destination = install_directory / relative
        if backup.is_file():
            _copy_for_replace(backup, destination, os.replace)


def apply_payload(
    payload_directory: Path,
    install_directory: Path,
    backup_directory: Path,
    replacer=None,
) -> BackupRecord:
    """Copia el payload y revierte automáticamente cualquier fallo parcial."""
    replace_file = replacer or os.replace
    source_files = sorted(
        (
            path
            for path in payload_directory.rglob("*")
            if path.is_file() and not path.is_symlink()
        ),
        key=lambda path: str(path.relative_to(payload_directory)).lower(),
    )
    if not source_files:
        raise UpdateInstallationFailure("El paquete de actualización está vacío.")

    backup_directory.mkdir(parents=True, exist_ok=True)
    replaced: list[Path] = []
    created: list[Path] = []
    record = BackupRecord(backup_directory, (), ())
    try:
        for source in source_files:
            relative = source.relative_to(payload_directory)
            destination = install_directory / relative
            if destination.exists():
                if not destination.is_file() or destination.is_symlink():
                    raise UpdateInstallationFailure(
                        f"No se puede reemplazar la ruta existente: {relative}"
                    )
                backup = backup_directory / relative
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(destination, backup)
                replaced.append(relative)
            else:
                created.append(relative)
            record = BackupRecord(
                backup_directory,
                tuple(replaced),
                tuple(created),
            )
            _copy_for_replace(source, destination, replace_file)
    except Exception as error:
        try:
            rollback_installation(record, install_directory)
        except Exception as rollback_error:
            log_error(
                "Actualizaciones",
                "Falló también la restauración del backup.",
                rollback_error,
            )
            raise UpdateInstallationFailure(
                "No se pudo instalar la actualización ni restaurar completamente el backup."
            ) from error
        raise UpdateInstallationFailure(
            "No se pudo instalar la actualización. Se restauró la versión anterior."
        ) from error
    return record


def install_archive_package(
    package_path: Path,
    package_kind: str,
    install_directory: Path,
    main_name: str,
    working_directory: Path,
) -> tuple[BackupRecord, Path]:
    """Extrae ZIP/TAR, valida el ejecutable y aplica el payload."""
    extracted = working_directory / "extracted"
    if package_kind == "zip":
        safe_extract_zip(package_path, extracted)
    elif package_kind == "tar.gz":
        safe_extract_tar(package_path, extracted)
    else:
        raise UpdateInstallationFailure("Tipo de paquete no compatible con esta instalación.")
    payload_root = find_payload_root(extracted, main_name)
    validate_payload_files(payload_root, main_name)
    backup = working_directory / "backup"
    record = apply_payload(payload_root, install_directory, backup)
    return record, install_directory / main_name


def install_appimage_package(
    package_path: Path,
    target_path: Path,
    working_directory: Path,
) -> tuple[BackupRecord, Path]:
    """Reemplaza una AppImage conservando una copia reversible."""
    if not package_path.is_file():
        raise UpdateInstallationFailure("No se encontró la AppImage descargada.")
    backup_directory = working_directory / "backup"
    backup_directory.mkdir(parents=True, exist_ok=True)
    relative = Path(target_path.name)
    shutil.copy2(target_path, backup_directory / relative)
    record = BackupRecord(backup_directory, (relative,), ())
    try:
        _copy_for_replace(package_path, target_path, os.replace)
        target_path.chmod(target_path.stat().st_mode | 0o111)
    except Exception as error:
        rollback_installation(record, target_path.parent)
        raise UpdateInstallationFailure(
            "No se pudo instalar la AppImage. Se restauró la versión anterior."
        ) from error
    return record, target_path


def _process_exists(pid: int) -> bool:
    if pid <= 0:
        return False
    if sys.platform == "win32":
        import ctypes

        process = ctypes.windll.kernel32.OpenProcess(0x00100000, False, pid)
        if not process:
            return False
        ctypes.windll.kernel32.CloseHandle(process)
        return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def wait_for_parent_exit(
    parent_pid: int,
    timeout_seconds: float = PARENT_EXIT_TIMEOUT_SECONDS,
) -> None:
    """Espera sin terminal visible hasta que el proceso principal libere sus archivos."""
    deadline = time.monotonic() + max(1.0, timeout_seconds)
    while _process_exists(parent_pid):
        if time.monotonic() >= deadline:
            raise UpdateInstallationFailure(
                "La aplicación principal no se cerró a tiempo."
            )
        time.sleep(0.25)


def write_update_result(result_path: Path, success: bool, message: str) -> None:
    """Deja un mensaje atómico que la app mostrará después del reinicio."""
    result_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = result_path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps({"success": success, "message": message}, ensure_ascii=False),
        encoding="utf-8",
    )
    temporary.replace(result_path)


def launch_application(executable: Path, working_directory: Path) -> None:
    """Reabre la aplicación sin shell ni consola adicional."""
    kwargs: dict[str, object] = {
        "cwd": str(working_directory),
        "close_fds": True,
        "shell": False,
    }
    if sys.platform == "win32":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    else:
        kwargs["start_new_session"] = True
    subprocess.Popen([str(executable)], **kwargs)


def _parse_arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--package", required=True)
    parser.add_argument("--kind", choices=("zip", "tar.gz", "appimage"), required=True)
    parser.add_argument("--install-dir", required=True)
    parser.add_argument("--main-name", required=True)
    parser.add_argument("--parent-pid", required=True, type=int)
    parser.add_argument("--version", required=True)
    parser.add_argument("--result-path", required=True)
    parser.add_argument("--appimage-target")
    return parser.parse_args(argv)


def run_installer(argv: list[str] | None = None) -> int:
    """Punto de entrada del helper, separado del proceso principal."""
    arguments = _parse_arguments(argv)
    package_path = Path(arguments.package).resolve()
    install_directory = Path(arguments.install_dir).resolve()
    result_path = Path(arguments.result_path).resolve()
    original_main = (
        Path(arguments.appimage_target).resolve()
        if arguments.appimage_target
        else install_directory / arguments.main_name
    )
    record: BackupRecord | None = None

    log_info("Actualizaciones", f"Inicio de instalación de v{arguments.version}.")
    try:
        wait_for_parent_exit(arguments.parent_pid)
        with TemporaryDirectory(
            prefix=".install-",
            dir=package_path.parent,
        ) as temporary_directory:
            working_directory = Path(temporary_directory)
            if arguments.kind == "appimage":
                if not arguments.appimage_target:
                    raise UpdateInstallationFailure(
                        "No se indicó la AppImage que debe reemplazarse."
                    )
                record, new_main = install_appimage_package(
                    package_path,
                    original_main,
                    working_directory,
                )
            else:
                record, new_main = install_archive_package(
                    package_path,
                    arguments.kind,
                    install_directory,
                    arguments.main_name,
                    working_directory,
                )
            log_info("Actualizaciones", f"Backup creado: {record.backup_directory}")
            log_info("Actualizaciones", "Archivos reemplazados correctamente.")
            write_update_result(
                result_path,
                True,
                f"Kenji Music Downloader se actualizó correctamente a v{arguments.version}.",
            )
            try:
                launch_application(new_main, new_main.parent)
            except Exception as launch_error:
                rollback_installation(record, install_directory)
                raise UpdateInstallationFailure(
                    "No se pudo abrir la versión nueva. Se restauró la versión anterior."
                ) from launch_error
            log_info("Actualizaciones", f"Reinicio iniciado: {new_main}")
        try:
            package_path.unlink(missing_ok=True)
        except OSError:
            pass
        return 0
    except Exception as error:
        message = str(error) or "No se pudo instalar la actualización."
        log_error("Actualizaciones", message, error)
        try:
            write_update_result(result_path, False, message)
        except OSError:
            pass
        if original_main.is_file() and not _process_exists(arguments.parent_pid):
            try:
                launch_application(original_main, original_main.parent)
            except OSError as restart_error:
                log_error(
                    "Actualizaciones",
                    "No se pudo reabrir la versión anterior.",
                    restart_error,
                )
        return 1


if __name__ == "__main__":
    raise SystemExit(run_installer())
