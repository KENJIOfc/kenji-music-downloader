"""Pruebas deterministas del cliente de GitHub Releases."""

import json
import socket
import unittest
from urllib.error import HTTPError, URLError

from src.updates import (
    GITHUB_RELEASES_URL,
    InvalidVersionError,
    check_for_updates,
    compare_versions,
    parse_release_payload,
)


class FakeResponse:
    """Respuesta mínima compatible con urllib para evitar acceso de red."""

    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self, _limit: int = -1) -> bytes:
        return self.payload


def response_opener(payload: object):
    encoded = json.dumps(payload).encode("utf-8")

    def opener(_request, timeout: float):
        if timeout <= 0:
            raise AssertionError("La consulta debe usar un timeout positivo.")
        return FakeResponse(encoded)

    return opener


class VersionComparisonTests(unittest.TestCase):
    def test_requested_version_comparisons(self) -> None:
        comparisons = [
            ("1.0.0", "1.0.0", 0),
            ("v1.0.0", "1.0.0", 0),
            ("v1.0.1", "v1.0.0", 1),
            ("v1.1.0", "v1.0.9", 1),
            ("v2.0.0", "v1.9.9", 1),
            ("v1.0.10", "v1.0.2", 1),
        ]
        for left, right, expected in comparisons:
            with self.subTest(left=left, right=right):
                self.assertEqual(compare_versions(left, right), expected)

    def test_invalid_version_raises_clear_error(self) -> None:
        with self.assertRaises(InvalidVersionError):
            compare_versions("release-final", "1.0.0")


class UpdateResultTests(unittest.TestCase):
    def _payload(self, tag_name: str) -> dict:
        return {
            "tag_name": tag_name,
            "html_url": (
                "https://github.com/KENJIOFC/kenji-music-downloader/"
                f"releases/tag/{tag_name}"
            ),
            "name": f"Kenji {tag_name}",
            "body": "Notas de prueba",
            "published_at": "2026-06-21T12:00:00Z",
            "assets": [
                {
                    "name": "kenji-music-downloader.exe",
                    "browser_download_url": (
                        "https://github.com/KENJIOFC/kenji-music-downloader/"
                        f"releases/download/{tag_name}/kenji-music-downloader.exe"
                    ),
                    "size": 1234,
                    "content_type": "application/octet-stream",
                }
            ],
        }

    def test_remote_greater_reports_update(self) -> None:
        result = parse_release_payload(self._payload("v1.0.1"), "1.0.0")
        self.assertTrue(result.success)
        self.assertTrue(result.update_available)
        self.assertEqual(result.latest_version, "1.0.1")
        self.assertEqual(len(result.assets), 1)

    def test_equal_remote_reports_no_update(self) -> None:
        result = parse_release_payload(self._payload("v1.0.0"), "1.0.0")
        self.assertTrue(result.success)
        self.assertFalse(result.update_available)

    def test_older_remote_reports_no_update(self) -> None:
        result = parse_release_payload(self._payload("v0.9.9"), "1.0.0")
        self.assertTrue(result.success)
        self.assertFalse(result.update_available)

    def test_missing_tag_is_controlled(self) -> None:
        result = parse_release_payload({}, "1.0.0")
        self.assertFalse(result.success)
        self.assertEqual(result.error_type, "missing_tag")

    def test_invalid_remote_version_is_controlled(self) -> None:
        result = parse_release_payload(self._payload("version-final"), "1.0.0")
        self.assertFalse(result.success)
        self.assertEqual(result.error_type, "invalid_version")

    def test_no_releases_http_404_is_controlled(self) -> None:
        def opener(request, timeout: float):
            raise HTTPError(request.full_url, 404, "Not Found", {}, None)

        result = check_for_updates("1.0.0", opener=opener)
        self.assertFalse(result.success)
        self.assertEqual(result.error_type, "no_releases")

    def test_connection_failure_is_controlled(self) -> None:
        def opener(_request, timeout: float):
            raise URLError("sin conexión")

        result = check_for_updates("1.0.0", opener=opener)
        self.assertFalse(result.success)
        self.assertEqual(result.error_type, "connection_error")

    def test_timeout_is_controlled(self) -> None:
        def opener(_request, timeout: float):
            raise socket.timeout("timeout")

        result = check_for_updates("1.0.0", opener=opener)
        self.assertFalse(result.success)
        self.assertEqual(result.error_type, "timeout")

    def test_rate_limit_is_controlled(self) -> None:
        def opener(request, timeout: float):
            raise HTTPError(request.full_url, 403, "Forbidden", {}, None)

        result = check_for_updates("1.0.0", opener=opener)
        self.assertFalse(result.success)
        self.assertEqual(result.error_type, "rate_limit")

    def test_invalid_json_is_controlled(self) -> None:
        result = check_for_updates(
            "1.0.0",
            opener=lambda _request, timeout: FakeResponse(b"{json roto"),
        )
        self.assertFalse(result.success)
        self.assertEqual(result.error_type, "invalid_json")

    def test_valid_api_response_uses_release_url(self) -> None:
        result = check_for_updates(
            "1.0.0",
            opener=response_opener(self._payload("v1.1.0")),
        )
        self.assertTrue(result.success)
        self.assertTrue(result.update_available)
        self.assertNotEqual(result.release_url, GITHUB_RELEASES_URL)


if __name__ == "__main__":
    unittest.main()
