"""Politica de confianza: dos umbrales y tres zonas, mas estados aparte.

Unidad de analisis: el FRAME. Su puntuacion principal `s` es la mayor confianza entre sus
detecciones candidatas (las que salen del detector con piso 0.05 y NMS).

    s >= superior            -> "aceptada"  (aceptada por politica; no afirma acierto)
    inferior <= s < superior -> "duda"
    s < inferior             -> "baja"

Estados aparte, sin puntuacion ni zona (nunca se les asigna confianza 0):
    "sin_detecciones"  el detector corrio y no emitio candidatas
    "error"            la imagen no se pudo leer o el detector fallo

Cada candidata tambien recibe su zona, para poder observarla, pero las proporciones de la
politica y de las reglas se calculan por frame (denominador = frames puntuados).
"""

from __future__ import annotations

ACEPTADA, DUDA, BAJA = "aceptada", "duda", "baja"
OK, SIN_DETECCIONES, ERROR = "ok", "sin_detecciones", "error"


def zona(score: float, inferior: float, superior: float) -> str:
    if score >= superior:
        return ACEPTADA
    if score >= inferior:
        return DUDA
    return BAJA


def clasificar_frame(
    scores: list[float], inferior: float, superior: float
) -> tuple[str, float | None, str | None]:
    """(estado, score_principal, zona) de un frame inferido sin error."""
    if not scores:
        return SIN_DETECCIONES, None, None
    s = max(scores)
    return OK, s, zona(s, inferior, superior)
