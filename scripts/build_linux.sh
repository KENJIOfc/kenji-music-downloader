#!/usr/bin/env bash
set -euo pipefail

# Construye el ejecutable desde la raíz del proyecto, sin depender de la ruta local.
project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"

python -m PyInstaller --clean --noconfirm kenji-music-downloader.spec
mkdir -p dist/downloads

echo "Ejecutable creado en: $project_root/dist/KenjiMusicDownloader"
