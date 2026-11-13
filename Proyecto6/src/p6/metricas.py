"""Calculo de las metricas base G1-G7 a partir de observaciones primarias.

Las mismas funciones las usa el monitor (en linea) y `p6.recalcular` (fuera de linea, desde
los JSONL exportados). Ninguna devuelve 0 cuando no hay observaciones: devuelve `None`
("sin datos"), que el portal y los reportes muestran como evidencia insuficiente.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from typing import Any


def percentil_rango(valores: Sequence[float], p: float) -> float | None:
    """Percentil por rango mas cercano: el valor en la posicion ceil(p*n) (1-indexada)."""
    if not valores:
        return None
    orden = sorted(valores)
    k = max(1, math.ceil(p * len(orden)))
    return orden[k - 1]


def g1_inferencia(obs: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """G1. Tiempo de `session.run` (ms) por frame inferido. Excluye frames con error."""
    v = [o["inferencia_ms"] for o in obs if o.get("inferencia_ms") is not None]
    return {"n": len(v), "p50_ms": percentil_rango(v, 0.50), "p95_ms": percentil_rango(v, 0.95)}


def g2_fps_procesamiento(obs: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """G2. Frames inferidos / segundos entre la emision del primer frame y el fin del ultimo.

    Frames inferidos = estado ok o sin_detecciones (el modelo corrio). Con <2 frames o
    duracion 0 no hay tasa definida -> None.
    """
    inferidos = [o for o in obs if o.get("inferencia_ms") is not None]
    if len(obs) < 2 or not inferidos:
        return {"n": len(inferidos), "duracion_s": None, "fps": None}
    t0 = min(o["t_captura_mono"] for o in obs)
    t1 = max(o["t_fin_mono"] for o in obs)
    dur = t1 - t0
    return {
        "n": len(inferidos),
        "duracion_s": dur,
        "fps": (len(inferidos) / dur) if dur > 0 else None,
    }


def g3_rss(muestras: Sequence[float]) -> dict[str, Any]:
    """G3. Memoria residente (RSS, MiB) del proceso de monitoreo, muestreada por ventana."""
    if not muestras:
        return {"n": 0, "max_mib": None, "media_mib": None}
    return {
        "n": len(muestras),
        "max_mib": max(muestras),
        "media_mib": sum(muestras) / len(muestras),
    }


def g4_baja(eventos: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """G4. Frames en zona baja / frames puntuados (estado ok). Excluye sin_detecciones y error."""
    puntuados = [e for e in eventos if e["estado"] == "ok"]
    bajos = sum(1 for e in puntuados if e["zona"] == "baja")
    return {
        "puntuados": len(puntuados),
        "bajos": bajos,
        "proporcion": (bajos / len(puntuados)) if puntuados else None,
    }


CAMPOS_TRAZA = (
    "event_id",
    "run_id",
    "frame_id",
    "source_id",
    "t_captura",
    "image_source_sha256",
    "model_sha256",
    "detector_config_sha256",
    "config_sha256",
    "estado",
    "window_id",
)


def evento_trazable(e: dict[str, Any], captura_ok: bool | None) -> bool:
    """Identidad completa y, si declara captura, la captura resuelve y su SHA coincide."""
    if any(e.get(c) in (None, "") for c in CAMPOS_TRAZA):
        return False
    if e["estado"] == "ok" and (e.get("score_principal") is None or e.get("zona") is None):
        return False
    if e.get("image_ref"):
        return bool(captura_ok)
    return True


def g5_trazabilidad(resultados: Sequence[bool]) -> dict[str, Any]:
    """G5. Eventos trazables / eventos registrados."""
    n = len(resultados)
    ok = sum(resultados)
    return {"eventos": n, "trazables": ok, "cobertura": (ok / n) if n else None}


def g6_version(eventos: Iterable[dict[str, Any]], esperado: str) -> dict[str, Any]:
    """G6. Eventos cuyo model_sha256 reportado coincide con el esperado (descriptor)."""
    ev = list(eventos)
    coinciden = sum(1 for e in ev if e.get("model_sha256") == esperado)
    return {
        "eventos": len(ev),
        "coinciden": coinciden,
        "proporcion": (coinciden / len(ev)) if ev else None,
        "versiones_reportadas": sorted(
            {e.get("model_sha256") for e in ev if e.get("model_sha256")}
        ),
    }


def g7_activas(alertas: Iterable[dict[str, Any]], window_seq: int) -> int:
    """G7. Alertas abiertas al cierre de la ventana `window_seq`.

    Abierta = abierta en una ventana <= window_seq y no resuelta en una ventana <= window_seq.
    """
    n = 0
    for a in alertas:
        if a["abierta_ventana"] <= window_seq and (
            a.get("resuelta_ventana") is None or a["resuelta_ventana"] > window_seq
        ):
            n += 1
    return n
