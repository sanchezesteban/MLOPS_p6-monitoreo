"""Compara una corrida reproducida con la evidencia versionada (mismo manifiesto y config).

    PYTHONPATH=src python scripts/comparar_corridas.py var/c1 evidencias/escenarios/c1-normal

Compara frame a frame: SHA-256 de la imagen de origen, estado, zona y score principal
(diferencia maxima), y ventana de apertura y resolucion de cada alerta. Codigo 1 si difieren
estados, zonas o alertas, o si |delta score| > 1e-4.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def jl(p: Path) -> list[dict]:
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]


def main(nuevo: str, original: str) -> int:
    a, b = jl(Path(nuevo) / "eventos.jsonl"), jl(Path(original) / "eventos.jsonl")
    clave = ("image_source_sha256", "estado", "zona")
    iguales = len(a) == len(b) and all(
        [x[k] for k in clave] == [y[k] for k in clave] for x, y in zip(a, b, strict=True)
    )
    dif = max(
        (
            abs(x["score_principal"] - y["score_principal"])
            for x, y in zip(a, b, strict=False)
            if x["score_principal"] is not None and y["score_principal"] is not None
        ),
        default=0.0,
    )

    def alertas(d: str) -> list[tuple]:
        return [
            (r["rule_id"], r["abierta_ventana"], r["resuelta_ventana"])
            for r in jl(Path(d) / "alertas.jsonl")
        ]

    al_ok = alertas(nuevo) == alertas(original)
    res = {
        "frames": [len(a), len(b)],
        "estados_zonas_iguales": iguales,
        "max_abs_delta_score": dif,
        "alertas_iguales": al_ok,
        "alertas": alertas(nuevo),
    }
    print(json.dumps(res))
    return 0 if iguales and al_ok and dif <= 1e-4 else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1], sys.argv[2]))
