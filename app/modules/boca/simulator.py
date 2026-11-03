from app.modules.boca.schemas import DatosBoca

def generar_captura_simulada(
    nombre_imagen: str = "boca_demo_01.jpg",
    observacion_tecnica: str | None = "Imagen ficticia enfocada"
) -> DatosBoca:
    """Genera datos simulados válidos para el módulo de Boca."""
    return DatosBoca(
        nombre_imagen=nombre_imagen,
        observacion_tecnica=observacion_tecnica
    )