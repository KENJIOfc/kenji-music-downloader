# Kenji Music Downloader

Aplicación de escritorio para descargar el audio de un video individual de
YouTube y convertirlo al formato elegido. Está escrita en Python, ofrece una
interfaz gráfica con Tkinter, usa la API de `yt-dlp` y delega la conversión a
FFmpeg.

Versión actual: **v1.0.5**.

> Usa esta herramienta únicamente con contenido propio o cuando tengas permiso
> para descargarlo. Respeta los derechos de autor y los términos aplicables.

## Seguridad y alcance

- Solo acepta enlaces de `youtube.com`, `music.youtube.com` y `youtu.be`.
- Convierte cada enlace válido a una URL canónica de un solo video.
- No acepta playlists ni dominios parecidos a YouTube.
- Usa la API de Python de `yt-dlp`; no construye comandos de shell con texto del usuario.
- Permite elegir una carpeta de salida; la predeterminada es `downloads`.
- La descarga se ejecuta en un hilo separado para no congelar la ventana.
- Muestra título, porcentaje real, velocidad, tamaño descargado y tiempo restante.
- Informa las etapas de validación, conexión, descarga, conversión y guardado.
- Obtiene la información y descarga en una sola ejecución de `yt-dlp`.
- No solicita miniaturas, comentarios, subtítulos, descripciones ni archivos JSON.
- Permite cancelar una operación lenta sin bloquear ni cerrar la ventana.
- Guarda como `Título.ext`, sin ID de YouTube; si existe, usa `Título (1).ext`.
- Incluye botones para pegar el enlace, limpiar la interfaz y abrir la carpeta.
- Recuerda la última carpeta, formato, calidad y tema elegidos.
- Conserva un historial local de las últimas 20 descargas.
- Permite abrir el último archivo descargado con el reproductor predeterminado.
- Verifica `yt-dlp`, FFmpeg, FFprobe, carpeta de salida y conexión.
- Puede instalar FFmpeg y FFprobe localmente, siempre con confirmación previa.
- Incluye temas claro y oscuro y un registro local de errores.
- Usa una interfaz compacta con desplazamiento vertical para pantallas pequeñas.
- Busca nuevas versiones mediante la API pública de GitHub Releases.
- Ofrece menú de Archivo, Herramientas y Ayuda.
- No incluye playlists, no ejecuta instaladores externos y no modifica el `PATH`.

## Requisitos

- Python 3.10 o posterior.
- Tkinter (incluido normalmente con Python en Windows).
- `yt-dlp-ejs` y Deno, instalados automáticamente mediante `requirements.txt`.
- Conexión a Internet durante las descargas.

El ejecutable de Windows incluye Python, `yt-dlp` y Deno; el usuario no
necesita instalar Python. Si FFmpeg o FFprobe faltan, la propia aplicación
puede descargarlos e instalarlos para ese usuario.

## Herramientas necesarias

FFmpeg y FFprobe realizan la conversión de audio. La aplicación los busca en
este orden:

