#!/usr/bin/env bash
set -euo pipefail

# Construye el ejecutable desde la raíz del proyecto, sin depender de la ruta local.
project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"

python -m unittest discover -s tests -v
version="$(python -c 'from src.config import APP_VERSION; print(APP_VERSION)')"

# Limpia únicamente artefactos Linux; conserva un ZIP Windows presente en dist.
mkdir -p dist
rm -f dist/KenjiMusicDownloader dist/KenjiUpdateInstaller
rm -f dist/KenjiMusicDownloader-v*-Linux-x64.tar.gz
rm -f dist/update-linux.json dist/update.json

python -m PyInstaller --clean --noconfirm kenji-music-downloader.spec

asset_name="KenjiMusicDownloader-v${version}-Linux-x64.tar.gz"
release_stage="$project_root/build/release-linux"
rm -rf "$release_stage"
mkdir -p "$release_stage"
cp dist/KenjiMusicDownloader "$release_stage/"
cp dist/KenjiUpdateInstaller "$release_stage/"
cp README.md "$release_stage/"
# Enumera los archivos para no crear la entrada raíz `./`; esto conserva
# compatibilidad con helpers de actualización publicados anteriormente.
tar -czf "dist/$asset_name" -C "$release_stage" \
    KenjiMusicDownloader KenjiUpdateInstaller README.md
python scripts/generate_update_manifest.py

echo "Ejecutable creado en: $project_root/dist/KenjiMusicDownloader"
echo "Helper creado en: $project_root/dist/KenjiUpdateInstaller"
echo "Paquete creado en: $project_root/dist/$asset_name"
echo "Manifest Linux creado en: $project_root/dist/update-linux.json"
if [[ -f "$project_root/dist/update.json" ]]; then
    echo "Manifest combinado creado en: $project_root/dist/update.json"
fi
