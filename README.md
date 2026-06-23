# Kenji Music Downloader

AplicaciÃ³n de escritorio para descargar el audio de un video individual de
YouTube y convertirlo al formato elegido. EstÃ¡ escrita en Python, ofrece una
interfaz grÃ¡fica con Tkinter, usa la API de `yt-dlp` y delega la conversiÃ³n a
FFmpeg.

VersiÃ³n actual: **v1.0.7**.

> Usa esta herramienta Ãºnicamente con contenido propio o cuando tengas permiso
> para descargarlo. Respeta los derechos de autor y los tÃ©rminos aplicables.

## Seguridad y alcance

- Solo acepta enlaces de `youtube.com`, `music.youtube.com` y `youtu.be`.
- Convierte cada enlace vÃ¡lido a una URL canÃ³nica de un solo video.
- No acepta playlists ni dominios parecidos a YouTube.
- Usa la API de Python de `yt-dlp`; no construye comandos de shell con texto del usuario.
- Permite elegir una carpeta de salida; la predeterminada es `downloads`.
- La descarga se ejecuta en un hilo separado para no congelar la ventana.
- Muestra tÃ­tulo, porcentaje real, velocidad, tamaÃ±o descargado y tiempo restante.
- Informa las etapas de validaciÃ³n, conexiÃ³n, descarga, conversiÃ³n y guardado.
- Obtiene la informaciÃ³n y descarga en una sola ejecuciÃ³n de `yt-dlp`.
- No solicita miniaturas, comentarios, subtÃ­tulos, descripciones ni archivos JSON.
- Permite cancelar una operaciÃ³n lenta sin bloquear ni cerrar la ventana.
- Guarda como `TÃ­tulo.ext`, sin ID de YouTube; si existe, usa `TÃ­tulo (1).ext`.
- Incluye botones para pegar el enlace, limpiar la interfaz y abrir la carpeta.
- Recuerda la Ãºltima carpeta, formato, calidad y tema elegidos.
- Conserva un historial local de las Ãºltimas 20 descargas.
- Permite abrir el Ãºltimo archivo descargado con el reproductor predeterminado.
- Verifica `yt-dlp`, FFmpeg, FFprobe, carpeta de salida y conexiÃ³n.
- Puede instalar FFmpeg y FFprobe localmente, siempre con confirmaciÃ³n previa.
- Incluye temas claro y oscuro, con diseÃ±o oscuro/neÃ³n como experiencia principal.
- Usa una interfaz compacta con desplazamiento vertical para pantallas pequeÃ±as.
- Incluye logotipo oficial, assets visuales e icono propio para la ventana y el ejecutable.
- Busca nuevas versiones mediante la API pÃºblica de GitHub Releases.
- Ofrece menÃº de Archivo, Herramientas y Ayuda.
- No incluye playlists, no ejecuta instaladores externos y no modifica el `PATH`.

## Requisitos

- Python 3.10 o posterior.
- Tkinter (incluido normalmente con Python en Windows).
- `yt-dlp-ejs` y Deno, instalados automÃ¡ticamente mediante `requirements.txt`.
- ConexiÃ³n a Internet durante las descargas.

El ejecutable de Windows incluye Python, `yt-dlp` y Deno; el usuario no
necesita instalar Python. Si FFmpeg o FFprobe faltan, la propia aplicaciÃ³n
puede descargarlos e instalarlos para ese usuario.

## Identidad visual y assets

Los recursos visuales oficiales viven en `assets/`:

```text
assets/logo_main.png
assets/logo_main_header.png
assets/logo_main_icon.png
assets/logo_main.ico
assets/updater_logo.png
assets/updater_logo_icon.png
assets/updater_logo.ico
assets/typography_reference.png
assets/interface_reference_new.png
```

- `assets/logo_main.png`: logo principal de Kenji Music Downloader.
- `assets/logo_main_header.png`: versiÃ³n optimizada que se muestra en el encabezado.
- `assets/logo_main_icon.png`: versiÃ³n PNG cuadrada para icono de ventana en Linux.
- `assets/logo_main.ico`: icono principal de `KenjiMusicDownloader.exe`.
- `assets/updater_logo.png`: logo exclusivo del actualizador.
- `assets/updater_logo_icon.png`: vista previa PNG del icono del actualizador.
- `assets/updater_logo.ico`: icono de `KenjiUpdateInstaller.exe`.
- `assets/typography_reference.png`: referencia de estilo tipogrÃ¡fico.
- `assets/interface_reference_new.png`: referencia visual del diseÃ±o oscuro/neÃ³n.

La interfaz intenta usar **Rajdhani** para tÃ­tulos y secciones. Si esa fuente no
estÃ¡ instalada, usa alternativas seguras y modernas como **Bahnschrift**,
**Segoe UI**, **Noto Sans** o **DejaVu Sans**, segÃºn el sistema.

