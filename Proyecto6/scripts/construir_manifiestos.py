"""Construye los manifiestos de stream de referencia y C1 desde las capturas del carrito (P5).

Las 78 imagenes de `Proyecto5/datos/evaluacion/` (ESP32-CAM del carrito, 400x296) se
reparten en dos conjuntos DISJUNTOS para no fijar umbrales con los mismos frames que se
demuestran:

  referencia.csv  S2, S3, S5  (42 frames)  -> observaciones de referencia y umbrales
  c1_normal.csv   S1, S4, S6  (36 frames)  -> escenario C1, operacion normal

Orden: por secuencia y por `t_capture_ms` del manifiesto del P5. El SHA-256 se copia del
manifiesto del P5; la fuente lo verifica antes de inferir.

    python scripts/construir_manifiestos.py
"""

from __future__ import annotations

import csv
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
ORIGEN = RAIZ / "Proyecto5/datos/evaluacion/capturas.csv"
DESTINO = RAIZ / "Proyecto6/escenarios"
CONJUNTOS = {"referencia.csv": ("S2", "S3", "S5"), "c1_normal.csv": ("S1", "S4", "S6")}


def main() -> None:
    with ORIGEN.open(encoding="utf-8", newline="") as f:
        filas = list(csv.DictReader(f))
    DESTINO.mkdir(parents=True, exist_ok=True)
    for nombre, secuencias in CONJUNTOS.items():
        sel = [r for r in filas if r["sequence_id"] in secuencias]
        sel.sort(key=lambda r: (secuencias.index(r["sequence_id"]), float(r["t_capture_ms"])))
        with (DESTINO / nombre).open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(["path", "sha256", "sequence_id"])
            for r in sel:
                w.writerow(
                    [f"Proyecto5/datos/evaluacion/{r['path']}", r["sha256"], r["sequence_id"]]
                )
        print(nombre, len(sel))


if __name__ == "__main__":
    main()