1. `%APPDATA%\KenjiMusicDownloader\tools\`;
2. una carpeta `tools` junto al ejecutable, o junto al propio ejecutable;
3. el `PATH` del sistema.

Si no los encuentra, usa **Herramientas > Instalar herramientas necesarias** o
acepta la propuesta que aparece al verificar herramientas o iniciar una
descarga. La aplicación pide confirmación, descarga el ZIP essentials para
Windows x64, extrae únicamente `ffmpeg.exe` y `ffprobe.exe`, y elimina el ZIP
temporal al terminar. No modifica el `PATH`, no instala nada globalmente y no
solicita permisos de administrador.

La fuente configurada es
[Gyan.dev](https://www.gyan.dev/ffmpeg/builds/), proveedor de compilaciones de
Windows enlazado desde la
[página oficial de descarga de FFmpeg](https://ffmpeg.org/download.html#build-windows).
La constante `FFMPEG_WINDOWS_X64_URL` de `src/tool_manager.py` usa esta URL
estable:

```text
https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip
```

La instalación automática está disponible para Windows x64. En Linux se usa el
paquete FFmpeg de la distribución. Quien lo prefiera también puede instalar
FFmpeg manualmente y dejar `ffmpeg` y `ffprobe` disponibles en el `PATH`.

## Descargar desde GitHub Releases

Las versiones publicadas se distribuyen desde
[GitHub Releases](https://github.com/KENJIOFC/kenji-music-downloader/releases).
Para Windows, descarga el archivo con nombre similar a
`KenjiMusicDownloader-v1.0.5-Windows-x64.zip`, extráelo y ejecuta
`KenjiMusicDownloader.exe`.

Esta primera distribución no está firmada digitalmente. Windows SmartScreen o
una política corporativa pueden mostrar una advertencia o bloquear ejecutables
sin firma. Descarga únicamente desde el repositorio oficial y comprueba el
hash SHA-256 publicado junto a cada release.

## Formatos de audio

El selector ofrece MP3 (predeterminado), M4A/AAC, OPUS, WAV, FLAC y OGG. Todos
conservan el nombre limpio y la extensión correspondiente. WAV y FLAC evitan
pérdidas adicionales durante la conversión, pero no recuperan información que
ya haya sido comprimida por la fuente de YouTube.

## Calidad y preferencias

Para formatos comprimidos se puede elegir 128, 192, 256 o 320 kbps. La opción
predeterminada es **Media - 192 kbps**. WAV y FLAC no reciben un bitrate con
pérdida: el selector se conserva como preferencia, pero no se aplica de forma
incorrecta a esos formatos.

La aplicación guarda automáticamente la última carpeta, formato, calidad,
tema y preferencia de búsqueda de actualizaciones en un archivo JSON del
perfil del usuario:

- Windows: `%APPDATA%\KenjiMusicDownloader\settings.json`
- Linux: `~/.config/kenji-music-downloader/settings.json` o la ruta indicada por
  `XDG_CONFIG_HOME`.

El botón **Limpiar** no modifica estas preferencias ni borra archivos. El botón
**Abrir carpeta** usa el explorador de archivos nativo del sistema y no ejecuta
texto proporcionado por el usuario como comando.

La interfaz usa tamaños compactos según el sistema: `1000x720` en Windows y
`920x680` en Linux. El mínimo recomendado es `850x600` en Windows y `820x580`
en Linux; si la pantalla es menor, la app se ajusta al espacio disponible. El
contenido principal tiene scroll vertical, por lo que historial, acciones y
versión siguen accesibles en laptops pequeñas y en Linux Mint XFCE. El
historial muestra tres filas por defecto y conserva sus barras vertical y
horizontal.

El botón de maximizar permanece deshabilitado para conservar la distribución.
Los controles normales de minimizar y cerrar siguen disponibles.

## Actualizaciones automáticas

**Ayuda > Buscar actualizaciones...** consulta en segundo plano la última
release pública de
[`KENJIOFC/kenji-music-downloader`](https://github.com/KENJIOFC/kenji-music-downloader/releases).
Cuando existe una versión nueva, la app muestra versión, notas, tamaño y los
botones **Descargar e instalar**, **Ver en GitHub** y **Cancelar**.

La versión instalada se obtiene de la constante única `APP_VERSION` en
`src/config.py`. Los tags aceptados usan el formato `vMAJOR.MINOR.PATCH` o
`MAJOR.MINOR.PATCH`, por ejemplo:

- versión local: `v1.0.0`;
- release publicada: `v1.0.1`;
- resultado: la aplicación avisa que existe una actualización.

Las opciones del menú Ayuda se guardan en `settings.json`:

- `auto_check_updates`: busca al iniciar; activado por defecto.
- `auto_download_updates`: descarga en segundo plano; desactivado por defecto.
- `allow_auto_install_updates`: permite ofrecer la instalación inmediatamente
  después de una descarga automática; desactivado por defecto.

La instalación siempre exige una confirmación visible. Nunca se reemplazan
archivos silenciosamente.

El flujo automático:

1. elige el asset exacto para Windows o Linux x64;
2. lee `update.json` si está publicado;
3. descarga bajo `%APPDATA%\KenjiMusicDownloader\updates\` en Windows o
   `~/.local/share/KenjiMusicDownloader/updates/` en Linux;
4. calcula SHA-256 y cancela la instalación si no coincide;
5. copia y ejecuta `KenjiUpdateInstaller` sin `shell=True` ni terminal visible;
6. cierra la app, crea backup, reemplaza archivos y la vuelve a abrir;
7. restaura el backup si la sustitución o el reinicio falla.

La configuración, el historial, los logs, las herramientas locales y las
descargas no forman parte del payload y se conservan. La app no modifica el
`PATH`, no instala componentes globales y no solicita permisos administrativos.

Los nombres reconocidos son:

```text
KenjiMusicDownloader-vX.X.X-Windows-x64.zip
KenjiMusicDownloader-vX.X.X-Linux-x64.AppImage
KenjiMusicDownloader-vX.X.X-Linux-x64.tar.gz
KenjiMusicDownloader-vX.X.X-Linux-x64.zip
```

En Linux se prefiere AppImage, después TAR.GZ y finalmente ZIP. Si la carpeta
actual no permite escritura o la app se ejecuta desde el código fuente, se
muestra el fallback para descargar manualmente desde GitHub Releases. El modo
desarrollo permite probar búsqueda, selección, descarga y validación, pero no
sobrescribe el árbol de fuentes.

### Manifest `update.json`

El manifest es opcional, pero se recomienda publicarlo siempre para verificar
SHA-256. Debe subirse como asset de la misma release:

```json
{
  "version": "1.0.5",
  "assets": {
    "windows-x64": {
      "name": "KenjiMusicDownloader-v1.0.5-Windows-x64.zip",
      "sha256": "HASH_SHA256_WINDOWS"
    },
    "linux-x64": {
      "name": "KenjiMusicDownloader-v1.0.5-Linux-x64.tar.gz",
      "sha256": "HASH_SHA256_LINUX"
    }
  },
  "notes": "Notas breves de la actualización"
}
```

Hay una plantilla en `release/update.example.json`. Los scripts de build crean
un `dist/update.json` para su plataforma; si una release contiene Windows y
Linux, combina ambas entradas antes de subir un único manifest.

Sin manifest la app puede continuar únicamente después de advertir que no hay
un hash fuerte publicado. Las URLs siempre se limitan a los assets del
repositorio oficial y ZIP/TAR rechazan path traversal y enlaces simbólicos.

La versión `v1.0.4` introduce el helper. Una instalación anterior que todavía
no incluya `KenjiUpdateInstaller` necesita actualizarse manualmente una sola vez
a `v1.0.4`; las versiones posteriores ya pueden usar el flujo completo.

Al iniciar:

- si existe una versión nueva, se muestra el aviso;
- si ya está actualizado, no se interrumpe al usuario;
- si falla la red o GitHub, el error se registra silenciosamente.

Para que la detección funcione debe existir al menos una release publicada en
GitHub. Si todavía no hay releases, la búsqueda manual muestra una explicación
clara. Para probar el flujo:

1. publica una release con tag `v1.0.5` y comprueba que la app indique que está
   actualizada;
2. publica después una release de prueba con una versión superior, como
   `v1.0.6`;
3. vuelve a buscar y la app ofrecerá descargar e instalar el paquete correcto.

## Historial, herramientas y registro

La ventana muestra las últimas 20 operaciones con nombre, formato, calidad,
estado y ruta. Registra resultados completados, cancelados y con error. La
opción **Herramientas > Limpiar historial** elimina únicamente este registro;
nunca borra los audios descargados.

Selecciona una fila para usar **Abrir seleccionado**, **Abrir su carpeta**,
**Copiar ruta** o **Eliminar entrada**. Las mismas acciones aparecen con clic
derecho. Un doble clic abre directamente el archivo. Eliminar una entrada no
borra el audio real. Las rutas largas permanecen completas y se consultan con
la barra horizontal sin ensanchar la ventana.

Después de una descarga correcta se activa **Abrir archivo**, que utiliza el
reproductor predeterminado del sistema. Si hay una fila seleccionada, este
botón abre primero esa descarga; si no, abre el último archivo descargado. Si
el archivo fue movido o eliminado, la aplicación muestra un error claro.

**Herramientas > Verificar herramientas** comprueba en segundo plano:

- módulo Python de `yt-dlp`;
- `ffmpeg` y `ffprobe` locales, junto al ejecutable o en el `PATH`;
- existencia y permiso de escritura de la carpeta de salida;
- conexión HTTPS básica con YouTube.

La opción **Herramientas > Tema** permite cambiar entre Claro y Oscuro. La
preferencia se carga automáticamente al volver a iniciar la aplicación.

Los datos locales se guardan junto a `settings.json`:

- `history.json`: historial limitado a 20 entradas.
- `logs/errors.log`: errores importantes de descarga, conversión, herramientas,
  configuración y apertura de archivos o carpetas.

En Windows, `settings.json` e `history.json` están en
`%APPDATA%\KenjiMusicDownloader\`, y el log está en
`%APPDATA%\KenjiMusicDownloader\logs\errors.log`. En Linux se usa
`~/.config/kenji-music-downloader/` o `XDG_CONFIG_HOME`. El registro se puede
consultar desde **Ayuda > Ver registro de errores**. Si está vacío, la
aplicación muestra `No hay errores registrados.`

## Probar en Windows

Si el comando `py` todavía no existe, instala primero Python y vuelve a abrir
PowerShell:

```powershell
winget install --id Python.Python.3.12 --exact
```

Entra en la carpeta del proyecto (sustituye la ruta del ejemplo por la tuya) y
crea un entorno virtual:

```powershell
cd ruta\a\kenji-music-downloader
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