Si cambias el logotipo en el futuro, reemplaza `assets/logo_main.png` o
`assets/updater_logo.png` y vuelve a generar las versiones derivadas
(`logo_main_header.png`, `logo_main_icon.png`, `logo_main.ico`,
`updater_logo_icon.png` y `updater_logo.ico`). El archivo `.spec` ya incluye
`assets/`, por lo que el ejecutable puede cargar el logo desde PyInstaller sin
usar rutas absolutas.

Para regenerar esos derivados puedes usar el script opcional:

```powershell
python -m pip install pillow
python scripts\generate_visual_assets.py
```

Pillow solo es necesario para regenerar imÃ¡genes durante desarrollo; la app y el
ejecutable no lo necesitan para funcionar porque cargan los PNG/ICO ya creados.

## Herramientas necesarias

FFmpeg y FFprobe realizan la conversiÃ³n de audio. La aplicaciÃ³n los busca en
este orden:

1. `%APPDATA%\KenjiMusicDownloader\tools\`;
2. una carpeta `tools` junto al ejecutable, o junto al propio ejecutable;
3. el `PATH` del sistema.

Si no los encuentra, usa **Herramientas > Instalar herramientas necesarias** o
acepta la propuesta que aparece al verificar herramientas o iniciar una
descarga. La aplicaciÃ³n pide confirmaciÃ³n, descarga el ZIP essentials para
Windows x64, extrae Ãºnicamente `ffmpeg.exe` y `ffprobe.exe`, y elimina el ZIP
temporal al terminar. No modifica el `PATH`, no instala nada globalmente y no
solicita permisos de administrador.

La fuente configurada es
[Gyan.dev](https://www.gyan.dev/ffmpeg/builds/), proveedor de compilaciones de
Windows enlazado desde la
[pÃ¡gina oficial de descarga de FFmpeg](https://ffmpeg.org/download.html#build-windows).
La constante `FFMPEG_WINDOWS_X64_URL` de `src/tool_manager.py` usa esta URL
estable:

```text
https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip
```

La instalaciÃ³n automÃ¡tica estÃ¡ disponible para Windows x64. En Linux se usa el
paquete FFmpeg de la distribuciÃ³n. Quien lo prefiera tambiÃ©n puede instalar
FFmpeg manualmente y dejar `ffmpeg` y `ffprobe` disponibles en el `PATH`.

## Descargar desde GitHub Releases

Las versiones publicadas se distribuyen desde
[GitHub Releases](https://github.com/KENJIOFC/kenji-music-downloader/releases).
Para Windows, descarga el archivo con nombre similar a
`KenjiMusicDownloader-v1.0.7-Windows-x64.zip`, extrÃ¡elo y ejecuta
`KenjiMusicDownloader.exe`.

Esta distribuciÃ³n no estÃ¡ firmada digitalmente. Windows SmartScreen, Smart App
Control o una polÃ­tica corporativa pueden mostrar una advertencia o bloquear
ejecutables sin publicador comprobable. Esto no se debe resolver con bypasses:
lo ideal para una publicaciÃ³n pÃºblica es firmar el ejecutable con un certificado
de firma de cÃ³digo. Descarga Ãºnicamente desde el repositorio oficial y comprueba
el hash SHA-256 publicado junto a cada release.

## Formatos de audio

El selector ofrece MP3 (predeterminado), M4A/AAC, OPUS, WAV, FLAC y OGG. Todos
conservan el nombre limpio y la extensiÃ³n correspondiente. WAV y FLAC evitan
pÃ©rdidas adicionales durante la conversiÃ³n, pero no recuperan informaciÃ³n que
ya haya sido comprimida por la fuente de YouTube.

## Calidad y preferencias

Para formatos comprimidos se puede elegir 128, 192, 256 o 320 kbps. La opciÃ³n
predeterminada es **Media - 192 kbps**. WAV y FLAC no reciben un bitrate con
pÃ©rdida: el selector se conserva como preferencia, pero no se aplica de forma
incorrecta a esos formatos.

La aplicaciÃ³n guarda automÃ¡ticamente la Ãºltima carpeta, formato, calidad,
tema y preferencia de bÃºsqueda de actualizaciones en un archivo JSON del
perfil del usuario:

- Windows: `%APPDATA%\KenjiMusicDownloader\settings.json`
- Linux: `~/.config/kenji-music-downloader/settings.json` o la ruta indicada por
  `XDG_CONFIG_HOME`.

El botÃ³n **Limpiar** no modifica estas preferencias ni borra archivos. El botÃ³n
**Abrir carpeta** usa el explorador de archivos nativo del sistema y no ejecuta
texto proporcionado por el usuario como comando.

La interfaz usa tamaÃ±os compactos segÃºn el sistema: `1050x760` en Windows y
`960x700` en Linux. El mÃ­nimo recomendado es `860x620` en Windows y `820x600`
en Linux; si la pantalla es menor, la app se ajusta al espacio disponible. El
contenido principal tiene scroll vertical, por lo que historial, acciones y
versiÃ³n siguen accesibles en laptops pequeÃ±as y en Linux Mint XFCE. El
historial muestra cuatro filas por defecto y conserva sus barras vertical y
horizontal.

El botÃ³n de maximizar permanece deshabilitado para conservar la distribuciÃ³n.
Los controles normales de minimizar y cerrar siguen disponibles.

## Actualizaciones automÃ¡ticas

**Ayuda > Buscar actualizaciones...** consulta en segundo plano la Ãºltima
release pÃºblica de
[`KENJIOFC/kenji-music-downloader`](https://github.com/KENJIOFC/kenji-music-downloader/releases).
Cuando existe una versiÃ³n nueva, la app muestra versiÃ³n, notas, tamaÃ±o y los
botones **Descargar e instalar**, **Ver en GitHub** y **Cancelar**.

La versiÃ³n instalada se obtiene de la constante Ãºnica `APP_VERSION` en
`src/config.py`. Los tags aceptados usan el formato `vMAJOR.MINOR.PATCH` o
`MAJOR.MINOR.PATCH`, por ejemplo:

- versiÃ³n local: `v1.0.0`;
- release publicada: `v1.0.1`;
- resultado: la aplicaciÃ³n avisa que existe una actualizaciÃ³n.

Las opciones del menÃº Ayuda se guardan en `settings.json`:

- `auto_check_updates`: busca al iniciar; activado por defecto.
- `auto_download_updates`: descarga en segundo plano; desactivado por defecto.
- `allow_auto_install_updates`: permite ofrecer la instalaciÃ³n inmediatamente
  despuÃ©s de una descarga automÃ¡tica; desactivado por defecto.

La instalaciÃ³n siempre exige una confirmaciÃ³n visible. Nunca se reemplazan
archivos silenciosamente.

El flujo automÃ¡tico:

1. elige el asset exacto para Windows o Linux x64;
2. lee `update.json` si estÃ¡ publicado;
3. descarga bajo `%APPDATA%\KenjiMusicDownloader\updates\` en Windows o
   `~/.local/share/KenjiMusicDownloader/updates/` en Linux;
4. calcula SHA-256 y cancela la instalaciÃ³n si no coincide;
5. copia y ejecuta `KenjiUpdateInstaller` sin `shell=True` ni terminal visible;
6. cierra la app, crea backup, reemplaza archivos y la vuelve a abrir;
7. restaura el backup si la sustituciÃ³n o el reinicio falla.

La configuraciÃ³n, el historial, los logs, las herramientas locales y las
descargas no forman parte del payload y se conservan. La app no modifica el
`PATH`, no instala componentes globales y no solicita permisos administrativos.

Los nombres reconocidos son:

```text
KenjiMusicDownloader-vX.X.X-Windows-x64.zip
KenjiMusicDownloader-vX.X.X-Linux-x64.AppImage
KenjiMusicDownloader-vX.X.X-Linux-x64.tar.gz
KenjiMusicDownloader-vX.X.X-Linux-x64.zip
```

En Linux se prefiere AppImage, despuÃ©s TAR.GZ y finalmente ZIP. Si la carpeta
actual no permite escritura o la app se ejecuta desde el cÃ³digo fuente, se
muestra el fallback para descargar manualmente desde GitHub Releases. El modo
desarrollo permite probar bÃºsqueda, selecciÃ³n, descarga y validaciÃ³n, pero no
sobrescribe el Ã¡rbol de fuentes.

### Manifest `update.json`

El manifest es opcional, pero se recomienda publicarlo siempre para verificar
SHA-256. Debe subirse como asset de la misma release:

```json
{
  "version": "1.0.7",
  "assets": {
    "windows-x64": {
      "name": "KenjiMusicDownloader-v1.0.7-Windows-x64.zip",
      "sha256": "HASH_SHA256_WINDOWS"
    },
    "linux-x64": {
      "name": "KenjiMusicDownloader-v1.0.7-Linux-x64.tar.gz",
      "sha256": "HASH_SHA256_LINUX"
    }
  },
  "notes": "Notas breves de la actualizaciÃ³n"
}
```

Hay una plantilla en `release/update.example.json`. Windows genera
`update-windows.json` y Linux genera `update-linux.json`, siempre con el hash
real de su paquete. Cuando ambos paquetes estÃ¡n juntos en `dist`, el generador
crea ademÃ¡s el `update.json` combinado recomendado para GitHub Releases.

El actualizador busca primero `update.json`. Si ese archivo no estÃ¡ publicado,
no puede descargarse, es invÃ¡lido o no contiene el sistema actual, usa
`update-windows.json` en Windows o `update-linux.json` en Linux. Ambos formatos
se normalizan al mismo modelo interno antes de descargar. Si tampoco existe un
manifest especÃ­fico vÃ¡lido, la actualizaciÃ³n se cancela con un mensaje claro.

Sin manifest vÃ¡lido la app no descarga ni instala el paquete. Las URLs siempre
se limitan a los assets del repositorio oficial y ZIP/TAR rechazan path
traversal y enlaces simbÃ³licos.

La versiÃ³n `v1.0.4` introduce el helper. Una instalaciÃ³n anterior que todavÃ­a
no incluya `KenjiUpdateInstaller` necesita actualizarse manualmente una sola vez
a `v1.0.4`; las versiones posteriores ya pueden usar el flujo completo.

Al iniciar:

- si existe una versiÃ³n nueva, se muestra el aviso;
- si ya estÃ¡ actualizado, no se interrumpe al usuario;
- si falla la red o GitHub, el error se registra silenciosamente.

Para que la detecciÃ³n funcione debe existir al menos una release publicada en
GitHub. Si todavÃ­a no hay releases, la bÃºsqueda manual muestra una explicaciÃ³n
clara. Para probar el flujo:

1. publica una release con tag `v1.0.7` y comprueba que la app indique que estÃ¡
   actualizada;
2. publica despuÃ©s una release de prueba con una versiÃ³n superior, como
   `v1.0.7`;
3. vuelve a buscar y la app ofrecerÃ¡ descargar e instalar el paquete correcto.

### DiagnÃ³stico seguro del actualizador

El mÃ³dulo `src.update_diagnostics` prueba el mismo manifest, descarga, SHA-256 y
extractor usados por la actualizaciÃ³n real, pero trabaja Ãºnicamente dentro de
una carpeta temporal. No inicia `KenjiUpdateInstaller`, no cierra la aplicaciÃ³n
y no reemplaza archivos instalados.

El comando documentado para dry-run es `python -m src.update_diagnostics`; el
mÃ³dulo `src.update_manager` permanece como biblioteca interna y no instala nada
por sÃ­ solo.

Para probar automÃ¡ticamente el sistema actual contra la Ãºltima release:

```bash
python -m src.update_diagnostics --dry-run --expect-version 1.0.7
```

TambiÃ©n se puede comprobar explÃ­citamente la selecciÃ³n de cada asset desde una
sola mÃ¡quina:

```bash
python -m src.update_diagnostics --dry-run --platform windows --expect-version 1.0.7
python -m src.update_diagnostics --dry-run --platform linux --expect-version 1.0.7
```

El diagnÃ³stico exige que el Ãºnico `update.json` contenga entradas y SHA-256
vÃ¡lidos para `windows-x64` y `linux-x64`. Registra URL consultada, manifest,
sistema, asset, ruta temporal, hashes y resultado de extracciÃ³n en el log local.
Los temporales se eliminan al terminar, incluso cuando la prueba falla.

## Historial, herramientas y registro

La ventana muestra las Ãºltimas 20 operaciones con nombre, formato, calidad,
estado y ruta. Registra resultados completados, cancelados y con error. La
opciÃ³n **Herramientas > Limpiar historial** elimina Ãºnicamente este registro;
nunca borra los audios descargados.

Selecciona una fila para usar **Abrir seleccionado**, **Abrir su carpeta**,
**Copiar ruta** o **Eliminar entrada**. Las mismas acciones aparecen con clic
derecho. Un doble clic abre directamente el archivo. Eliminar una entrada no
borra el audio real. Las rutas largas permanecen completas y se consultan con
la barra horizontal sin ensanchar la ventana.

DespuÃ©s de una descarga correcta se activa **Abrir archivo**, que utiliza el
reproductor predeterminado del sistema. Si hay una fila seleccionada, este
botÃ³n abre primero esa descarga; si no, abre el Ãºltimo archivo descargado. Si
el archivo fue movido o eliminado, la aplicaciÃ³n muestra un error claro.

**Herramientas > Verificar herramientas** comprueba en segundo plano:

- mÃ³dulo Python de `yt-dlp`;
- `ffmpeg` y `ffprobe` locales, junto al ejecutable o en el `PATH`;
- existencia y permiso de escritura de la carpeta de salida;
- conexiÃ³n HTTPS bÃ¡sica con YouTube.

La opciÃ³n **Herramientas > Tema** permite cambiar entre Claro y Oscuro. La
preferencia se carga automÃ¡ticamente al volver a iniciar la aplicaciÃ³n.

Los datos locales se guardan junto a `settings.json`:

- `history.json`: historial limitado a 20 entradas.
- `logs/errors.log`: errores importantes de descarga, conversiÃ³n, herramientas,
  configuraciÃ³n y apertura de archivos o carpetas.

En Windows, `settings.json` e `history.json` estÃ¡n en
`%APPDATA%\KenjiMusicDownloader\`, y el log estÃ¡ en
`%APPDATA%\KenjiMusicDownloader\logs\errors.log`. En Linux se usa
`~/.config/kenji-music-downloader/` o `XDG_CONFIG_HOME`. El registro se puede
consultar desde **Ayuda > Ver registro de errores**. Si estÃ¡ vacÃ­o, la
aplicaciÃ³n muestra `No hay errores registrados.`

La opciÃƒÂ³n **Herramientas > Limpiar registros** vacÃƒÂ­a solamente los logs
tÃƒÂ©cnicos generados por la aplicaciÃƒÂ³n. No elimina descargas, historial ni
configuraciÃƒÂ³n del usuario.

## Contacto y soporte

La opciÃ³n **Ayuda > Contacto / Soporte** muestra el contacto oficial por
Discord. Desde esa ventana se puede abrir el perfil en el navegador o copiar el
enlace al portapapeles:

<https://discordapp.com/users/649369933226180658>

Usa este contacto para soporte, dudas o reportar problemas de la aplicaciÃ³n.

## Probar en Windows

Si el comando `py` todavÃ­a no existe, instala primero Python y vuelve a abrir
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

FFmpeg puede instalarse desde el menÃº de la aplicaciÃ³n. Como alternativa
manual, Windows Package Manager ofrece:

```powershell
winget install --id Gyan.FFmpeg --exact
```

Cierra y vuelve a abrir PowerShell si usaste la alternativa manual y el comando
todavÃ­a no aparece. Ejecuta las pruebas y abre la interfaz grÃ¡fica:

```powershell
python -m unittest discover -s tests -v
python -m src.gui
```

La versiÃ³n por consola sigue disponible con `python -m src.main`.

Si PowerShell impide activar el entorno virtual, puedes ejecutar sin activarlo:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m src.gui
```

