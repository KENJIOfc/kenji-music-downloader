"""CLI para generar manifests de release desde la carpeta dist."""

from __future__ import annotations

import argparse
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


def main(argv: list[str] | None = None) -> int:
    arguments = _parse_arguments(argv)
    try:
        generated = generate_release_manifests(arguments.dist, APP_VERSION)
    except (ReleaseManifestError, OSError) as error:
        print(f"ERROR: {error}")
        return 1

    print(f"Versión: {APP_VERSION}")
    for manifest in generated:
        print(f"Manifest creado: {manifest.path}")
        for platform_key in manifest.platforms:
            platform_data = (
                "KenjiMusicDownloader-"
                f"v{APP_VERSION}-{'Windows-x64.zip' if platform_key == 'windows-x64' else 'Linux-x64.tar.gz'}"
            )
            asset_path = arguments.dist.resolve() / platform_data
            print(f"  {platform_key}: {asset_path.name}")
            print(f"  SHA-256: {calculate_sha256(asset_path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
