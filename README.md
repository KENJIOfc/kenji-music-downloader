# Kenji Music Downloader

Aplicación de escritorio para descargar el audio de un video individual de
YouTube y convertirlo a MP3. Está escrita en Python, ofrece una interfaz gráfica
con Tkinter, usa la API de `yt-dlp` y delega la conversión a FFmpeg.

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
- Guarda como `Título.mp3`, sin ID de YouTube; si existe, usa `Título (1).mp3`.
- No incluye historial, playlists ni instaladores de terceros.

## Requisitos

- Python 3.10 o posterior.
- Tkinter (incluido normalmente con Python en Windows).
- FFmpeg disponible en el `PATH` del sistema.
- `yt-dlp-ejs` y Deno, instalados automáticamente mediante `requirements.txt`.
- Conexión a Internet durante las descargas.

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

Instala FFmpeg. Una opción mediante Windows Package Manager es:

```powershell
winget install --id Gyan.FFmpeg --exact
```

Cierra y vuelve a abrir PowerShell si el comando todavía no aparece. Comprueba
la instalación, ejecuta las pruebas y abre la interfaz gráfica:

```powershell
ffmpeg -version
python -m unittest discover -s tests -v
python -m src.gui
```

La versión por consola sigue disponible con `python -m src.main`.

Si PowerShell impide activar el entorno virtual, puedes ejecutar sin activarlo:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m src.gui
```

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
./dist/kenji-music-downloader
```

El comando equivalente, si prefieres ejecutarlo manualmente, es:

```bash
python -m PyInstaller --clean --noconfirm kenji-music-downloader.spec
mkdir -p dist/downloads
```

El ejecutable se crea en `dist/kenji-music-downloader`. FFmpeg continúa siendo
una dependencia del sistema: debe estar instalado en la laptop Linux. El
ejecutable abre la interfaz gráfica sin una consola adicional. La carpeta
predeterminada será `dist/downloads`, pero puede cambiarse desde la ventana.

Para distribuirlo manualmente, copia a la misma carpeta:

```text
kenji-music-downloader
downloads/
```

Si hace falta restaurar el permiso de ejecución:

```bash
chmod +x kenji-music-downloader
./kenji-music-downloader
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

## Estructura

```text
kenji-music-downloader/
├── src/
│   ├── __init__.py
│   ├── gui.py
│   ├── main.py
│   ├── downloader.py
│   ├── security.py
│   └── config.py
├── downloads/
│   └── .gitkeep
├── tests/
│   ├── test_downloader.py
│   └── test_security.py
├── scripts/
│   └── build_linux.sh
├── kenji-music-downloader.spec
├── requirements.txt
├── README.md
└── .gitignore
```

## Archivos principales

- `src/gui.py`: ventana, selección de carpeta, progreso y mensajes al usuario.
- `src/main.py`: versión alternativa por consola.
- `src/security.py`: valida el dominio y extrae un identificador de video seguro.
- `src/downloader.py`: descarga audio y lo convierte a MP3 mediante `yt-dlp` y FFmpeg.
- `src/config.py`: rutas portables, carpeta de salida y comprobación de FFmpeg.
- `tests/test_security.py`: verifica que se acepten y rechacen los enlaces correctos.
- `tests/test_downloader.py`: verifica el progreso consumido por la interfaz.
- `kenji-music-downloader.spec`: configuración portable de PyInstaller.
- `scripts/build_linux.sh`: construcción repetible del ejecutable Linux.
- `requirements.txt`: dependencias de Python, incluido PyInstaller.
- `.gitignore`: excluye descargas, entornos y archivos generados.

## Actualizar yt-dlp

YouTube cambia con frecuencia. Si una descarga deja de funcionar, actualiza
`yt-dlp` dentro del entorno virtual antes de investigar otros errores:

```bash
python -m pip install --upgrade yt-dlp
```
