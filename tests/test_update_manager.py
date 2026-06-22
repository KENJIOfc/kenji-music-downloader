"""Pruebas de selección, descarga e inicio del actualizador automático."""

from io import BytesIO
import hashlib
import json
from pathlib import Path
import tempfile
from threading import Event
import unittest
from unittest.mock import patch

from src.update_manager import (
    DownloadedUpdate,
    InstallationContext,
    UpdateIntegrityError,
    UpdateInstallError,
    UpdatePackage,
    UpdatePackageError,
    detect_platform_key,
    download_update,
    ensure_installation_writable,
    launch_update_installer,
    prepare_update_package,
    select_release_asset,
)
from src.updates import ReleaseAsset, UpdateResult


RELEASE_PREFIX = (
    "https://github.com/KENJIOFC/kenji-music-downloader/"
    "releases/download/v1.0.4/"
)


class FakeResponse(BytesIO):
    def __init__(self, content: bytes) -> None:
        super().__init__(content)
        self.headers = {"Content-Length": str(len(content))}


def make_asset(name: str, size: int = 100) -> ReleaseAsset:
    return ReleaseAsset(name, RELEASE_PREFIX + name, size=size)


def make_result(*assets: ReleaseAsset) -> UpdateResult:
    return UpdateResult(
        success=True,
        update_available=True,
        current_version="1.0.3",
        latest_version="1.0.4",
        release_notes="Cambios de prueba",
        assets=tuple(assets),
    )


class UpdateManagerTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.info_patcher = patch("src.update_manager.log_info")
        self.error_patcher = patch("src.update_manager.log_error")
        self.info_patcher.start()
        self.error_patcher.start()
        self.addCleanup(self.info_patcher.stop)
        self.addCleanup(self.error_patcher.stop)


class AssetSelectionTests(UpdateManagerTestCase):
    def test_selects_windows_zip(self) -> None:
        expected = make_asset("KenjiMusicDownloader-v1.0.4-Windows-x64.zip")
        platform_key, asset, kind = select_release_asset(
            make_result(expected),
            "Windows",
            "AMD64",
        )
        self.assertEqual(platform_key, "windows-x64")
        self.assertEqual(asset, expected)
        self.assertEqual(kind, "zip")

    def test_linux_prefers_appimage_then_tar_and_zip(self) -> None:
        zip_asset = make_asset("KenjiMusicDownloader-v1.0.4-Linux-x64.zip")
        tar_asset = make_asset("KenjiMusicDownloader-v1.0.4-Linux-x64.tar.gz")
        appimage = make_asset("KenjiMusicDownloader-v1.0.4-Linux-x64.AppImage")

        _platform_key, selected, kind = select_release_asset(
            make_result(zip_asset, tar_asset, appimage),
            "Linux",
            "x86_64",
        )

        self.assertEqual(selected, appimage)
        self.assertEqual(kind, "appimage")

    def test_missing_asset_is_controlled(self) -> None:
        with self.assertRaisesRegex(UpdatePackageError, "No hay paquete"):
            select_release_asset(make_result(), "Windows", "AMD64")

    def test_unsupported_architecture_is_controlled(self) -> None:
        with self.assertRaises(UpdatePackageError):
            detect_platform_key("Linux", "arm64")

    def test_manifest_provides_sha256(self) -> None:
        windows_name = "KenjiMusicDownloader-v1.0.4-Windows-x64.zip"
        manifest = {
            "version": "1.0.4",
            "assets": {
                "windows-x64": {
                    "name": windows_name,
                    "sha256": "a" * 64,
                }
            },
            "notes": "Notas del manifest",
        }
        result = make_result(
            make_asset(windows_name),
            make_asset("update.json"),
        )

        package = prepare_update_package(
            result,
            "Windows",
            "AMD64",
            opener=lambda _request, timeout: FakeResponse(
                json.dumps(manifest).encode("utf-8")
            ),
        )

        self.assertEqual(package.expected_sha256, "a" * 64)
        self.assertEqual(package.notes, "Notas del manifest")


