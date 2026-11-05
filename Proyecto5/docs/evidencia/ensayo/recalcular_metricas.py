"""Recálculo independiente de TP/FP/FN, precisión, recall y F1 a IoU 0.50 (ensayo P5-17).

No importa nada de `p5`: lee el COCO de la verdad de referencia y el JSONL de detecciones
del contrato v1 y aplica el protocolo de la Fase 4A del prompt de evaluación:

- por cuadro y clase, predicciones ordenadas por confianza descendente;
- cada predicción se empareja con la caja real libre de mayor IoU (>= umbral);
- una caja real se usa una sola vez; duplicados = FP; reales sin pareja = FN;
- clase equivocada = FP para la predicción y FN para la clase real;
- se agregan todos los cuadros, incluidos los negativos.

Uso (desde `Proyecto5/`):
    python docs/evidencia/ensayo/recalcular_metricas.py \
        --gt datos/anotaciones.json --pred <detecciones.jsonl> [--iou 0.5] [--salida x.json]
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

CLASES = ("person", "dog", "cat")


def iou(a: list[float], b: list[float]) -> float:
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def cargar_gt(ruta: Path) -> dict[str, list[tuple[str, list[float]]]]:
    coco = json.loads(ruta.read_text(encoding="utf-8"))
    nombres = {c["id"]: c["name"] for c in coco["categories"]}
    imagenes = {i["id"]: Path(i["file_name"]).name for i in coco["images"]}
    gt: dict[str, list[tuple[str, list[float]]]] = {nombre: [] for nombre in imagenes.values()}
    for a in coco["annotations"]:
        x, y, w, h = a["bbox"]  # COCO: xywh
        gt[imagenes[a["image_id"]]].append((nombres[a["category_id"]], [x, y, x + w, y + h]))
    return gt


def cargar_pred(ruta: Path) -> dict[str, list[tuple[str, float, list[float]]]]:
    pred: dict[str, list[tuple[str, float, list[float]]]] = {}
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        evento = json.loads(linea)
        nombre = Path(evento["image_path"]).name
        pred[nombre] = [
            (d["class_name"], d["confidence"], d["bbox"])
            for d in evento["detections"]
            if evento["status"] == "ok" and d["class_name"] in CLASES
        ]
    return pred


def f1(c: Counter) -> float:
    denominador = 2 * c["tp"] + c["fp"] + c["fn"]
    return 2 * c["tp"] / denominador if denominador else 0.0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--gt", type=Path, required=True)
    parser.add_argument("--pred", type=Path, required=True)
    parser.add_argument("--iou", type=float, default=0.5)
    parser.add_argument("--salida", type=Path)
    args = parser.parse_args()

    gt, pred = cargar_gt(args.gt), cargar_pred(args.pred)
    faltan = sorted(set(gt) - set(pred))  # sin predicción: sus objetos cuentan como FN
    por_clase: dict[str, Counter] = defaultdict(Counter)
    for cuadro, reales in gt.items():
        predichas = pred.get(cuadro, [])
        for clase in CLASES:
            cajas = [b for c, b in reales if c == clase]
            usadas: set[int] = set()
            for _, caja in sorted(
                ((s, b) for c, s, b in predichas if c == clase), key=lambda t: -t[0]
            ):
                mejor, indice = args.iou, None
                for i, real in enumerate(cajas):
                    if i not in usadas and (v := iou(caja, real)) >= mejor:
                        mejor, indice = v, i
                if indice is None:
                    por_clase[clase]["fp"] += 1
                else:
                    usadas.add(indice)
                    por_clase[clase]["tp"] += 1
            por_clase[clase]["fn"] += len(cajas) - len(usadas)

    micro = sum(por_clase.values(), Counter())
    resultado = {
        "cuadros": len(gt),
        "cuadros_sin_prediccion": faltan,
        "iou": args.iou,
        "micro": {
            **{k: micro[k] for k in ("tp", "fp", "fn")},
            "precision": micro["tp"] / (micro["tp"] + micro["fp"]) if micro["tp"] else 0.0,
            "recall": micro["tp"] / (micro["tp"] + micro["fn"]) if micro["tp"] else 0.0,
            "f1": f1(micro),
        },
        "por_clase": {
            c: {**{k: por_clase[c][k] for k in ("tp", "fp", "fn")}, "f1": f1(por_clase[c])}
            for c in CLASES
        },
        "puntos_1_4": math.floor(12 * f1(micro)) / 2,
    }
    texto = json.dumps(resultado, indent=2, ensure_ascii=False)
    print(texto)
    if args.salida:
        args.salida.write_text(texto + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
