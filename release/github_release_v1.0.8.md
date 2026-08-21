# Yugen Audio v1.0.8

Yugen Audio v1.0.8 es una actualizacion de mantenimiento centrada en compatibilidad con YouTube, empaquetado limpio y preparacion multiplataforma.

## Novedades

- Compatibilidad actualizada con YouTube mediante `yt-dlp` 2026.08.19.
- Build Windows limpio con `yt-dlp`, FFmpeg y FFprobe incluidos en el paquete.
- Manifests de actualizacion por plataforma con SHA-256 y tamano real del asset.
- Preparacion del flujo Linux para generar paquetes nativos desde Linux.

## Correcciones

- Corregidos fallos de descarga relacionados con `HTTP Error 403: Forbidden`.
- Corregida la advertencia de Pillow por `Image.Image.getdata`.
- Mejorada la deteccion de herramientas internas empaquetadas.
- El actualizador ahora acepta los binarios internos de FFmpeg/FFprobe incluidos en el paquete.

## Compatibilidad

- Windows x64: paquete verificado para ejecutarse sin Python, pip, `yt-dlp`, FFmpeg ni FFprobe instalados manualmente.
- Linux x64: el build esta preparado en scripts, pero los paquetes Linux v1.0.8 deben compilarse y verificarse nativamente en Linux antes de adjuntarse a esta release.

## Dependencias Actualizadas

- `yt-dlp`: 2026.08.19.
- FFmpeg/FFprobe: incluidos en Windows desde el build disponible en el entorno de compilacion.

## Windows

Adjuntar a esta release unicamente los artefactos Windows v1.0.8 verificados:

- `YugenAudio-v1.0.8-Windows-x64.zip`
- `update-windows.json`
- `update.json` si tambien existe el paquete Linux verificado para la misma version.

## Linux

No adjuntar paquetes Linux generados desde Windows. Para Linux, ejecutar y verificar nativamente:

- `YugenAudio-v1.0.8-Linux-x64.tar.gz`
- `YugenAudio-v1.0.8-Linux-x64.AppImage`, si `appimagetool` esta disponible.
- `yugen-audio_1.0.8_amd64.deb`, si se decide publicar el paquete DEB.

## Notas Conocidas

- Los ejecutables Windows no estan firmados digitalmente; SmartScreen o politicas corporativas pueden mostrar advertencias.
- El paquete Linux v1.0.8 queda pendiente de compilacion y prueba real en Linux antes de publicarse como asset oficial.
