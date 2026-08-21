"""CLI para generar manifests de release desde la carpeta dist."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import APP_VERSION  # noqa: E402
from src.release_manifest import (  # noqa: E402
    ReleaseManifestError,
    calculate_sha256,
    generate_release_manifests,
)


def _parse_arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Genera manifests con hashes reales para GitHub Releases.",
    )
    parser.add_argument(
        "--dist",
        type=Path,
        default=PROJECT_ROOT / "dist",
        help="Carpeta que contiene los paquetes (predeterminado: dist).",
    )
    return parser.parse_args(argv)


def _configure_console_encoding() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except AttributeError:
            pass


def _asset_names_from_manifest(path: Path) -> dict[str, str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return {}

    assets = payload.get("assets")
    if isinstance(assets, dict):
        return {
            platform_key: asset["name"]
            for platform_key, asset in assets.items()
            if isinstance(asset, dict) and isinstance(asset.get("name"), str)
        }

    platform_key = payload.get("platform")
    asset = payload.get("asset")
    if isinstance(platform_key, str) and isinstance(asset, dict):
        asset_name = asset.get("name")
        if isinstance(asset_name, str):
            return {platform_key: asset_name}
    return {}


def main(argv: list[str] | None = None) -> int:
    _configure_console_encoding()
    arguments = _parse_arguments(argv)
    dist = arguments.dist.resolve()
    try:
        generated = generate_release_manifests(dist, APP_VERSION)
    except (ReleaseManifestError, OSError) as error:
        print(f"ERROR: {error}")
        return 1

    print(f"Versión: {APP_VERSION}")
    for manifest in generated:
        print(f"Manifest creado: {manifest.path}")
        for platform_key, asset_name in _asset_names_from_manifest(manifest.path).items():
            if platform_key not in manifest.platforms:
                continue
            asset_path = dist / asset_name
            print(f"  {platform_key}: {asset_path.name}")
            print(f"  SHA-256: {calculate_sha256(asset_path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
