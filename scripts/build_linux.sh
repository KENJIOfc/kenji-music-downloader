#!/usr/bin/env bash
set -euo pipefail

# Construye el ejecutable desde la raíz del proyecto, sin depender de la ruta local.
project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"

python -m unittest discover -s tests -v
version="$(python -c 'from src.config import APP_VERSION; print(APP_VERSION)')"

# Limpia únicamente artefactos Linux; conserva un ZIP Windows presente en dist.
mkdir -p dist
rm -rf dist/KenjiMusicDownloader
rm -f dist/KenjiUpdateInstaller
rm -f dist/KenjiMusicDownloader-v*-Linux-x64.tar.gz
rm -f dist/update-linux.json dist/update.json

python -m PyInstaller --clean --noconfirm kenji-music-downloader.spec

asset_name="KenjiMusicDownloader-v${version}-Linux-x64.tar.gz"
onedir_output="$project_root/dist/KenjiMusicDownloader"
main_executable="$onedir_output/KenjiMusicDownloader"
helper_executable="$onedir_output/KenjiUpdateInstaller"
if [[ ! -f "$main_executable" ]]; then
    echo "No se generó el ejecutable esperado: $main_executable" >&2
    exit 1
fi
if [[ ! -f "$helper_executable" ]]; then
    echo "No se generó el helper esperado: $helper_executable" >&2
    exit 1
fi
cp README.md "$onedir_output/"
tar -czf "dist/$asset_name" -C "$project_root/dist" KenjiMusicDownloader
python scripts/generate_update_manifest.py

echo "Ejecutable creado en: $main_executable"
echo "Helper creado en: $helper_executable"
echo "Paquete creado en: $project_root/dist/$asset_name"
echo "Manifest Linux creado en: $project_root/dist/update-linux.json"
if [[ -f "$project_root/dist/update.json" ]]; then
    echo "Manifest combinado creado en: $project_root/dist/update.json"
fi
