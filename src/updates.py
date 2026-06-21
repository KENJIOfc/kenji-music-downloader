"""Punto de extensión para una futura búsqueda segura de actualizaciones."""

from dataclasses import dataclass


@dataclass(frozen=True)
class UpdateStatus:
    """Resultado que podrá devolver el servicio de actualizaciones."""

    available: bool
    message: str


def check_for_updates() -> UpdateStatus:
    """Marcador funcional: todavía no realiza conexiones ni modifica archivos."""
    return UpdateStatus(
        available=False,
        message="La búsqueda automática de actualizaciones estará disponible próximamente.",
    )
