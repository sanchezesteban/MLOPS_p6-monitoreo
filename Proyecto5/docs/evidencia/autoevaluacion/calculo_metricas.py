"""Matching propio, independiente de p5.metricas (autoevaluacion P5-17).

Uso: python calculo_metricas.py <anotaciones.json> <detecciones.jsonl>
Por clase y cuadro: predicciones por confianza descendente, cada una con la caja real libre
de mayor IoU de su clase (IoU >= 0.5); una caja real solo se usa una vez.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

CLASES = ("person", "cat", "dog")


def iou(a: tuple, b: tuple) -> float:
    ancho = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    alto = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ancho * alto
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union else 0.0


def main(gt_path: str, pred_path: str) -> None:
    coco = json.loads(Path(gt_path).read_text(encoding="utf-8"))
    nombres = {c["id"]: c["name"] for c in coco["categories"]}
    reales = defaultdict(list)
    for a in coco["annotations"]:
        x, y, w, h = a["bbox"]
        reales[a["image_id"]].append((nombres[a["category_id"]], (x, y, x + w, y + h)))
    cuadros = {im["frame_id"]: im["id"] for im in coco["images"]}
    preds = defaultdict(list)
    for linea in Path(pred_path).read_text(encoding="utf-8").splitlines():
        evento = json.loads(linea)
        for d in evento["detections"]:
            preds[evento["frame_id"]].append((d["class_name"], d["confidence"], tuple(d["bbox"])))
    total = Counter()
    for frame_id, image_id in cuadros.items():
        for clase in CLASES:
            cajas = [b for c, b in reales[image_id] if c == clase]
            usada = [False] * len(cajas)
            candidatas = sorted((p for p in preds[frame_id] if p[0] == clase), key=lambda p: -p[1])
            for _, _, caja in candidatas:
                mejor, indice = 0.0, -1
                for i, real in enumerate(cajas):
                    valor = iou(caja, real)
                    if not usada[i] and valor > mejor:
                        mejor, indice = valor, i
                if mejor >= 0.5:
                    usada[indice] = True
                    total["tp"] += 1
                else:
                    total["fp"] += 1
            total["fn"] += usada.count(False)
    tp, fp, fn = total["tp"], total["fp"], total["fn"]
    f1 = 2 * tp / (2 * tp + fp + fn)
    print(f"micro TP={tp} FP={fp} FN={fn}")
    print(f"precision={tp / (tp + fp):.6f} recall={tp / (tp + fn):.6f} F1={f1:.17g}")
    print(f"puntos 1.4 = floor(12 x F1) / 2 = {math.floor(12 * f1) / 2}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
