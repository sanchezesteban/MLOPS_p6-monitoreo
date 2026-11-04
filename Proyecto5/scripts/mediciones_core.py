"""Cálculos y exportación exclusiva para mediciones, fuera de los datasets."""

from __future__ import annotations

import argparse
import json
import math
import statistics
import uuid
from datetime import datetime, timezone
from pathlib import Path

OUTPUT = Path(__file__).resolve().parents[1] / "resultados" / "mediciones"


def positive(value):
    result = float(value)
    if not math.isfinite(result) or result <= 0:
        raise ValueError("El valor debe ser finito y mayor que cero")
    return result


def seconds(value):
    try:
        return positive(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def repetitions(value):
    result = int(value)
    if result < 3:
        raise argparse.ArgumentTypeError("Realizar al menos tres repeticiones")
    return result


def statistics_of(values):
    if not values:
        raise ValueError("Se necesita al menos una medición")
    if any(not math.isfinite(v) for v in values):
        raise ValueError("Medición no finita")
    return {
        "n": len(values),
        "media": statistics.mean(values),
        "minimo": min(values),
        "maximo": max(values),
        "rango": max(values) - min(values),
        "desviacion_estandar_muestral": statistics.stdev(values) if len(values) > 1 else None,
    }


def export_report(report, folder, prefix):
    """Un JSON nuevo por ejecución; nunca abre CSV de capturas ni reemplaza informes."""
    text = json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    # La herramienta también se ejecuta con Python 3.10 del operador.
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")  # noqa: UP017
    path = folder / f"{prefix}_{stamp}_{uuid.uuid4().hex}.json"
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    return path
