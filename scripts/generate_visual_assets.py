"""Genera PNG optimizados e iconos ICO desde los assets oficiales.

Este script es opcional para desarrollo: la aplicación no necesita Pillow en
tiempo de ejecución porque los derivados ya quedan guardados en assets/.
"""

from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
ASSETS_DIR = PROJECT_ROOT / "assets"
ICON_SIZES = ((16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256))


def _load_pillow():
    try:
        from PIL import Image
    except ImportError as error:
        raise SystemExit(
            "Pillow no está instalado. Instálalo solo para desarrollo con: "
            "python -m pip install pillow"
        ) from error
    return Image


def _transparent_checkerboard(image):
    """Convierte el fondo tipo tablero claro en transparencia."""
    pixels = []
    source_pixels = (
        image.get_flattened_data()
        if hasattr(image, "get_flattened_data")
        else image.getdata()
    )
    for red, green, blue, alpha in source_pixels:
        looks_like_checker = (
            red >= 210
            and green >= 210
            and blue >= 210
            and max(red, green, blue) - min(red, green, blue) <= 28
        )
        pixels.append((red, green, blue, 0 if looks_like_checker else alpha))
    image.putdata(pixels)
    return image


def _center_square(image, size: int, image_module):
    """Recorta el contenido visible y lo centra en un lienzo cuadrado."""
    alpha_box = image.getchannel("A").getbbox()
    if alpha_box:
        image = image.crop(alpha_box)

    side = max(image.size)
    canvas = image_module.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.alpha_composite(image, ((side - image.width) // 2, (side - image.height) // 2))
    return canvas.resize((size, size), image_module.Resampling.LANCZOS)


def _save_icon(
    source_name: str,
    png_name: str,
    ico_name: str | None,
    size: int,
    assets_directory: Path = ASSETS_DIR,
) -> None:
    Image = _load_pillow()
    source = assets_directory / source_name
    image = Image.open(source).convert("RGBA")
    image = _transparent_checkerboard(image)
    icon = _center_square(image, size, Image)

    png_path = assets_directory / png_name
    icon.save(png_path)
    print(f"PNG generado: {png_path.relative_to(PROJECT_ROOT)}")

    if ico_name:
        ico_path = assets_directory / ico_name
        icon.save(ico_path, sizes=ICON_SIZES)
        print(f"ICO generado: {ico_path.relative_to(PROJECT_ROOT)}")


def main() -> None:
    _save_icon("logo_main.png", "logo_main_header.png", None, 150)
    _save_icon(
        "logo_main.png",
        "logo_main_icon.png",
        "logo_main.ico",
        256,
    )
    _save_icon(
        "updater_logo.png",
        "updater_logo_icon.png",
        "updater_logo.ico",
        256,
    )
    yugen_directory = ASSETS_DIR / "yugen"
    if yugen_directory.is_dir():
        # Icono principal nuevo de Yūgen Audio. Se genera desde el emblema
        # oficial sin sobrescribir los PNG originales del usuario.
        _save_icon(
            "yugen_emblem.png",
            "yugen_audio_icon.png",
            "yugen_audio.ico",
            256,
            yugen_directory,
        )


if __name__ == "__main__":
    main()