FFmpeg puede instalarse desde el menú de la aplicación. Como alternativa
manual, Windows Package Manager ofrece:

```powershell
winget install --id Gyan.FFmpeg --exact
```

Cierra y vuelve a abrir PowerShell si usaste la alternativa manual y el comando
todavía no aparece. Ejecuta las pruebas y abre la interfaz gráfica:

```powershell
python -m unittest discover -s tests -v
python -m src.gui
```

La versión por consola sigue disponible con `python -m src.main`.

Si PowerShell impide activar el entorno virtual, puedes ejecutar sin activarlo:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m src.gui
```

## Crear el ejecutable para Windows

PyInstaller debe ejecutarse en Windows para generar el `.exe`. El script de
construcción elimina únicamente `build/` y `dist/`, ejecuta las pruebas,
construye el ejecutable y crea el ZIP para GitHub Releases:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_windows.ps1
```

Resultados:

```text
dist\KenjiMusicDownloader.exe
dist\KenjiUpdateInstaller.exe
dist\KenjiMusicDownloader-v1.0.5-Windows-x64.zip
dist\update.json
```

El comando manual equivalente es:

```powershell
.\.venv\Scripts\python.exe -m PyInstaller --clean --noconfirm kenji-music-downloader.spec
```

Los dos ejecutables son de un solo archivo, no abren consola negra y no dependen de la
carpeta de desarrollo de Codex. Las preferencias, el historial y los logs
continúan guardándose bajo `%APPDATA%`. El empaquetado no requiere que FFmpeg
esté instalado globalmente: si falta, puede instalarse desde la propia app.

