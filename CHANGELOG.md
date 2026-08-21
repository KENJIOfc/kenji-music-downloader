# Changelog

Todos los cambios relevantes de Yugen Audio se documentan en este archivo.

## v1.0.8

Version de mantenimiento, compatibilidad y distribucion para preparar una nueva publicacion oficial.

- Actualizada la compatibilidad de descarga con YouTube mediante `yt-dlp`.
- Verificado `yt-dlp` 2026.08.19 para corregir rechazos `HTTP Error 403: Forbidden`.
- Mejorado el empaquetado de `yt-dlp` para desacoplar el build del entorno de desarrollo.
- Integrados FFmpeg y FFprobe en la distribucion Windows.
- Mejorada la deteccion de herramientas internas empaquetadas.
- Corregida la advertencia de Pillow por `Image.Image.getdata` usando una ruta compatible con versiones actuales y futuras.
- Mejorado el proceso de build limpio para evitar reutilizar dependencias de compilaciones anteriores.
- Mejorados los manifests de actualizacion con hashes y tamanos calculados sobre los paquetes finales.
- Preparado el flujo de actualizacion para distinguir paquetes Windows x64 y Linux x64.
- Preparado el script de build Linux para generar binario PyInstaller, TAR.GZ, AppImage si `appimagetool` esta disponible y DEB si `dpkg-deb` esta disponible.
- Corregida la validacion del actualizador para aceptar `tools/ffmpeg` y `tools/ffprobe` empaquetados sin permitir archivos de desarrollo o datos de usuario.
- Correcciones menores de estabilidad y distribucion.

## v1.0.7

Version previa de la linea 1.0.x, conservada como referencia historica.

- Incluia la aplicacion de escritorio con interfaz Tkinter para descargar audio de videos individuales de YouTube.
- Usaba `yt-dlp` para descarga y FFmpeg/FFprobe para conversion y diagnostico.
- Mantenia historial local, ajustes de usuario, seleccion de carpeta de salida y temas de interfaz.
- Incluia el sistema de actualizacion basado en GitHub Releases, manifests JSON y helper independiente de instalacion.
- Servia como base funcional antes del mantenimiento publicado como v1.0.8.
