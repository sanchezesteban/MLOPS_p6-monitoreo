"""Recálculo independiente de p50/p95/máximo del benchmark (ensayo P5-17).

No importa `p5` ni numpy: lee `tiempos.csv`, descarta los calentamientos y los intentos
fallidos y calcula los percentiles con interpolación lineal (el mismo método que
`numpy.percentile(method="linear")`: posición (n - 1) · q).

Uso (desde `Proyecto5/`):
    python docs/evidencia/ensayo/recalcular_percentiles.py --tiempos <carpeta>/tiempos.csv \
        [--resumen <carpeta>/resumen.json] [--salida x.json]
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

ETAPAS = (
    "preprocesamiento_ms",
    "inferencia_ms",
    "posprocesamiento_ms",
    "politica_adaptador_ms",
    "total_local_ms",
)


def percentil(valores: list[float], q: float) -> float:
    ordenados = sorted(valores)
    posicion = (len(ordenados) - 1) * q
    abajo, arriba = math.floor(posicion), math.ceil(posicion)
    fraccion = posicion - abajo
    return ordenados[abajo] + (ordenados[arriba] - ordenados[abajo]) * fraccion


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tiempos", type=Path, required=True)
    parser.add_argument("--resumen", type=Path, help="resumen.json del equipo para contrastar")
    parser.add_argument("--salida", type=Path)
    args = parser.parse_args()

    with args.tiempos.open(encoding="utf-8", newline="") as archivo:
        filas = list(csv.DictReader(archivo))
    calentamientos = [f for f in filas if f["fase"] == "calentamiento"]
    validas = [f for f in filas if f["fase"] == "medicion" and f["estado"] == "ok"]
    fallidas = [f for f in filas if f["estado"] != "ok"]

    equipo = {}
    if args.resumen:
        equipo = json.loads(args.resumen.read_text(encoding="utf-8"))["estadisticas"]

    resultado: dict = {
        "intentos": len(filas),
        "calentamientos_excluidos": len(calentamientos),
        "mediciones_validas": len(validas),
        "fallidas": len(fallidas),
        "metodo": "interpolacion lineal, posicion (n-1)*q",
        "etapas": {},
    }
    for etapa in ETAPAS:
        valores = [float(f[etapa]) for f in validas]
        propio = {
            "p50_ms": percentil(valores, 0.50),
            "p95_ms": percentil(valores, 0.95),
            "max_ms": max(valores),
        }
        if etapa in equipo:
            propio["coincide_con_resumen"] = all(
                abs(propio[k] - equipo[etapa][k]) < 1e-9 for k in ("p50_ms", "p95_ms", "max_ms")
            )
        resultado["etapas"][etapa] = propio

    texto = json.dumps(resultado, indent=2, ensure_ascii=False)
    print(texto)
    if args.salida:
        args.salida.write_text(texto + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
