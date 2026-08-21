# Yugen Audio v1.0.8

Yugen Audio v1.0.8 es una actualizacion de mantenimiento centrada en compatibilidad con YouTube, empaquetado limpio y soporte oficial multiplataforma para Windows y Linux.

## Novedades

- Compatibilidad actualizada con YouTube mediante `yt-dlp` 2026.08.19.
- Soporte oficial para Linux x64 con AppImage generado y probado en Linux Mint.
- Builds Windows y Linux con `yt-dlp`, FFmpeg y FFprobe incluidos en el paquete.
- Manifests de actualizacion por plataforma con SHA-256 y tamano real del asset.
- Flujo de compilacion Linux nativo con AppImage, TAR.GZ y paquete DEB.

## Correcciones

- Corregidos fallos de descarga relacionados con `HTTP Error 403: Forbidden`.
- Corregida la advertencia de Pillow por `Image.Image.getdata`.
- Corregida la compatibilidad de Pillow/ImageTk en binarios PyInstaller de Linux.
- Mejorada la deteccion de herramientas internas empaquetadas.
- El actualizador ahora acepta los binarios internos de FFmpeg/FFprobe incluidos en el paquete.

## Compatibilidad

- Windows x64: paquete verificado para ejecutarse sin Python, pip, `yt-dlp`, FFmpeg ni FFprobe instalados manualmente.
- Linux x64: AppImage y TAR.GZ verificados en Linux Mint 22.3; no requieren Python ni `yt-dlp` instalados manualmente.

## Dependencias Actualizadas

- `yt-dlp`: 2026.08.19.
- FFmpeg/FFprobe: incluidos en Windows; incluidos en Linux como binarios estaticos 7.0.2.

## Windows

Artefactos Windows v1.0.8 verificados:

- `YugenAudio-v1.0.8-Windows-x64.zip`
- `update-windows.json`
- `update.json`

## Linux

Artefactos Linux v1.0.8 generados nativamente y probados en Linux Mint:

- `YugenAudio-v1.0.8-Linux-x64.tar.gz`
- `YugenAudio-v1.0.8-Linux-x64.AppImage`
- `yugen-audio_1.0.8_amd64.deb`
- `update-linux.json`

## Notas Conocidas

- Los ejecutables Windows no estan firmados digitalmente; SmartScreen o politicas corporativas pueden mostrar advertencias.
- El paquete DEB se ofrece como formato auxiliar; el AppImage es el formato principal recomendado para usuarios Linux.
