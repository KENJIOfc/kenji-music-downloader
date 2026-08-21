#!/usr/bin/env bash
set -euo pipefail

# Construye artefactos Linux desde Linux. PyInstaller no genera binarios Linux
# válidos si este script se ejecuta desde Windows.
project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"

dist_dir="$project_root/dist"
build_dir="$project_root/build"
release_dir="$project_root/release/linux"
spec_file="$project_root/kenji-music-downloader.spec"

safe_rm_project_path() {
    local target="$1"
    local resolved
    resolved="$(python -c 'from pathlib import Path; import sys; print(Path(sys.argv[1]).resolve())' "$target")"
    case "$resolved" in
        "$project_root"/*)
            rm -rf -- "$resolved"
            ;;
        *)
            echo "Se rechazo una ruta de limpieza fuera del proyecto: $resolved" >&2
            exit 1
            ;;
    esac
}

find_tool_executable() {
    local tool_name="$1"
    if [[ -n "${YUGEN_FFMPEG_DIR:-}" && -x "${YUGEN_FFMPEG_DIR}/${tool_name}" ]]; then
        printf '%s\n' "${YUGEN_FFMPEG_DIR}/${tool_name}"
        return 0
    fi
    command -v "$tool_name" 2>/dev/null || return 1
}

copy_optional_ffmpeg_notices() {
    local source_path="$1"
    local destination="$2"
    local binary_directory
    local parent_directory
    binary_directory="$(dirname "$source_path")"
    parent_directory="$(dirname "$binary_directory")"

    for directory in "$binary_directory" "$parent_directory"; do
        for notice_name in LICENSE COPYING README.txt; do
            local notice_path="$directory/$notice_name"
            if [[ ! -f "$notice_path" ]]; then
                continue
            fi
            local base_name="${notice_name%.*}"
            local destination_path="$destination/FFmpeg-${base_name}.txt"
            if [[ ! -f "$destination_path" ]]; then
                cp "$notice_path" "$destination_path"
                echo "Aviso de FFmpeg incluido: $destination_path"
            fi
        done
    done
}

copy_required_ffmpeg_tools() {
    local destination="$1"
    local missing=()
    mkdir -p "$destination"

    for tool_name in ffmpeg ffprobe; do
        local source_path=""
        if source_path="$(find_tool_executable "$tool_name")"; then
            cp "$source_path" "$destination/$tool_name"
            chmod +x "$destination/$tool_name"
            echo "Herramienta incluida: $destination/$tool_name"
            copy_optional_ffmpeg_notices "$source_path" "$destination"
        else
            missing+=("$tool_name")
        fi
    done

    if (( ${#missing[@]} > 0 )); then
        echo "ADVERTENCIA: no se encontraron herramientas para incluir: ${missing[*]}." >&2
        echo "La app mostrara el diagnostico normal y dependera de FFmpeg del sistema." >&2
        if [[ "${YUGEN_REQUIRE_BUNDLED_FFMPEG:-0}" == "1" ]]; then
            exit 1
        fi
    fi
}

find_app_icon() {
    for candidate in \
        "$project_root/assets/yugen/yugen_audio.png" \
        "$project_root/assets/yugen/yugen_audio_icon.png" \
        "$project_root/assets/logo_main_icon.png" \
        "$project_root/assets/logo.png"; do
        if [[ -f "$candidate" ]]; then
            printf '%s\n' "$candidate"
            return 0
        fi
    done
    return 1
}

build_appimage() {
    local appimagetool="${APPIMAGETOOL:-appimagetool}"
    if ! command -v "$appimagetool" >/dev/null 2>&1; then
        echo "ADVERTENCIA: appimagetool no esta disponible; se omite AppImage." >&2
        return 0
    fi

    local appimage_name="YugenAudio-v${version}-Linux-x64.AppImage"
    local appdir="$build_dir/appimage/YugenAudio.AppDir"
    safe_rm_project_path "$appdir"
    mkdir -p \
        "$appdir/usr/bin" \
        "$appdir/usr/share/applications" \
        "$appdir/usr/share/icons/hicolor/256x256/apps"

    cp -a "$onedir_output" "$appdir/usr/bin/YugenAudio"
    chmod +x "$appdir/usr/bin/YugenAudio/YugenAudio"
    chmod +x "$appdir/usr/bin/YugenAudio/YugenAudioUpdateInstaller"

    if icon_source="$(find_app_icon)"; then
        cp "$icon_source" "$appdir/YugenAudio.png"
        cp "$icon_source" "$appdir/usr/share/icons/hicolor/256x256/apps/YugenAudio.png"
    fi

    cat > "$appdir/AppRun" <<'APP_RUN'
#!/usr/bin/env bash
set -e
APPDIR="$(dirname "$(readlink -f "$0")")"
export PATH="$APPDIR/usr/bin/YugenAudio/tools:$APPDIR/usr/bin/YugenAudio:$PATH"
exec "$APPDIR/usr/bin/YugenAudio/YugenAudio" "$@"
APP_RUN
    chmod +x "$appdir/AppRun"

    cat > "$appdir/YugenAudio.desktop" <<'DESKTOP'
[Desktop Entry]
Type=Application
Name=Yugen Audio
Comment=YouTube audio downloader
Exec=YugenAudio
Icon=YugenAudio
Categories=AudioVideo;Audio;
Terminal=false
DESKTOP
    cp "$appdir/YugenAudio.desktop" "$appdir/usr/share/applications/YugenAudio.desktop"

    ARCH=x86_64 "$appimagetool" "$appdir" "$dist_dir/$appimage_name"
    chmod +x "$dist_dir/$appimage_name"
}

build_deb_package() {
    if ! command -v dpkg-deb >/dev/null 2>&1; then
        echo "ADVERTENCIA: dpkg-deb no esta disponible; se omite paquete .deb." >&2
        return 0
    fi

    local package_root="$build_dir/deb/yugen-audio"
    local deb_path="$dist_dir/yugen-audio_${version}_amd64.deb"
    safe_rm_project_path "$package_root"
    mkdir -p \
        "$package_root/DEBIAN" \
        "$package_root/opt/yugen-audio" \
        "$package_root/usr/bin" \
        "$package_root/usr/share/applications" \
        "$package_root/usr/share/icons/hicolor/256x256/apps"

    cp -a "$onedir_output" "$package_root/opt/yugen-audio/YugenAudio"
    chmod +x "$package_root/opt/yugen-audio/YugenAudio/YugenAudio"
    chmod +x "$package_root/opt/yugen-audio/YugenAudio/YugenAudioUpdateInstaller"

    cat > "$package_root/usr/bin/yugen-audio" <<'LAUNCHER'
#!/usr/bin/env bash
set -e
export PATH="/opt/yugen-audio/YugenAudio/tools:/opt/yugen-audio/YugenAudio:$PATH"
exec /opt/yugen-audio/YugenAudio/YugenAudio "$@"
LAUNCHER
    chmod +x "$package_root/usr/bin/yugen-audio"

    if icon_source="$(find_app_icon)"; then
        cp "$icon_source" "$package_root/usr/share/icons/hicolor/256x256/apps/YugenAudio.png"
    fi

    cat > "$package_root/usr/share/applications/YugenAudio.desktop" <<'DESKTOP'
[Desktop Entry]
Type=Application
Name=Yugen Audio
Comment=YouTube audio downloader
Exec=yugen-audio
Icon=YugenAudio
Categories=AudioVideo;Audio;
Terminal=false
DESKTOP

    cat > "$package_root/DEBIAN/control" <<CONTROL
Package: yugen-audio
Version: $version
Section: sound
Priority: optional
Architecture: amd64
Maintainer: KENJIOFC
Description: YouTube audio downloader and converter.
 Yugen Audio packages its Python runtime and yt-dlp through PyInstaller.
CONTROL

    dpkg-deb --build "$package_root" "$deb_path"
}

python -m unittest discover -s tests -v
version="$(python -c 'from src.config import APP_VERSION; print(APP_VERSION)')"

mkdir -p "$dist_dir"
safe_rm_project_path "$build_dir"
safe_rm_project_path "$release_dir"
mkdir -p "$release_dir"

# Limpia artefactos Linux y el onedir activo antes de reconstruir con PyInstaller.
safe_rm_project_path "$dist_dir/YugenAudio"
safe_rm_project_path "$dist_dir/KenjiMusicDownloader"
rm -f "$dist_dir/YugenAudioUpdateInstaller" "$dist_dir/KenjiUpdateInstaller"
rm -f "$dist_dir"/YugenAudio-v*-Linux-x64.tar.gz
rm -f "$dist_dir"/YugenAudio-v*-Linux-x64.AppImage
rm -f "$dist_dir"/YugenAudio-v*-Linux-x64.zip
rm -f "$dist_dir"/KenjiMusicDownloader-v*-Linux-x64.tar.gz
rm -f "$dist_dir"/KenjiMusicDownloader-v*-Linux-x64.AppImage
rm -f "$dist_dir"/yugen-audio_*_amd64.deb
rm -f "$dist_dir/update-linux.json" "$dist_dir/update.json"

python -m PyInstaller --clean --noconfirm "$spec_file"

asset_name="YugenAudio-v${version}-Linux-x64.tar.gz"
onedir_output="$dist_dir/YugenAudio"
main_executable="$onedir_output/YugenAudio"
helper_executable="$onedir_output/YugenAudioUpdateInstaller"
if [[ ! -f "$main_executable" ]]; then
    echo "No se genero el ejecutable esperado: $main_executable" >&2
    exit 1
fi
if [[ ! -f "$helper_executable" ]]; then
    echo "No se genero el helper esperado: $helper_executable" >&2
    exit 1
fi

chmod +x "$main_executable" "$helper_executable"
cp README.md "$onedir_output/"
copy_required_ffmpeg_tools "$onedir_output/tools"

tar -czf "$dist_dir/$asset_name" -C "$dist_dir" YugenAudio
build_appimage
build_deb_package
python scripts/generate_update_manifest.py

cp "$dist_dir/$asset_name" "$release_dir/"
for optional_artifact in \
    "$dist_dir/YugenAudio-v${version}-Linux-x64.AppImage" \
    "$dist_dir/yugen-audio_${version}_amd64.deb" \
    "$dist_dir/update-linux.json" \
    "$dist_dir/update.json"; do
    if [[ -f "$optional_artifact" ]]; then
        cp "$optional_artifact" "$release_dir/"
    fi
done

echo "Ejecutable creado en: $main_executable"
echo "Helper creado en: $helper_executable"
echo "Paquete TAR.GZ creado en: $dist_dir/$asset_name"
if [[ -f "$dist_dir/YugenAudio-v${version}-Linux-x64.AppImage" ]]; then
    echo "AppImage creado en: $dist_dir/YugenAudio-v${version}-Linux-x64.AppImage"
fi
if [[ -f "$dist_dir/yugen-audio_${version}_amd64.deb" ]]; then
    echo "Paquete DEB creado en: $dist_dir/yugen-audio_${version}_amd64.deb"
fi
echo "Manifest Linux creado en: $dist_dir/update-linux.json"
echo "Release Linux: $release_dir"
if [[ -f "$dist_dir/update.json" ]]; then
    echo "Manifest combinado creado en: $dist_dir/update.json"
fi
