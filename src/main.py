"""Interfaz mínima por consola de Kenji Music Downloader."""

from time import perf_counter

from src.config import APP_NAME, ConfigurationError, prepare_environment
from src.downloader import AudioDownloader, AudioDownloadError
from src.security import InvalidYouTubeURLError, validate_and_normalize_youtube_url


def show_status(message: str) -> None:
    """Muestra mensajes de progreso; puede sustituirse por una GUI en el futuro."""
    print(message)


def run() -> int:
    """Ejecuta el flujo interactivo y devuelve un código de salida del sistema."""
    print(f"\n=== {APP_NAME} ===")
    print("Descarga un video individual de YouTube como archivo MP3.\n")

    operation_started_at: float | None = None
    try:
        downloads_directory = prepare_environment()
        raw_url = input("Pega el enlace de YouTube: ")
        operation_started_at = perf_counter()
        validation_started_at = perf_counter()
        try:
            safe_url = validate_and_normalize_youtube_url(raw_url)
        finally:
            validation_seconds = perf_counter() - validation_started_at
            print(f"[TIEMPO] Validación: {validation_seconds:.2f}s", flush=True)

        downloader = AudioDownloader(downloads_directory, show_status)
        output_path = downloader.download_mp3(safe_url)
    except (InvalidYouTubeURLError, ConfigurationError, AudioDownloadError) as error:
        print(f"\nError: {error}")
        return 1
    except (EOFError, KeyboardInterrupt):
        print("\nOperación cancelada.")
        return 130
    finally:
        if operation_started_at is not None:
            total_seconds = perf_counter() - operation_started_at
            print(f"[TIEMPO] Total: {total_seconds:.2f}s", flush=True)

    print("\n¡Descarga completada!")
    print(f"Archivo guardado en: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