## Crear el ejecutable para Windows

PyInstaller debe ejecutarse en Windows para generar el `.exe`. El script de
construcciÃ³n limpia `build/` y los artefactos Windows anteriores, conserva un
paquete Linux presente en `dist`, ejecuta las pruebas, incluye `assets/`, aplica
`assets/logo_main.ico` como icono de `KenjiMusicDownloader.exe`, aplica
`assets/updater_logo.ico` como icono de `KenjiUpdateInstaller.exe` y
crea el ZIP:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_windows.ps1
```

Resultados:

```text
dist\KenjiMusicDownloader\KenjiMusicDownloader.exe
dist\KenjiMusicDownloader\KenjiUpdateInstaller.exe
dist\KenjiMusicDownloader\_internal\
dist\KenjiMusicDownloader-v1.0.7-Windows-x64.zip
dist\update-windows.json
dist\update.json (solo si tambiÃ©n estÃ¡ presente el paquete Linux)
```

El comando manual equivalente es:

```powershell
.\.venv\Scripts\python.exe -m PyInstaller --clean --noconfirm kenji-music-downloader.spec
```

El `.spec` genera una carpeta **onedir**. Este formato evita el autoextractor de
`--onefile`, deja los archivos de soporte visibles en `_internal` y suele ser
mÃ¡s transparente para antivirus que un ejecutable Ãºnico empaquetado. Si quieres
probar comandos directos sin el `.spec`, usa tambiÃ©n `--onedir`:

```powershell
.\.venv\Scripts\python.exe -m PyInstaller --onedir --windowed --name KenjiMusicDownloader --icon assets\logo_main.ico --add-data "assets;assets" src\gui.py
.\.venv\Scripts\python.exe -m PyInstaller --onedir --windowed --name KenjiUpdateInstaller --icon assets\updater_logo.ico src\update_installer.py
```

Los ejecutables no abren consola negra y no dependen de la carpeta de desarrollo
de Codex. Las preferencias, el historial y los logs continÃºan guardÃ¡ndose bajo
`%APPDATA%`. El empaquetado no requiere que FFmpeg estÃ© instalado globalmente:
si falta, puede instalarse desde la propia app.

El build excluye archivos de desarrollo como tests, cachÃ©s, backups, `.git`,
entornos virtuales, descargas y temporales. El actualizador solo lanza
`KenjiUpdateInstaller` despuÃ©s de una confirmaciÃ³n visible del usuario y descarga
assets desde GitHub Releases del repositorio oficial usando el manifest publicado.
El `.spec` desactiva UPX, usa `onedir` y no solicita permisos de administrador.

### Falsos positivos y firma digital

Algunos antivirus pueden marcar ejecutables de PyInstaller con detecciones
genÃ©ricas, especialmente si son nuevos, no estÃ¡n firmados o usan `--onefile`.
Este proyecto usa `onedir`, no oculta procesos, no ejecuta PowerShell/CMD, no
modifica el `PATH` del sistema y no intenta evadir controles de seguridad.

Smart App Control puede bloquear la app aunque VirusTotal sea mayormente limpio
si Windows no puede comprobar el publicador. La soluciÃ³n correcta para reducir
ese bloqueo en distribuciÃ³n pÃºblica es firmar `KenjiMusicDownloader.exe` y
`KenjiUpdateInstaller.exe` con un certificado de firma de cÃ³digo y publicar los
hashes SHA-256 de cada release.

Errores comunes de assets o icono:

- Si la ventana abre sin logotipo, verifica que exista `assets/logo_main_header.png`.
- Si `KenjiMusicDownloader.exe` queda con icono genÃ©rico, confirma que exista
  `assets/logo_main.ico` antes de ejecutar PyInstaller y reconstruye desde cero
  con el `.spec`.
- Si `KenjiUpdateInstaller.exe` muestra el mismo icono de la app principal,
  confirma que el `.spec` apunte a `assets/updater_logo.ico`.
- Si Windows sigue mostrando un icono viejo aunque el `.spec` estÃ© correcto,
  puede ser cachÃ© del Explorador. Prueba renombrar el `.exe`, reconstruir en una
  carpeta limpia o limpiar la cachÃ© de iconos de Windows.
- Si PyInstaller no encuentra assets, usa el archivo `.spec` del proyecto o agrega
  `--add-data "assets;assets"` en Windows.

## Pasar el proyecto a Linux

No copies `.venv`, `build` ni `dist`: contienen archivos especÃ­ficos de Windows.
Copia la carpeta del proyecto por Git, memoria USB, red local o el mÃ©todo que
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
comandos deben ejecutarse en la laptop Linux (o en una mÃ¡quina/VM Linux de la
misma arquitectura de destino), con el entorno virtual activado. El script de
construcciÃ³n usa el archivo `kenji-music-downloader.spec` e incluye la carpeta
`assets/` para que el logotipo cargue tambiÃ©n en el binario:

```bash
bash scripts/build_linux.sh
./dist/KenjiMusicDownloader
```

Resultados publicables:

```text
dist/KenjiMusicDownloader/KenjiMusicDownloader
dist/KenjiMusicDownloader/KenjiUpdateInstaller
dist/KenjiMusicDownloader/_internal/
dist/KenjiMusicDownloader-v1.0.7-Linux-x64.tar.gz
dist/update-linux.json
dist/update.json (solo si tambiÃ©n estÃ¡ presente el paquete Windows)
```

El comando equivalente, si prefieres ejecutarlo manualmente, es:

```bash
python -m PyInstaller --clean --noconfirm kenji-music-downloader.spec
mkdir -p dist/downloads
```

Un comando directo mÃ­nimo para Linux serÃ­a:

```bash
python -m PyInstaller --onedir --name KenjiMusicDownloader --add-data "assets:assets" src/gui.py
```

Los ejecutables se crean dentro de la carpeta `dist/KenjiMusicDownloader/`.
FFmpeg continÃºa siendo una dependencia del sistema: debe estar instalado en la
laptop Linux. El ejecutable abre la interfaz grÃ¡fica sin una consola adicional.
La carpeta predeterminada serÃ¡ `dist/KenjiMusicDownloader/downloads`, pero puede
cambiarse desde la ventana.

Errores comunes de assets o icono en Linux:

- Si el logo no aparece, verifica que `assets/` se haya incluido con
  `--add-data "assets:assets"`.
- En Linux el icono visible depende del entorno de escritorio y del tipo de
  paquete final; la app usa el PNG incluido para la ventana y conserva el `.ico`
  principalmente para Windows.

Para distribuirlo manualmente, copia a la misma carpeta:

```text
KenjiMusicDownloader/
â”œâ”€â”€ KenjiMusicDownloader
â”œâ”€â”€ KenjiUpdateInstaller
â”œâ”€â”€ _internal/
â””â”€â”€ README.md
```

Si hace falta restaurar el permiso de ejecuciÃ³n:

```bash
chmod +x KenjiMusicDownloader/KenjiMusicDownloader
chmod +x KenjiMusicDownloader/KenjiUpdateInstaller
./KenjiMusicDownloader/KenjiMusicDownloader
```

## PublicaciÃ³n multiplataforma

DespuÃ©s de copiar ambos paquetes a una misma carpeta `dist`, genera nuevamente
los manifests desde la raÃ­z del proyecto:

```powershell
.\.venv\Scripts\python.exe scripts\generate_update_manifest.py
```

En Linux, el comando equivalente es:

```bash
python3 scripts/generate_update_manifest.py
```

La utilidad busca los nombres exactos de la versiÃ³n centralizada, calcula los
SHA-256 reales y crea:

```text
dist/update-windows.json
dist/update-linux.json
dist/update.json
```

Para GitHub Release `v1.0.7`, sube obligatoriamente:

```text
KenjiMusicDownloader-v1.0.7-Windows-x64.zip
KenjiMusicDownloader-v1.0.7-Linux-x64.tar.gz
update.json
```

Los manifests especÃ­ficos son auxiliares y opcionales en la release. No edites
hashes manualmente: vuelve a ejecutar el generador cada vez que cambie un
paquete.

## Diagnosticar tiempos de descarga

La GUI muestra un resumen y la consola imprime lÃ­neas con el prefijo
`[TIEMPO]`. Para comparar dos pruebas, revisa especialmente:

- `ValidaciÃ³n`: procesamiento local de la URL; normalmente debe ser casi cero.
- `Inicio yt-dlp`: creaciÃ³n de `YoutubeDL` y carga de sus componentes.
- `ConexiÃ³n/obtenciÃ³n`: tiempo dentro del extractor de YouTube antes del primer byte.
- `Primer progreso recibido`: tiempo acumulado hasta comenzar la descarga real.
- `Descarga`: transferencia del audio.
- `ConversiÃ³n`: trabajo de FFmpeg despuÃ©s de terminar la transferencia.
- `Total`: flujo completo desde la validaciÃ³n hasta el archivo final.

Si `ValidaciÃ³n` e `Inicio yt-dlp` son bajos, pero `ConexiÃ³n/obtenciÃ³n` es alta,
la espera estÃ¡ dentro de YouTube/yt-dlp (red, respuestas del extractor o retos
JavaScript), no en la GUI ni en una segunda llamada de la aplicaciÃ³n.

La interfaz muestra un aviso al superar 30 segundos de conexiÃ³n y otro al
superar 90 segundos. Puedes seguir esperando o pulsar `Cancelar`. La
cancelaciÃ³n es cooperativa: la ventana responde inmediatamente, pero una
peticiÃ³n de red que ya estÃ© en curso puede tardar hasta su timeout en cerrarse.

Si esta etapa tarda demasiado, actualiza primero `yt-dlp` dentro del entorno:

```bash
python -m pip install --upgrade yt-dlp
```

### Probar yt-dlp directamente

Con el entorno virtual activado, sustituye `URL_DEL_VIDEO` por un enlace entre
comillas. `--simulate` realiza la conexiÃ³n y extracciÃ³n, pero no descarga el
archivo:

```bash
python -m yt_dlp --version
python -m yt_dlp --force-ipv4 --socket-timeout 20 --no-playlist --simulate --verbose "URL_DEL_VIDEO"
```

Para comparar con la selecciÃ³n automÃ¡tica de red, repite sin IPv4 forzado:

```bash
python -m yt_dlp --socket-timeout 20 --no-playlist --simulate --verbose "URL_DEL_VIDEO"
```

Si la primera prueba es claramente mÃ¡s rÃ¡pida, conserva IPv4 forzado. Esta
opciÃ³n se controla en `src/config.py`:

```python
FORCE_IPV4 = True  # Activado
FORCE_IPV4 = False  # Desactivado
SOCKET_TIMEOUT_SECONDS = 20
```

## Archivos locales y publicaciÃ³n segura

El repositorio conserva Ãºnicamente `downloads/.gitkeep` para crear la carpeta
vacÃ­a. `.gitignore` excluye audios, entornos virtuales, cachÃ©s, builds, logs,
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
Los paquetes temporales de actualizaciÃ³n usan la subcarpeta `updates/` y no se
suben a Git.

## Estructura

```text
kenji-music-downloader/
â”œâ”€â”€ src/
â”‚   â”œâ”€â”€ __init__.py
â”‚   â”œâ”€â”€ gui.py
â”‚   â”œâ”€â”€ main.py
â”‚   â”œâ”€â”€ downloader.py
â”‚   â”œâ”€â”€ audio_formats.py
â”‚   â”œâ”€â”€ user_settings.py
â”‚   â”œâ”€â”€ platform_utils.py
â”‚   â”œâ”€â”€ download_history.py
â”‚   â”œâ”€â”€ diagnostics.py
â”‚   â”œâ”€â”€ tool_manager.py
â”‚   â”œâ”€â”€ error_log.py
â”‚   â”œâ”€â”€ updates.py
â”‚   â”œâ”€â”€ update_manager.py
â”‚   â”œâ”€â”€ release_manifest.py
â”‚   â”œâ”€â”€ update_diagnostics.py
â”‚   â”œâ”€â”€ update_installer.py
â”‚   â”œâ”€â”€ security.py
â”‚   â””â”€â”€ config.py
â”œâ”€â”€ downloads/
â”‚   â””â”€â”€ .gitkeep
â”œâ”€â”€ assets/
â”‚   â”œâ”€â”€ logo_main.png
â”‚   â”œâ”€â”€ logo_main_header.png
â”‚   â”œâ”€â”€ logo_main_icon.png
â”‚   â”œâ”€â”€ logo_main.ico
â”‚   â”œâ”€â”€ updater_logo.png
â”‚   â”œâ”€â”€ updater_logo_icon.png
â”‚   â”œâ”€â”€ updater_logo.ico
â”‚   â”œâ”€â”€ typography_reference.png
â”‚   â””â”€â”€ interface_reference_new.png
â”œâ”€â”€ tests/
â”‚   â”œâ”€â”€ test_downloader.py
â”‚   â”œâ”€â”€ test_download_history.py
â”‚   â”œâ”€â”€ test_diagnostics.py
â”‚   â”œâ”€â”€ test_config.py
â”‚   â”œâ”€â”€ test_tool_manager.py
â”‚   â”œâ”€â”€ test_error_log.py
â”‚   â”œâ”€â”€ test_platform_utils.py
â”‚   â”œâ”€â”€ test_user_settings.py
â”‚   â”œâ”€â”€ test_updates.py
â”‚   â”œâ”€â”€ test_update_manager.py
â”‚   â”œâ”€â”€ test_release_manifest.py
â”‚   â”œâ”€â”€ test_update_diagnostics.py
â”‚   â”œâ”€â”€ test_update_installer.py
â”‚   â””â”€â”€ test_security.py
â”œâ”€â”€ scripts/
â”‚   â”œâ”€â”€ build_windows.ps1
â”‚   â”œâ”€â”€ build_linux.sh
â”‚   â””â”€â”€ generate_update_manifest.py
â”œâ”€â”€ kenji-music-downloader.spec
â”œâ”€â”€ release/
â”‚   â””â”€â”€ update.example.json
â”œâ”€â”€ requirements.txt
â”œâ”€â”€ README.md
â””â”€â”€ .gitignore
```

## Archivos principales

- `src/gui.py`: ventana, logotipo, tema visual neÃ³n, selecciÃ³n de carpeta,
  progreso y mensajes al usuario.
- `src/main.py`: versiÃ³n alternativa por consola.
- `src/security.py`: valida el dominio y extrae un identificador de video seguro.
- `src/downloader.py`: descarga y convierte al formato elegido mediante `yt-dlp` y FFmpeg.
- `src/audio_formats.py`: catÃ¡logo permitido de formatos, cÃ³decs y extensiones.
- `src/user_settings.py`: preferencias JSON portables del usuario.
- `src/platform_utils.py`: apertura segura de carpetas en Windows, Linux y macOS.
- `src/download_history.py`: historial JSON persistente y limitado.
- `src/diagnostics.py`: verificaciÃ³n de herramientas, carpeta y conexiÃ³n.
- `src/tool_manager.py`: resoluciÃ³n, descarga y extracciÃ³n segura de FFmpeg/FFprobe.
- `src/error_log.py`: registro local de errores importantes.
- `src/updates.py`: consulta GitHub Releases, compara versiones y conserva
  metadatos de assets.
- `src/update_manager.py`: selecciona assets, lee el manifest, descarga, valida
  SHA-256 y lanza el helper.
- `src/release_manifest.py`: genera manifests especÃ­ficos y combinado usando
  los hashes reales de los paquetes presentes en `dist`.
- `src/update_diagnostics.py`: dry-run temporal del manifest, descarga, hash y
  extracciÃ³n para Windows o Linux sin instalar archivos.
- `src/update_installer.py`: helper separado con extracciÃ³n segura, backup,
  reemplazo, rollback y reinicio.
- `src/config.py`: versiÃ³n, rutas portables y validaciÃ³n de la carpeta de salida.
- `tests/test_security.py`: verifica que se acepten y rechacen los enlaces correctos.
- `tests/test_downloader.py`: verifica el progreso consumido por la interfaz.
- `assets/`: logotipo oficial, icono `.ico`, PNG optimizados y referencia visual.
- `kenji-music-downloader.spec`: configuraciÃ³n portable de PyInstaller con
  assets e icono del ejecutable.
- `scripts/build_linux.sh`: construcciÃ³n repetible del ejecutable Linux.
- `scripts/build_windows.ps1`: pruebas, construcciÃ³n y ZIP publicable para Windows.
- `scripts/generate_update_manifest.py`: crea los manifests de publicaciÃ³n desde
  los paquetes existentes en `dist`.
- `requirements.txt`: dependencias de Python, incluido PyInstaller.
- `.gitignore`: excluye descargas, entornos y archivos generados.

## Actualizar yt-dlp

YouTube cambia con frecuencia. Si una descarga deja de funcionar, actualiza
`yt-dlp` dentro del entorno virtual antes de investigar otros errores:

```bash
python -m pip install --upgrade yt-dlp
```