## Pasar el proyecto a Linux

No copies `.venv`, `build` ni `dist`: contienen archivos específicos de Windows.
Copia la carpeta del proyecto por Git, memoria USB, red local o el método que
prefieras. En Linux, entra en la carpeta copiada y crea un entorno nuevo.

En Debian, Ubuntu o Linux Mint:

```bash
sudo apt update
sudo apt install python3 python3-venv python3-pip python3-tk ffmpeg
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python -m src.gui
```

En otras distribuciones, instala los paquetes equivalentes de Python, entornos
virtuales y FFmpeg con el gestor de paquetes correspondiente.

## Crear el ejecutable para Linux

PyInstaller no genera correctamente un ejecutable Linux desde Windows. Estos
comandos deben ejecutarse en la laptop Linux (o en una máquina/VM Linux de la
misma arquitectura de destino), con el entorno virtual activado. El script de
construcción usa el archivo `kenji-music-downloader.spec`:

```bash
bash scripts/build_linux.sh
./dist/KenjiMusicDownloader
```

Resultados publicables:

```text
dist/KenjiMusicDownloader
dist/KenjiUpdateInstaller
dist/KenjiMusicDownloader-v1.0.5-Linux-x64.tar.gz
dist/update.json
```

El comando equivalente, si prefieres ejecutarlo manualmente, es:

