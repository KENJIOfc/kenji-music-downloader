"""Pruebas de manifests específicos y combinado para una release."""

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from src.config import APP_VERSION
from src.release_manifest import (
    ReleaseManifestError,
    generate_release_manifests,
)


VERSION = APP_VERSION
WINDOWS_NAME = f"KenjiMusicDownloader-v{VERSION}-Windows-x64.zip"
LINUX_NAME = f"KenjiMusicDownloader-v{VERSION}-Linux-x64.tar.gz"


class ReleaseManifestTests(unittest.TestCase):
    def test_release_version_is_centralized(self) -> None:
        self.assertEqual(APP_VERSION, "1.0.7")

    def test_generates_windows_manifest_with_real_hash(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            dist = Path(temporary)
            content = b"paquete windows real"
            (dist / WINDOWS_NAME).write_bytes(content)

            generated = generate_release_manifests(dist, VERSION)
            manifest = json.loads(
                (dist / "update-windows.json").read_text(encoding="utf-8")
            )

            self.assertEqual(len(generated), 1)
            self.assertEqual(manifest["version"], VERSION)
            self.assertEqual(manifest["platform"], "windows-x64")
            self.assertEqual(manifest["asset"]["name"], WINDOWS_NAME)
            self.assertEqual(
                manifest["asset"]["sha256"],
                hashlib.sha256(content).hexdigest(),
            )
            self.assertFalse((dist / "update.json").exists())

    def test_generates_linux_manifest_with_real_hash(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            dist = Path(temporary)
            content = b"paquete linux real"
            (dist / LINUX_NAME).write_bytes(content)

            generate_release_manifests(dist, VERSION)
            manifest = json.loads(
                (dist / "update-linux.json").read_text(encoding="utf-8")
            )

            self.assertEqual(manifest["platform"], "linux-x64")
            self.assertEqual(manifest["asset"]["name"], LINUX_NAME)
            self.assertEqual(
                manifest["asset"]["sha256"],
                hashlib.sha256(content).hexdigest(),
            )

    def test_generates_combined_manifest_when_both_packages_exist(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            dist = Path(temporary)
            windows_content = b"windows"
            linux_content = b"linux"
            (dist / WINDOWS_NAME).write_bytes(windows_content)
            (dist / LINUX_NAME).write_bytes(linux_content)

            generated = generate_release_manifests(dist, VERSION)
            combined = json.loads(
                (dist / "update.json").read_text(encoding="utf-8")
            )

            self.assertEqual(len(generated), 3)
            self.assertEqual(
                set(combined["assets"]),
                {"windows-x64", "linux-x64"},
            )
            self.assertEqual(
                combined["assets"]["windows-x64"]["sha256"],
                hashlib.sha256(windows_content).hexdigest(),
            )
            self.assertEqual(
                combined["assets"]["linux-x64"]["sha256"],
                hashlib.sha256(linux_content).hexdigest(),
            )

    def test_removes_stale_combined_manifest_when_only_one_package_exists(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            dist = Path(temporary)
            (dist / WINDOWS_NAME).write_bytes(b"windows")
            (dist / "update.json").write_text("obsoleto", encoding="utf-8")

            generate_release_manifests(dist, VERSION)

            self.assertFalse((dist / "update.json").exists())

    def test_fails_clearly_when_no_package_exists(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(ReleaseManifestError, "No se encontraron"):
                generate_release_manifests(Path(temporary), VERSION)


if __name__ == "__main__":
    unittest.main()
