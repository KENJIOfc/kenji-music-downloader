"""Pruebas del diagnóstico no destructivo del actualizador."""

from io import BytesIO
import hashlib
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from src.update_diagnostics import run_update_dry_run
from src.update_manager import (
    UpdateIntegrityError,
    UpdatePackageError,
    validate_release_manifest,
)
from src.updates import ReleaseAsset, UpdateResult


RELEASE_PREFIX = (
    "https://github.com/KENJIOFC/kenji-music-downloader/"
    "releases/download/v1.0.6/"
)
WINDOWS_NAME = "KenjiMusicDownloader-v1.0.6-Windows-x64.zip"
LINUX_NAME = "KenjiMusicDownloader-v1.0.6-Linux-x64.tar.gz"


class FakeResponse(BytesIO):
    def __init__(self, content: bytes) -> None:
        super().__init__(content)
        self.headers = {"Content-Length": str(len(content))}


def make_asset(name: str, size: int = 100) -> ReleaseAsset:
    return ReleaseAsset(name, RELEASE_PREFIX + name, size=size)


def make_result() -> UpdateResult:
    return UpdateResult(
        success=True,
        update_available=False,
        current_version="1.0.6",
        latest_version="1.0.6",
        assets=(
            make_asset(WINDOWS_NAME),
            make_asset(LINUX_NAME),
            make_asset("update.json"),
        ),
    )


def make_manifest(windows_hash: str, linux_hash: str) -> dict:
    return {
        "version": "1.0.6",
        "assets": {
            "windows-x64": {"name": WINDOWS_NAME, "sha256": windows_hash},
            "linux-x64": {"name": LINUX_NAME, "sha256": linux_hash},
        },
    }


def make_windows_zip() -> bytes:
    output = BytesIO()
    with ZipFile(output, "w") as archive:
        archive.writestr("KenjiMusicDownloader.exe", b"main-windows")
        archive.writestr("KenjiUpdateInstaller.exe", b"helper-windows")
        archive.writestr("README.md", b"readme")
    return output.getvalue()


def make_linux_tar() -> bytes:
    output = BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz") as archive:
        for name, content in (
            ("KenjiMusicDownloader", b"main-linux"),
            ("KenjiUpdateInstaller", b"helper-linux"),
            ("README.md", b"readme"),
        ):
            member = tarfile.TarInfo(name)
            member.size = len(content)
            member.mode = 0o755 if name != "README.md" else 0o644
            archive.addfile(member, BytesIO(content))
    return output.getvalue()


