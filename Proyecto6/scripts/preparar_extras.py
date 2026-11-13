"""Prepara las entradas de los escenarios ADICIONALES (extras S), desde capturas reales del carrito.

S-SOST · cambio sostenido con transicion y recuperacion (escenarios/s_sostenido.csv, 90 frames)
  fase normal       20 frames  S5 (12) + S4 (8 primeros), originales
  fase degradada    40 frames  S2 + S3 + S6 (10 primeros) con compresion JPEG calidad 5
                               (artefactos de bloque: camara con ancho de banda saturado)
  fase recuperacion 30 frames  S2 + S3, originales
  Inicio conocido de la condicion: frame 20 (columna `fase`), para medir tiempo de deteccion.

S-INT · interrupcion del stream y recuperacion (escenarios/s_interrupcion.csv, 80 frames)
  fase normal       20 frames  S5 + S4 (8 primeros), originales
  fase sin_senal    30 frames  la camara deja de entregar imagen: filas `fuente-sin-senal/...`
                               que no existen en disco; el monitor las registra como
                               estado=error ("imagen ausente"), sin score
  fase recuperacion 30 frames  S2 + S3, originales

Las puntuaciones salen del detector real; aqui solo se preparan entradas.

    python scripts/preparar_extras.py
"""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path

from PIL import Image

RAIZ = Path(__file__).resolve().parents[2]
P5 = RAIZ / "Proyecto5/datos/evaluacion"
ESC = RAIZ / "Proyecto6/escenarios"
DEG = RAIZ / "Proyecto6/datos/s_sostenido_jpeg5"


def secuencia(sid: str) -> list[dict[str, str]]:
    with (P5 / "capturas.csv").open(encoding="utf-8", newline="") as f:
        filas = [r for r in csv.DictReader(f) if r["sequence_id"] == sid]
    return sorted(filas, key=lambda r: float(r["t_capture_ms"]))


def original(r: dict[str, str], fase: str) -> list[str]:
    return [f"Proyecto5/datos/evaluacion/{r['path']}", r["sha256"], fase, "original"]


def jpeg5(r: dict[str, str]) -> list[str]:
    DEG.mkdir(parents=True, exist_ok=True)
    out = DEG / f"q5_{Path(r['path']).name}"
    with Image.open(P5 / r["path"]) as im:
        im.convert("RGB").save(out, "JPEG", quality=5)
    sha = hashlib.sha256(out.read_bytes()).hexdigest()
    return [
        out.relative_to(RAIZ).as_posix(),
        sha,
        "degradada",
        f"JPEG quality=5 de Proyecto5/datos/evaluacion/{r['path']} ({r['sha256'][:12]})",
    ]


def escribir(nombre: str, filas: list[list[str]]) -> None:
    with (ESC / nombre).open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["path", "sha256", "fase", "transformacion"])
        w.writerows(filas)
    print(nombre, len(filas))


def main() -> None:
    normal = [original(r, "normal") for r in secuencia("S5") + secuencia("S4")[:8]]
    recuperacion = [original(r, "recuperacion") for r in secuencia("S2") + secuencia("S3")]
    degradada = [jpeg5(r) for r in (secuencia("S2") + secuencia("S3") + secuencia("S6"))[:40]]
    escribir("s_sostenido.csv", normal + degradada + recuperacion)
    sin_senal = [
        [
            f"fuente-sin-senal/frame-{i:03d}.jpg",
            "",
            "sin_senal",
            "camara sin imagen (archivo inexistente a proposito)",
        ]
        for i in range(30)
    ]
    escribir("s_interrupcion.csv", normal + sin_senal + recuperacion)


if __name__ == "__main__":
    main()
