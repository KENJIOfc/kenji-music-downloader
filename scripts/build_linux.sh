#!/usr/bin/env bash
set -euo pipefail

# Construye el ejecutable desde la raíz del proyecto, sin depender de la ruta local.
project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"

python -m unittest discover -s tests -v
python -m PyInstaller --clean --noconfirm kenji-music-downloader.spec

version="$(python -c 'from src.config import APP_VERSION; print(APP_VERSION)')"
asset_name="KenjiMusicDownloader-v${version}-Linux-x64.tar.gz"
release_stage="$project_root/build/release-linux"
rm -rf "$release_stage"
mkdir -p "$release_stage"
cp dist/KenjiMusicDownloader "$release_stage/"
cp dist/KenjiUpdateInstaller "$release_stage/"
cp README.md "$release_stage/"
tar -czf "dist/$asset_name" -C "$release_stage" .
sha256="$(sha256sum "dist/$asset_name" | cut -d ' ' -f 1)"
python -c 'import json, pathlib, sys; pathlib.Path("dist/update.json").write_text(json.dumps({"version": sys.argv[1], "assets": {"linux-x64": {"name": sys.argv[2], "sha256": sys.argv[3]}}, "notes": f"Actualización de Kenji Music Downloader v{sys.argv[1]}"}, ensure_ascii=False, indent=2), encoding="utf-8")' "$version" "$asset_name" "$sha256"

echo "Ejecutable creado en: $project_root/dist/KenjiMusicDownloader"
echo "Helper creado en: $project_root/dist/KenjiUpdateInstaller"
echo "Paquete creado en: $project_root/dist/$asset_name"
echo "Manifest creado en: $project_root/dist/update.json"