class UpdateDiagnosticsTests(unittest.TestCase):
    def setUp(self) -> None:
        patches = (
            patch("src.update_manager.log_info"),
            patch("src.update_manager.log_error"),
            patch("src.update_diagnostics.log_info"),
            patch("src.update_diagnostics.log_error"),
        )
        for current_patch in patches:
            current_patch.start()
            self.addCleanup(current_patch.stop)

    def test_manifest_validates_windows_and_linux_entries(self) -> None:
        manifest = make_manifest("a" * 64, "b" * 64)
        packages = validate_release_manifest(
            make_result(),
            opener=lambda _request, timeout: FakeResponse(
                json.dumps(manifest).encode("utf-8")
            ),
        )
        self.assertEqual(set(packages), {"windows-x64", "linux-x64"})
        self.assertEqual(packages["windows-x64"].asset.name, WINDOWS_NAME)
        self.assertEqual(packages["linux-x64"].asset.name, LINUX_NAME)

    def test_missing_linux_manifest_entry_is_controlled(self) -> None:
        manifest = make_manifest("a" * 64, "b" * 64)
        del manifest["assets"]["linux-x64"]
        with self.assertRaisesRegex(UpdatePackageError, "este sistema operativo"):
            validate_release_manifest(
                make_result(),
                opener=lambda _request, timeout: FakeResponse(
                    json.dumps(manifest).encode("utf-8")
                ),
            )

    def test_windows_dry_run_verifies_and_does_not_launch_installer(self) -> None:
        archive = make_windows_zip()
        linux_hash = hashlib.sha256(make_linux_tar()).hexdigest()
        manifest = make_manifest(hashlib.sha256(archive).hexdigest(), linux_hash)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            protected = root / "instalacion-real.txt"
            protected.write_text("sin cambios", encoding="utf-8")
            with patch("src.update_manager.subprocess.Popen") as popen:
                result = run_update_dry_run(
                    make_result(),
                    root / "dry-run",
                    system_name="Windows",
                    machine_name="AMD64",
                    manifest_opener=lambda _request, timeout: FakeResponse(
                        json.dumps(manifest).encode("utf-8")
                    ),
                    download_opener=lambda _request, timeout: FakeResponse(archive),
                )
            self.assertEqual(protected.read_text(encoding="utf-8"), "sin cambios")
            popen.assert_not_called()
        self.assertEqual(result.platform_key, "windows-x64")
        self.assertEqual(result.asset_name, WINDOWS_NAME)
        self.assertEqual(result.expected_sha256, result.calculated_sha256)

    def test_windows_dry_run_uses_specific_manifest_fallback(self) -> None:
        archive = make_windows_zip()
        expected_hash = hashlib.sha256(archive).hexdigest()
        manifest = {
            "version": "1.0.6",
            "platform": "windows-x64",
            "asset": {"name": WINDOWS_NAME, "sha256": expected_hash},
            "notes": "Fallback Windows",
        }
        release = UpdateResult(
            success=True,
            update_available=False,
            current_version="1.0.6",
            latest_version="1.0.6",
            assets=(
                make_asset(WINDOWS_NAME),
                make_asset("update-windows.json"),
            ),
        )
        with tempfile.TemporaryDirectory() as temporary:
            result = run_update_dry_run(
                release,
                Path(temporary),
                system_name="Windows",
                machine_name="AMD64",
                manifest_opener=lambda _request, timeout: FakeResponse(
                    json.dumps(manifest).encode("utf-8")
                ),
                download_opener=lambda _request, timeout: FakeResponse(archive),
            )
        self.assertEqual(result.asset_name, WINDOWS_NAME)
        self.assertEqual(result.calculated_sha256, expected_hash)

    def test_linux_dry_run_selects_tar_and_validates_payload(self) -> None:
        windows_archive = make_windows_zip()
        archive = make_linux_tar()
        manifest = make_manifest(
            hashlib.sha256(windows_archive).hexdigest(),
            hashlib.sha256(archive).hexdigest(),
        )
        with tempfile.TemporaryDirectory() as temporary:
            result = run_update_dry_run(
                make_result(),
                Path(temporary),
                system_name="Linux",
                machine_name="x86_64",
                manifest_opener=lambda _request, timeout: FakeResponse(
                    json.dumps(manifest).encode("utf-8")
                ),
                download_opener=lambda _request, timeout: FakeResponse(archive),
            )
        self.assertEqual(result.platform_key, "linux-x64")
        self.assertEqual(result.asset_name, LINUX_NAME)
        self.assertIn("KenjiMusicDownloader", result.extracted_files)
        self.assertIn("KenjiUpdateInstaller", result.extracted_files)

    def test_dry_run_rejects_hash_mismatch_before_extraction(self) -> None:
        archive = make_windows_zip()
        manifest = make_manifest("0" * 64, "b" * 64)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaises(UpdateIntegrityError):
                run_update_dry_run(
                    make_result(),
                    root,
                    system_name="Windows",
                    machine_name="AMD64",
                    manifest_opener=lambda _request, timeout: FakeResponse(
                        json.dumps(manifest).encode("utf-8")
                    ),
                    download_opener=lambda _request, timeout: FakeResponse(archive),
                )
            self.assertFalse((root / "extracted").exists())


if __name__ == "__main__":
    unittest.main()
