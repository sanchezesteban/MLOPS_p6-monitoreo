"""Prepara la secuencia del escenario C2 (baja confianza) a partir de capturas reales del carrito.

Entrada: las imagenes de las secuencias S2-S6 de `Proyecto5/datos/evaluacion/` (ESP32-CAM).
Transformacion: desenfoque gaussiano de radio `--radio` (por defecto 2 px), que simula una
camara desenfocada o en movimiento. Es deterministica y se guarda en JPEG calidad 92.

Las puntuaciones de C2 NO se inyectan: el monitor corre el detector real sobre estas
imagenes. El manifiesto `escenarios/c2_baja_confianza.csv` registra origen, transformacion y
SHA-256 de cada imagen generada.

    python scripts/preparar_c2.py
"""

from __future__ import annotations

import argparse
import csv
import hashlib
from pathlib import Path

from PIL import Image, ImageFilter

RAIZ = Path(__file__).resolve().parents[2]
ORIGEN = RAIZ / "Proyecto5/datos/evaluacion/capturas.csv"
SECUENCIAS = ("S2", "S3", "S4", "S5", "S6")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--radio", type=float, default=2.0)
    p.add_argument("--destino", default=str(RAIZ / "Proyecto6/datos/c2_desenfoque"))
    p.add_argument("--manifiesto", default=str(RAIZ / "Proyecto6/escenarios/c2_baja_confianza.csv"))
    a = p.parse_args()
    destino = Path(a.destino)
    destino.mkdir(parents=True, exist_ok=True)
    with ORIGEN.open(encoding="utf-8", newline="") as f:
        filas = [r for r in csv.DictReader(f) if r["sequence_id"] in SECUENCIAS]
    filas.sort(key=lambda r: (SECUENCIAS.index(r["sequence_id"]), float(r["t_capture_ms"])))
    with open(a.manifiesto, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["path", "sha256", "sequence_id", "origen", "origen_sha256", "transformacion"])
        for r in filas:
            src = RAIZ / "Proyecto5/datos/evaluacion" / r["path"]
            out = destino / f"c2_{Path(r['path']).name}"
            with Image.open(src) as im:
                im.convert("RGB").filter(ImageFilter.GaussianBlur(a.radio)).save(out, quality=92)
            sha = hashlib.sha256(out.read_bytes()).hexdigest()
            w.writerow(
                [
                    out.relative_to(RAIZ).as_posix(),
                    sha,
                    r["sequence_id"],
                    f"Proyecto5/datos/evaluacion/{r['path']}",
                    r["sha256"],
                    f"GaussianBlur(radius={a.radio}); JPEG q=92",
                ]
            )
    print(f"{len(filas)} imagenes en {destino}")


if __name__ == "__main__":
    main()