```bash
python -m PyInstaller --clean --noconfirm kenji-music-downloader.spec
mkdir -p dist/downloads
```

Los ejecutables se crean en `dist/KenjiMusicDownloader` y
`dist/KenjiUpdateInstaller`. FFmpeg continúa siendo
una dependencia del sistema: debe estar instalado en la laptop Linux. El
ejecutable abre la interfaz gráfica sin una consola adicional. La carpeta
predeterminada será `dist/downloads`, pero puede cambiarse desde la ventana.

Para distribuirlo manualmente, copia a la misma carpeta:

```text
KenjiMusicDownloader
KenjiUpdateInstaller
downloads/
```

Si hace falta restaurar el permiso de ejecución:

```bash
chmod +x KenjiMusicDownloader
chmod +x KenjiUpdateInstaller
./KenjiMusicDownloader
```

## Diagnosticar tiempos de descarga

La GUI muestra un resumen y la consola imprime líneas con el prefijo
`[TIEMPO]`. Para comparar dos pruebas, revisa especialmente:

- `Validación`: procesamiento local de la URL; normalmente debe ser casi cero.
- `Inicio yt-dlp`: creación de `YoutubeDL` y carga de sus componentes.
- `Conexión/obtención`: tiempo dentro del extractor de YouTube antes del primer byte.
- `Primer progreso recibido`: tiempo acumulado hasta comenzar la descarga real.
- `Descarga`: transferencia del audio.
- `Conversión`: trabajo de FFmpeg después de terminar la transferencia.
- `Total`: flujo completo desde la validación hasta el archivo final.

Si `Validación` e `Inicio yt-dlp` son bajos, pero `Conexión/obtención` es alta,
la espera está dentro de YouTube/yt-dlp (red, respuestas del extractor o retos
JavaScript), no en la GUI ni en una segunda llamada de la aplicación.

La interfaz muestra un aviso al superar 30 segundos de conexión y otro al
superar 90 segundos. Puedes seguir esperando o pulsar `Cancelar`. La
cancelación es cooperativa: la ventana responde inmediatamente, pero una
petición de red que ya esté en curso puede tardar hasta su timeout en cerrarse.

Si esta etapa tarda demasiado, actualiza primero `yt-dlp` dentro del entorno:

```bash
python -m pip install --upgrade yt-dlp
```

### Probar yt-dlp directamente

Con el entorno virtual activado, sustituye `URL_DEL_VIDEO` por un enlace entre
comillas. `--simulate` realiza la conexión y extracción, pero no descarga el
archivo:

```bash
python -m yt_dlp --version
python -m yt_dlp --force-ipv4 --socket-timeout 20 --no-playlist --simulate --verbose "URL_DEL_VIDEO"
```

Para comparar con la selección automática de red, repite sin IPv4 forzado:

```bash
python -m yt_dlp --socket-timeout 20 --no-playlist --simulate --verbose "URL_DEL_VIDEO"
```

Si la primera prueba es claramente más rápida, conserva IPv4 forzado. Esta
opción se controla en `src/config.py`:

```python
FORCE_IPV4 = True  # Activado
FORCE_IPV4 = False  # Desactivado
SOCKET_TIMEOUT_SECONDS = 20
```

## Archivos locales y publicación segura

