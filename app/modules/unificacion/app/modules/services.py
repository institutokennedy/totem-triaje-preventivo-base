import json
from datetime import datetime
from typing import Any, Optional

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models import EpisodioAtencion, Paciente, ResultadoModulo

from .contracts import MODULOS_REQUERIDOS

LEYENDA_LEGAL = "Informe preventivo. No constituye un diagnóstico médico."


def _attr(obj: Any, *names: str, default: Any = None) -> Any:
    """Devuelve el primer atributo existente y no nulo entre los nombres dados."""
    for n in names:
        v = getattr(obj, n, None)
        if v is not None:
            return v
    return default


def _parse_data(raw: Any) -> Optional[dict]:
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {"valor": parsed}
    except (TypeError, ValueError):
        return {"valor": str(raw)}


def _fecha_str(valor: Any) -> Optional[str]:
    if valor is None:
        return None
    return valor.isoformat() if isinstance(valor, datetime) else str(valor)


def obtener_trazabilidad_episodio(session: Session, episodio_id: int) -> dict:
    episodio = session.get(EpisodioAtencion, episodio_id)
    if episodio is None:
        raise HTTPException(status_code=404, detail="Episodio no encontrado")

    paciente_ref = _attr(episodio, "paciente_id", "paciente_dni", "dni")
    paciente = session.get(Paciente, paciente_ref) if paciente_ref is not None else None
    if paciente is None and paciente_ref is not None:
        # Fallback: la referencia puede ser el DNI y la PK otro campo.
        paciente = session.exec(
            select(Paciente).where(Paciente.dni == str(paciente_ref))
        ).first()
    if paciente is None:
        raise HTTPException(status_code=404, detail="Paciente no encontrado")

    resultados = session.exec(
        select(ResultadoModulo).where(ResultadoModulo.episodio_id == episodio_id)
    ).all()

    # Último resultado por módulo (por fecha si está disponible).
    por_modulo: dict[str, Any] = {}
    for r in sorted(resultados, key=lambda x: str(_attr(x, "fecha_hora", "created_at", default=""))):
        nombre = str(_attr(r, "modulo", "nombre_modulo", "tipo_modulo", default="")).lower()
        if nombre:
            por_modulo[nombre] = r

    detalles: list[dict] = []
    completados: list[str] = []
    faltantes: list[str] = []
    for modulo in MODULOS_REQUERIDOS:
        r = por_modulo.get(modulo)
        if r is not None:
            completados.append(modulo)
            detalles.append(
                {
                    "modulo": modulo,
                    "completado": True,
                    "fecha_hora": _fecha_str(_attr(r, "fecha_hora", "created_at")),
                    "data": _parse_data(_attr(r, "data", "datos", "resultado", "resultado_json", "data_json")),
                }
            )
        else:
            faltantes.append(modulo)
            detalles.append({"modulo": modulo, "completado": False, "fecha_hora": None, "data": None})

    nombre = " ".join(
        str(p) for p in (_attr(paciente, "nombre"), _attr(paciente, "apellido")) if p
    ) or str(_attr(paciente, "nombre_completo", default="Sin nombre"))

    return {
        "episodio_id": episodio_id,
        "paciente_dni": str(_attr(paciente, "dni", "documento", default="")),
        "paciente_nombre": nombre,
        "circuito": str(
            _attr(
                episodio,
                "tipo_circuito",
                "circuito",
                "circuito_asignado",
                default="SIN_CIRCUITO",
            )
        ),
        "estado_episodio": str(_attr(episodio, "estado", "estado_episodio", default="DESCONOCIDO")),
        "modulos_completados": completados,
        "modulos_faltantes": faltantes,
        "detalles": detalles,
        "clasificacion": None,
        "advertencia_legal": LEYENDA_LEGAL,
    }