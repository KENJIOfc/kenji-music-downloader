"""Generación reproducible de manifests para paquetes de una release."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

from src.config import APP_VERSION


RELEASE_PACKAGE_NAME = "YugenAudio"
PLATFORM_ARTIFACTS = {
    "windows-x64": (
        (f"{RELEASE_PACKAGE_NAME}-v{{version}}-Windows-x64.zip",),
        "update-windows.json",
    ),
    "linux-x64": (
        (
            f"{RELEASE_PACKAGE_NAME}-v{{version}}-Linux-x64.AppImage",
            f"{RELEASE_PACKAGE_NAME}-v{{version}}-Linux-x64.tar.gz",
            f"{RELEASE_PACKAGE_NAME}-v{{version}}-Linux-x64.zip",
        ),
        "update-linux.json",
    ),
}
COMBINED_MANIFEST_NAME = "update.json"


class ReleaseManifestError(RuntimeError):
    """No existen paquetes válidos suficientes para crear un manifest."""


@dataclass(frozen=True, slots=True)
class GeneratedManifest:
    """Manifest escrito y plataformas incluidas en él."""

    path: Path
    platforms: tuple[str, ...]


def calculate_sha256(path: Path) -> str:
    """Calcula SHA-256 leyendo por bloques y sin cargar el paquete completo."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, payload: dict) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _select_platform_asset(
    dist: Path,
    artifact_templates: tuple[str, ...],
    version: str,
) -> tuple[str, Path] | None:
    for asset_template in artifact_templates:
        asset_name = asset_template.format(version=version)
        asset_path = dist / asset_name
        if asset_path.is_file() and not asset_path.is_symlink():
            return asset_name, asset_path
    return None


def generate_release_manifests(
    dist_directory: Path,
    version: str = APP_VERSION,
) -> tuple[GeneratedManifest, ...]:
    """Genera manifests específicos y combina ambos cuando están presentes."""
    dist = Path(dist_directory).resolve()
    if not dist.is_dir():
        raise ReleaseManifestError(f"No existe la carpeta de paquetes: {dist}")

    notes = f"Actualización de Yūgen Audio v{version}"
    assets: dict[str, dict[str, str]] = {}
    generated: list[GeneratedManifest] = []

    for platform_key, (artifact_templates, manifest_name) in PLATFORM_ARTIFACTS.items():
        manifest_path = dist / manifest_name
        selected_asset = _select_platform_asset(dist, artifact_templates, version)
        if selected_asset is None:
            manifest_path.unlink(missing_ok=True)
            continue
        asset_name, asset_path = selected_asset

        asset_data = {
            "name": asset_name,
            "sha256": calculate_sha256(asset_path),
            "size": asset_path.stat().st_size,
        }
        assets[platform_key] = asset_data
        _write_json(
            manifest_path,
            {
                "version": version,
                "platform": platform_key,
                "asset": asset_data,
                "notes": notes,
            },
        )
        generated.append(GeneratedManifest(manifest_path, (platform_key,)))

    if not assets:
        raise ReleaseManifestError(
            f"No se encontraron paquetes de Yūgen Audio v{version} en {dist}."
        )

    combined_path = dist / COMBINED_MANIFEST_NAME
    if set(assets) == set(PLATFORM_ARTIFACTS):
        _write_json(
            combined_path,
            {
                "version": version,
                "assets": assets,
                "notes": notes,
            },
        )
        generated.append(
            GeneratedManifest(combined_path, tuple(PLATFORM_ARTIFACTS))
        )
    else:
        # Nunca se conserva un combinado obsoleto o incompleto.
        combined_path.unlink(missing_ok=True)

    return tuple(generated)