El repositorio conserva únicamente `downloads/.gitkeep` para crear la carpeta
vacía. `.gitignore` excluye audios, entornos virtuales, cachés, builds, logs,
temporales, cookies y configuraciones locales. Antes de publicar puedes revisar:

```powershell
git status
git ls-files downloads
git ls-files "*.mp3" "*.m4a" "*.opus" "*.wav" "*.flac" "*.ogg" "*.log"
```

`settings.json`, `history.json` y `logs/errors.log` se crean bajo
`%APPDATA%\KenjiMusicDownloader\`, no dentro del repositorio ni del ZIP de la
release.

Las herramientas descargadas se guardan en
`%APPDATA%\KenjiMusicDownloader\tools\` y tampoco forman parte del repositorio.
Los paquetes temporales de actualización usan la subcarpeta `updates/` y no se
suben a Git.

## Estructura

```text
kenji-music-downloader/
├── src/
│   ├── __init__.py
│   ├── gui.py
│   ├── main.py
│   ├── downloader.py
│   ├── audio_formats.py
│   ├── user_settings.py
│   ├── platform_utils.py
│   ├── download_history.py
│   ├── diagnostics.py
│   ├── tool_manager.py
│   ├── error_log.py
│   ├── updates.py
│   ├── update_manager.py
│   ├── update_installer.py
│   ├── security.py
│   └── config.py
├── downloads/
│   └── .gitkeep
├── tests/
│   ├── test_downloader.py
│   ├── test_download_history.py
│   ├── test_diagnostics.py
│   ├── test_config.py
│   ├── test_tool_manager.py
│   ├── test_error_log.py
│   ├── test_platform_utils.py
│   ├── test_user_settings.py
│   ├── test_updates.py
│   ├── test_update_manager.py
│   ├── test_update_installer.py
│   └── test_security.py
├── scripts/
│   ├── build_windows.ps1
│   └── build_linux.sh
├── kenji-music-downloader.spec
├── release/
│   └── update.example.json
├── requirements.txt
├── README.md
└── .gitignore
```

## Archivos principales

- `src/gui.py`: ventana, selección de carpeta, progreso y mensajes al usuario.
- `src/main.py`: versión alternativa por consola.
- `src/security.py`: valida el dominio y extrae un identificador de video seguro.
- `src/downloader.py`: descarga y convierte al formato elegido mediante `yt-dlp` y FFmpeg.
- `src/audio_formats.py`: catálogo permitido de formatos, códecs y extensiones.
- `src/user_settings.py`: preferencias JSON portables del usuario.
- `src/platform_utils.py`: apertura segura de carpetas en Windows, Linux y macOS.
- `src/download_history.py`: historial JSON persistente y limitado.
- `src/diagnostics.py`: verificación de herramientas, carpeta y conexión.
- `src/tool_manager.py`: resolución, descarga y extracción segura de FFmpeg/FFprobe.
- `src/error_log.py`: registro local de errores importantes.
- `src/updates.py`: consulta GitHub Releases, compara versiones y conserva
  metadatos de assets.
- `src/update_manager.py`: selecciona assets, lee el manifest, descarga, valida
  SHA-256 y lanza el helper.
- `src/update_installer.py`: helper separado con extracción segura, backup,
  reemplazo, rollback y reinicio.
- `src/config.py`: versión, rutas portables y validación de la carpeta de salida.
- `tests/test_security.py`: verifica que se acepten y rechacen los enlaces correctos.
- `tests/test_downloader.py`: verifica el progreso consumido por la interfaz.
- `kenji-music-downloader.spec`: configuración portable de PyInstaller.
- `scripts/build_linux.sh`: construcción repetible del ejecutable Linux.
- `scripts/build_windows.ps1`: pruebas, construcción y ZIP publicable para Windows.
- `requirements.txt`: dependencias de Python, incluido PyInstaller.
- `.gitignore`: excluye descargas, entornos y archivos generados.

## Actualizar yt-dlp

YouTube cambia con frecuencia. Si una descarga deja de funcionar, actualiza
`yt-dlp` dentro del entorno virtual antes de investigar otros errores:

```bash
python -m pip install --upgrade yt-dlp
```