class UpdateDownloadTests(UpdateManagerTestCase):
    def test_simulated_download_verifies_sha256(self) -> None:
        content = b"paquete de actualizacion"
        expected_hash = hashlib.sha256(content).hexdigest()
        asset = make_asset("KenjiMusicDownloader-v1.0.4-Windows-x64.zip", len(content))
        package = UpdatePackage(
            "1.0.4",
            "windows-x64",
            asset,
            "zip",
            expected_hash,
        )
        progress = []

        with tempfile.TemporaryDirectory() as temporary_directory:
            result = download_update(
                package,
                progress_callback=progress.append,
                opener=lambda _request, timeout: FakeResponse(content),
                updates_directory=Path(temporary_directory),
            )

            self.assertTrue(result.path.is_file())
            self.assertTrue(result.hash_verified)
            self.assertEqual(result.calculated_sha256, expected_hash)
        self.assertTrue(progress)
        self.assertEqual(progress[-1].percentage, 100.0)

    def test_hash_mismatch_removes_partial_download(self) -> None:
        asset = make_asset("KenjiMusicDownloader-v1.0.4-Windows-x64.zip")
        package = UpdatePackage(
            "1.0.4",
            "windows-x64",
            asset,
            "zip",
            "0" * 64,
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            with self.assertRaises(UpdateIntegrityError):
                download_update(
                    package,
                    opener=lambda _request, timeout: FakeResponse(b"contenido distinto"),
                    updates_directory=directory,
                )
            self.assertEqual(list(directory.iterdir()), [])

    def test_cancelled_download_is_controlled(self) -> None:
        asset = make_asset("KenjiMusicDownloader-v1.0.4-Windows-x64.zip")
        package = UpdatePackage("1.0.4", "windows-x64", asset, "zip")
        cancel_event = Event()
        cancel_event.set()
        with tempfile.TemporaryDirectory() as temporary_directory:
            from src.update_manager import UpdateCancelledError

            with self.assertRaises(UpdateCancelledError):
                download_update(
                    package,
                    cancel_event=cancel_event,
                    opener=lambda _request, timeout: FakeResponse(b"contenido"),
                    updates_directory=Path(temporary_directory),
                )


class InstallerLaunchTests(UpdateManagerTestCase):
    def test_insufficient_permissions_are_reported(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            invalid_directory = Path(temporary_directory) / "archivo"
            invalid_directory.write_text("no es carpeta", encoding="utf-8")
            context = InstallationContext(
                "archive",
                "windows-x64",
                invalid_directory,
                invalid_directory / "KenjiMusicDownloader.exe",
                invalid_directory / "KenjiUpdateInstaller.exe",
            )
            with self.assertRaisesRegex(UpdateInstallError, "no permite escritura"):
                ensure_installation_writable(context)

    def test_helper_launch_never_uses_shell(self) -> None:
        calls = []

        def fake_popen(command, **kwargs):
            calls.append((command, kwargs))
            return object()

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            install_directory = root / "app"
            updates_directory = root / "updates"
            install_directory.mkdir()
            updates_directory.mkdir()
            helper = install_directory / "KenjiUpdateInstaller.exe"
            helper.write_bytes(b"helper")
            main = install_directory / "KenjiMusicDownloader.exe"
            main.write_bytes(b"main")
            package_path = updates_directory / "KenjiMusicDownloader-v1.0.4-Windows-x64.zip"
            package_path.write_bytes(b"zip")
            package = UpdatePackage(
                "1.0.4",
                "windows-x64",
                make_asset(package_path.name),
                "zip",
            )
            downloaded = DownloadedUpdate(package, package_path, "a" * 64, False)
            context = InstallationContext(
                "archive",
                "windows-x64",
                install_directory,
                main,
                helper,
            )

            launch_update_installer(
                downloaded,
                context=context,
                parent_pid=123,
                popen=fake_popen,
            )

        self.assertEqual(len(calls), 1)
        _command, kwargs = calls[0]
        self.assertIs(kwargs["shell"], False)
        self.assertIn("creationflags", kwargs)


if __name__ == "__main__":
    unittest.main()
