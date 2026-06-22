"""Pruebas de extracción, backup y rollback del helper independiente."""

from io import BytesIO
import os
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from src.update_installer import (
    UpdateInstallationFailure,
    apply_payload,
    run_installer,
    safe_extract_tar,
    safe_extract_zip,
)


class SafeExtractionTests(unittest.TestCase):
    def test_extracts_safe_zip(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            archive_path = root / "update.zip"
            with ZipFile(archive_path, "w") as archive:
                archive.writestr("package/KenjiMusicDownloader.exe", b"nuevo")

            destination = root / "extracted"
            safe_extract_zip(archive_path, destination)

            self.assertEqual(
                (destination / "package" / "KenjiMusicDownloader.exe").read_bytes(),
                b"nuevo",
            )

    def test_zip_path_traversal_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            archive_path = root / "unsafe.zip"
            with ZipFile(archive_path, "w") as archive:
                archive.writestr("../../fuera.exe", b"malicioso")

            with self.assertRaisesRegex(UpdateInstallationFailure, "ruta insegura"):
                safe_extract_zip(archive_path, root / "extracted")
            self.assertFalse((root / "fuera.exe").exists())

    def test_extracts_safe_tar_gz(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            archive_path = root / "update.tar.gz"
            content = b"linux"
            info = tarfile.TarInfo("package/KenjiMusicDownloader")
            info.size = len(content)
            with tarfile.open(archive_path, "w:gz") as archive:
                archive.addfile(info, BytesIO(content))

            destination = root / "extracted"
            safe_extract_tar(archive_path, destination)

            self.assertEqual(
                (destination / "package" / "KenjiMusicDownloader").read_bytes(),
                content,
            )

    def test_tar_path_traversal_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            archive_path = root / "unsafe.tar.gz"
            content = b"malicioso"
            info = tarfile.TarInfo("../fuera")
            info.size = len(content)
            with tarfile.open(archive_path, "w:gz") as archive:
                archive.addfile(info, BytesIO(content))

            with self.assertRaisesRegex(UpdateInstallationFailure, "ruta insegura"):
                safe_extract_tar(archive_path, root / "extracted")


class BackupRollbackTests(unittest.TestCase):
    def test_partial_failure_restores_previous_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            payload = root / "payload"
            install = root / "install"
            backup = root / "backup"
            payload.mkdir()
            install.mkdir()
            (payload / "a.exe").write_bytes(b"nuevo-a")
            (payload / "b.exe").write_bytes(b"nuevo-b")
            (install / "a.exe").write_bytes(b"anterior-a")
            (install / "b.exe").write_bytes(b"anterior-b")
            calls = 0

            def failing_replacer(source: Path, destination: Path) -> None:
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise PermissionError("fallo simulado")
                os.replace(source, destination)

            with self.assertRaisesRegex(
                UpdateInstallationFailure,
                "restauró la versión anterior",
            ):
                apply_payload(payload, install, backup, replacer=failing_replacer)

            self.assertEqual((install / "a.exe").read_bytes(), b"anterior-a")
            self.assertEqual((install / "b.exe").read_bytes(), b"anterior-b")

    def test_successful_payload_preserves_unrelated_user_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            payload = root / "payload"
            install = root / "install"
            payload.mkdir()
            install.mkdir()
            (payload / "KenjiMusicDownloader.exe").write_bytes(b"nuevo")
            (install / "KenjiMusicDownloader.exe").write_bytes(b"anterior")
            (install / "cancion.mp3").write_bytes(b"usuario")

            apply_payload(payload, install, root / "backup")

            self.assertEqual(
                (install / "KenjiMusicDownloader.exe").read_bytes(),
                b"nuevo",
            )
            self.assertEqual((install / "cancion.mp3").read_bytes(), b"usuario")

    @patch("src.update_installer.log_info")
    @patch("src.update_installer.log_error")
    @patch("src.update_installer.launch_application")
    def test_helper_end_to_end_replaces_and_preserves_user_data(
        self,
        launch_mock,
        _log_error_mock,
        _log_info_mock,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            install = root / "app"
            install.mkdir()
            (install / "KenjiMusicDownloader.exe").write_bytes(b"anterior")
            (install / "KenjiUpdateInstaller.exe").write_bytes(b"helper anterior")
            (install / "usuario.mp3").write_bytes(b"audio")
            package = root / "update.zip"
            with ZipFile(package, "w") as archive:
                archive.writestr("KenjiMusicDownloader.exe", b"nuevo")
                archive.writestr("KenjiUpdateInstaller.exe", b"helper nuevo")
            result_path = root / "last_update_result.json"

            exit_code = run_installer(
                [
                    "--package",
                    str(package),
                    "--kind",
                    "zip",
                    "--install-dir",
                    str(install),
                    "--main-name",
                    "KenjiMusicDownloader.exe",
                    "--parent-pid",
                    "0",
                    "--version",
                    "1.0.4",
                    "--result-path",
                    str(result_path),
                ]
            )

            self.assertEqual(exit_code, 0)
            self.assertEqual(
                (install / "KenjiMusicDownloader.exe").read_bytes(),
                b"nuevo",
            )
            self.assertEqual(
                (install / "KenjiUpdateInstaller.exe").read_bytes(),
                b"helper nuevo",
            )
            self.assertEqual((install / "usuario.mp3").read_bytes(), b"audio")
            self.assertTrue(result_path.is_file())
            launch_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
