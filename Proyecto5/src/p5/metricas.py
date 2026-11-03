"""Metricas de deteccion auditables COCO/JSONL del contrato v1 (P5-07, #59).

No carga imagenes, pesos ni hardware. Ver docs/metricas.md para identidad y fallos.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath
from typing import Any

from p5.contrato import SCHEMA_VERSION, SCHEMAS_DIR, ContratoError, validar_evento

# Indices del descriptor del detector de Edith (PR #80), no category_id del GT.
CLASES = {"person": 0, "cat": 15, "dog": 16}
VERSION = "p5-07/1.0"


class EntradaError(ValueError):
    """Entrada estructuralmente invalida; no producir metricas sobre GT ambiguo."""


def _exigir(condicion: bool, mensaje: str) -> None:
    if not condicion:
        raise EntradaError(mensaje)


def _objeto(pares: list[tuple[str, Any]]) -> dict:
    resultado: dict = {}
    for clave, valor in pares:
        _exigir(clave not in resultado, f"clave JSON repetida: {clave}")
        resultado[clave] = valor
    return resultado


def _json(texto: str) -> Any:
    try:
        return json.loads(texto, object_pairs_hook=_objeto)
    except json.JSONDecodeError as exc:
        raise EntradaError(f"JSON invalido: {exc.msg}") from exc


def _numero(valor: Any) -> bool:
    try:
        return type(valor) in (int, float) and math.isfinite(valor)
    except OverflowError:
        return False


def _id(valor: Any) -> bool:
    return type(valor) is int or (isinstance(valor, str) and bool(valor.strip()))


def _ruta(valor: Any) -> str:
    _exigir(isinstance(valor, str) and bool(valor), "ruta relativa vacia o invalida")
    partes = valor.split("/")
    _exigir(
        not PurePosixPath(valor).is_absolute()
        and "\\" not in valor
        and ":" not in valor
        and all(p not in ("", ".", "..") for p in partes),
        f"ruta no relativa/canonica: {valor}",
    )
    return valor


def _hash(valor: Any) -> bool:
    return (
        isinstance(valor, str) and len(valor) == 64 and all(c in "0123456789abcdef" for c in valor)
    )


def _bbox(caja: Any, ancho: int, alto: int, *, xywh: bool = False) -> tuple:
    _exigir(isinstance(caja, (list, tuple)) and len(caja) == 4, "bbox requiere 4 numeros")
    _exigir(all(_numero(v) for v in caja), "bbox contiene valores no finitos o no numericos")
    x1, y1, a, b = caja
    x2, y2 = (x1 + a, y1 + b) if xywh else (a, b)
    _exigir(
        0 <= x1 < x2 <= ancho and 0 <= y1 < y2 <= alto,
        f"bbox fuera del cuadro o sin area: {caja} en {ancho}x{alto}",
    )
    return x1, y1, x2, y2


def iou(a: tuple | list, b: tuple | list) -> float:
    """Interseccion/union de xyxy continuas (sin +1); rechaza cajas invalidas."""
    for caja in (a, b):
        _exigir(isinstance(caja, (tuple, list)) and len(caja) == 4, "bbox invalida")
        _exigir(all(_numero(v) for v in caja), "bbox no finita")
        _exigir(0 <= caja[0] < caja[2] and 0 <= caja[1] < caja[3], "bbox sin area")
    # En pixeles normales no reescalar: evita redondeos adicionales en empates.
    # Las magnitudes extremas se escalan para no desbordar/subdesbordar areas.
    maximo = max(*a, *b)
    escala = maximo if maximo > 1e150 or maximo < 1e-150 else 1
    x1, y1, x2, y2 = (v / escala for v in a)
    u1, v1, u2, v2 = (v / escala for v in b)
    inter = max(0, min(x2, u2) - max(x1, u1)) * max(0, min(y2, v2) - max(y1, v1))
    union = (x2 - x1) * (y2 - y1) + (u2 - u1) * (v2 - v1) - inter
    _exigir(union > 0, "area no representable numericamente")
    return inter / union


def _coco(data: Any) -> list[dict]:
    _exigir(isinstance(data, dict), "COCO debe ser un objeto")
    _exigir(isinstance(data.get("info", {}), dict), "info COCO debe ser objeto")
    if "synthetic" in data.get("info", {}):
        _exigir(type(data["info"]["synthetic"]) is bool, "info.synthetic debe ser booleano")
    for campo in ("images", "annotations", "categories"):
        _exigir(isinstance(data.get(campo), list), f"COCO requiere lista {campo}")
    # El export COCO define su propia numeracion; la identidad comun es el nombre.
    categorias: dict = {}
    nombres: set = set()
    for cat in data["categories"]:
        _exigir(isinstance(cat, dict) and _id(cat.get("id")), "categoria sin id valido")
        nombre = cat.get("name")
        _exigir(isinstance(nombre, str) and bool(nombre), "categoria sin name")
        _exigir(cat["id"] not in categorias and nombre not in nombres, "categoria duplicada")
        categorias[cat["id"]] = nombre
        nombres.add(nombre)
    imagenes: dict = {}
    rutas: set = set()
    frames: set = set()
    for img in data["images"]:
        _exigir(isinstance(img, dict) and _id(img.get("id")), "imagen sin id valido")
        _exigir(img["id"] not in imagenes, "image id duplicado")
        ruta = _ruta(img.get("file_name"))
        _exigir(ruta not in rutas, "file_name duplicado")
        rutas.add(ruta)
        for campo in ("width", "height"):
            _exigir(type(img.get(campo)) is int and img[campo] > 0, f"{campo} invalido")
        frame = img.get("frame_id")
        if frame is not None:
            _exigir(isinstance(frame, str) and bool(frame), "frame_id COCO invalido")
            _exigir(frame not in frames, "frame_id COCO duplicado")
            frames.add(frame)
        sec = img.get("sequence_id")
        _exigir(sec is None or (isinstance(sec, str) and bool(sec)), "sequence_id invalido")
        sha = img.get("sha256")
        _exigir(sha is None or _hash(sha), "sha256 COCO invalido")
        imagenes[img["id"]] = {**img, "file_name": ruta, "gt": []}
    _exigir(bool(imagenes), "COCO no contiene imagenes")
    anotaciones: set = set()
    for ann in data["annotations"]:
        _exigir(isinstance(ann, dict) and _id(ann.get("id")), "anotacion sin id valido")
        _exigir(ann["id"] not in anotaciones, "annotation id duplicado")
        anotaciones.add(ann["id"])
        _exigir(_id(ann.get("image_id")) and ann["image_id"] in imagenes, "image_id inexistente")
        _exigir(
            _id(ann.get("category_id")) and ann["category_id"] in categorias,
            "category_id inexistente",
        )
        # Este evaluador greedy no implementa crowd/ignore de COCO AP.
        _exigir(
            ann.get("iscrowd", 0) == 0 and ann.get("ignore", 0) == 0, "crowd/ignore no soportado"
        )
        img = imagenes[ann["image_id"]]
        caja = _bbox(ann.get("bbox"), img["width"], img["height"], xywh=True)
        nombre = categorias[ann["category_id"]]
        if nombre in CLASES:
            img["gt"].append({"id": ann["id"], "class_name": nombre, "bbox": caja})
    for img in imagenes.values():
        img["gt"].sort(key=lambda a: (type(a["id"]).__name__, str(a["id"])))
    return sorted(imagenes.values(), key=lambda img: img["file_name"])


def _manifiesto(texto: str, imagenes: list[dict]) -> None:
    lector = csv.DictReader(io.StringIO(texto))
    campos = {"sequence_id", "frame_id", "t_capture_ms", "ruta", "ancho", "alto", "sha256"}
    cabecera = lector.fieldnames or []
    _exigir(campos <= set(cabecera), "manifiesto sin campos requeridos de #58")
    _exigir(len(cabecera) == len(set(cabecera)), "campos repetidos en manifiesto")
    por_ruta = {img["file_name"]: img for img in imagenes}
    rutas: set = set()
    ids: set = set()
    for fila in lector:
        _exigir(
            None not in fila and all(v is not None for v in fila.values()), "fila CSV incompleta"
        )
        ruta = _ruta(fila.get("ruta"))
        _exigir(ruta in por_ruta and ruta not in rutas, "ruta ajena/repetida en manifiesto")
        rutas.add(ruta)
        frame, sec = fila["frame_id"], fila["sequence_id"]
        _exigir(bool(frame) and bool(sec) and frame not in ids, "identidad de manifiesto invalida")
        ids.add(frame)
        _exigir(_hash(fila["sha256"]), "hash de manifiesto invalido")
        try:
            ancho, alto, tiempo = int(fila["ancho"]), int(fila["alto"]), float(fila["t_capture_ms"])
        except (ValueError, TypeError) as exc:
            raise EntradaError("dimensiones/tiempo de manifiesto invalidos") from exc
        _exigir(_numero(tiempo) and tiempo >= 0, "tiempo de manifiesto invalido")
        img = por_ruta[ruta]
        _exigir(
            (ancho, alto) == (img["width"], img["height"]), "dimensiones COCO/manifiesto distintas"
        )
        for clave, valor in (("frame_id", frame), ("sequence_id", sec), ("sha256", fila["sha256"])):
            _exigir(img.get(clave) in (None, valor), f"COCO/manifiesto discrepan: {clave}")
            img[clave] = valor
    _exigir(rutas == set(por_ruta), "COCO/manifiesto no contienen las mismas imagenes")


def _predicciones(texto: str) -> list[dict]:
    registros = []
    firma = None
    tiempo = None
    mezcla = False
    for linea, contenido in enumerate(texto.splitlines(), 1):
        if not contenido.strip():
            continue
        registro: dict = {"line": linea, "raw": {}, "errors": [], "event": None}
        registros.append(registro)
        try:
            raw = _json(contenido)
            _exigir(isinstance(raw, dict), "evento debe ser objeto")
            registro["raw"] = raw
            ev = validar_evento(raw)
            registro["event"] = ev
            _exigir(
                ev.frame_id.startswith(f"{ev.sequence_id}_"), "frame_id sin prefijo de secuencia"
            )
            if ev.image_path is not None:
                _ruta(ev.image_path)
            actual = (ev.run_id, ev.model_sha256, ev.config_sha256, ev.synthetic)
            if firma is not None and firma != actual:
                mezcla = True
            firma = actual
            _exigir(tiempo is None or ev.t_capture_ms > tiempo, "reloj no estrictamente creciente")
            tiempo = ev.t_capture_ms
            for det in ev.detections:
                if det.class_name in CLASES or det.class_id in CLASES.values():
                    _exigir(
                        CLASES.get(det.class_name) == det.class_id,
                        "class_name/class_id no coincide con descriptor: person=0, cat=15, dog=16",
                    )
        except (EntradaError, ContratoError) as exc:
            registro["errors"].append(str(exc))
    if mezcla:
        for registro in registros:
            registro["errors"].append(
                "mezcla de run/model/config/synthetic: archivo completo invalido"
            )
    return registros


def _asociar(registros: list[dict], imagenes: list[dict]) -> list[dict]:
    ids = {img["frame_id"]: img for img in imagenes if img.get("frame_id")}
    rutas = {img["file_name"]: img for img in imagenes}
    conocidos: dict[str, list[dict]] = defaultdict(list)
    repetidos = Counter(
        r["raw"].get("frame_id") for r in registros if isinstance(r["raw"].get("frame_id"), str)
    )
    desconocidos = []
    for r in registros:
        raw = r["raw"]
        frame, ruta = raw.get("frame_id"), raw.get("image_path")
        por_id = ids.get(frame) if isinstance(frame, str) else None
        por_ruta = rutas.get(ruta) if isinstance(ruta, str) else None
        candidatos = [img for img in (por_id, por_ruta) if img is not None]
        if not candidatos:
            r["errors"].append("cuadro desconocido o no identificable")
            desconocidos.append(r)
            continue
        if por_id is not None and ruta is not None and ruta != por_id["file_name"]:
            r["errors"].append("frame_id y image_path contradictorios")
        for img in {c["file_name"]: c for c in candidatos}.values():
            conocidos[img["file_name"]].append(r)
        if isinstance(frame, str) and repetidos[frame] > 1:
            r["errors"].append("frame_id duplicado")
    for img in imagenes:
        img["records"] = conocidos[img["file_name"]]
    return desconocidos


def _medidas(tp: int, fp: int, fn: int, ambito: str, avisos: list[str]) -> dict:
    def dividir(num: float, den: float, nombre: str) -> float:
        if den == 0:
            avisos.append(f"{ambito}.{nombre}: denominador cero; se devuelve 0")
            return 0.0
        return num / den

    precision = dividir(tp, tp + fp, "precision")
    recall = dividir(tp, tp + fn, "recall")
    f1 = dividir(2 * precision * recall, precision + recall, "f1")
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "support": tp + fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def _emparejar(img: dict, detecciones: tuple, umbral: float) -> dict:
    resultado = {}
    for clase in CLASES:
        reales = [a for a in img["gt"] if a["class_name"] == clase]
        libres = set(range(len(reales)))
        pred = [(i, d) for i, d in enumerate(detecciones) if d.class_name == clase]
        pred.sort(key=lambda par: (-par[1].confidence, par[0]))
        parejas = []
        for indice, det in pred:
            mejor = max(
                sorted(libres), key=lambda j: iou(det.bbox, reales[j]["bbox"]), default=None
            )
            valor = iou(det.bbox, reales[mejor]["bbox"]) if mejor is not None else 0.0
            acierto = mejor is not None and valor >= umbral
            if acierto:
                libres.remove(mejor)
            parejas.append(
                {
                    "prediction_index": indice,
                    "confidence": det.confidence,
                    "annotation_id": reales[mejor]["id"] if acierto else None,
                    "best_free_iou": valor,
                    "result": "tp" if acierto else "fp",
                }
            )
        tp = sum(p["result"] == "tp" for p in parejas)
        resultado[clase] = {
            "tp": tp,
            "fp": len(pred) - tp,
            "fn": len(libres),
            "matches": parejas,
            "unmatched_gt": [reales[j]["id"] for j in sorted(libres)],
        }
    return resultado


def _resumen_registro(r: dict) -> dict:
    raw = r["raw"]
    return {
        "line": r["line"],
        "frame_id": raw.get("frame_id") if isinstance(raw.get("frame_id"), str) else None,
        "image_path": raw.get("image_path") if isinstance(raw.get("image_path"), str) else None,
        "errors": r["errors"],
    }


def _corridas(registros: list[dict]) -> list[dict]:
    firmas = {
        (ev.run_id, ev.model_sha256, ev.config_sha256, ev.synthetic)
        for registro in registros
        if (ev := registro["event"]) is not None
    }
    campos = ("run_id", "model_sha256", "config_sha256", "synthetic")
    return [dict(zip(campos, firma, strict=True)) for firma in sorted(firmas)]


def evaluar(
    coco: dict, predicciones: str, umbral: float = 0.5, *, manifiesto: str | None = None
) -> dict:
    """Evalua todos los cuadros GT, incluidos negativos y fallidos; no altera entradas."""
    _exigir(_numero(umbral) and 0 < umbral <= 1, "IoU debe estar en (0, 1]")
    imagenes = _coco(coco)
    if manifiesto is not None:
        _manifiesto(manifiesto, imagenes)
    registros = _predicciones(predicciones)
    desconocidos = _asociar(registros, imagenes)
    cuadros = []
    for img in imagenes:
        records = img["records"]
        problemas = []
        ev = records[0]["event"] if len(records) == 1 else None
        if not records:
            estado = "missing"
        elif len(records) != 1:
            estado = "duplicate"
            problemas.append("varios registros para la misma imagen; se rechazan todos")
        else:
            problemas.extend(records[0]["errors"])
            if ev is not None:
                if ev.image_width is not None and (ev.image_width, ev.image_height) != (
                    img["width"],
                    img["height"],
                ):
                    problemas.append("dimensiones GT/pred distintas")
                if (
                    img.get("sha256")
                    and ev.image_sha256 is not None
                    and img["sha256"] != ev.image_sha256
                ):
                    problemas.append("hash GT/pred distinto")
                # Con IDs iguales, la secuencia debe coincidir. cli_* se asocia por ruta.
                if (
                    img.get("frame_id") == ev.frame_id
                    and img.get("sequence_id") is not None
                    and img["sequence_id"] != ev.sequence_id
                ):
                    problemas.append("sequence_id GT/pred distinto")
            estado = "invalid" if problemas else ev.status
        detalles = _emparejar(img, ev.detections if estado == "ok" else (), umbral)
        cuadros.append(
            {
                "image_id": img["id"],
                "file_name": img["file_name"],
                "gt_frame_id": img.get("frame_id"),
                "gt_sequence_id": img.get("sequence_id"),
                "prediction_frame_id": ev.frame_id if ev else None,
                "prediction_t_capture_ms": ev.t_capture_ms if ev else None,
                "image_sha256": img.get("sha256"),
                "association": "frame_id"
                if img.get("frame_id")
                and any(r["raw"].get("frame_id") == img["frame_id"] for r in records)
                else "path"
                if records
                else None,
                "status": estado,
                "issues": problemas,
                "error_msg": ev.error_msg if ev else None,
                "record_lines": [r["line"] for r in records],
                "ignored_detections": sum(d.class_name not in CLASES for d in ev.detections)
                if estado == "ok"
                else 0,
                "per_class": detalles,
            }
        )
    avisos: list[str] = []
    por_clase = {}
    for clase in CLASES:
        cuentas = [sum(c["per_class"][clase][k] for c in cuadros) for k in ("tp", "fp", "fn")]
        por_clase[clase] = _medidas(*cuentas, clase, avisos)
    cuentas_micro = [sum(c[k] for c in por_clase.values()) for k in ("tp", "fp", "fn")]
    micro = _medidas(*cuentas_micro, "micro", avisos)
    invalidos = [_resumen_registro(r) for r in registros if r["errors"]]
    estados = Counter(c["status"] for c in cuadros)
    if any(c["ignored_detections"] for c in cuadros):
        avisos.append("detecciones de clases fuera de person/cat/dog excluidas del alcance")
    fuera_alcance = len(coco["annotations"]) - micro["support"]
    if fuera_alcance:
        avisos.append(f"{fuera_alcance} anotaciones GT de otras clases excluidas del alcance")
    if len(cuadros) != estados["ok"]:
        avisos.append("cuadros fallidos/omitidos incluidos: todos sus objetos cuentan como FN")
    integridad = not (invalidos or desconocidos or estados["invalid"] or estados["duplicate"])
    sintetico = bool(coco.get("info", {}).get("synthetic", False)) or any(
        r["raw"].get("synthetic") is True for r in registros
    )
    return {
        "report_version": VERSION,
        "input_integrity_ok": integridad,
        "evidence": "SINTETICA" if sintetico else "NO_CERTIFICADA_COMO_CORRIDA_REAL",
        "parameters": {
            "iou": umbral,
            "classes": dict(CLASES),
            "contract_version": SCHEMA_VERSION,
            "matching": "confidence_desc_greedy_best_free_iou",
            "ties": "prediction input index; annotation type/id lexicographic",
            "failure_policy": "reject frame detections; all its GT become FN",
            "confidence_filter": None,
        },
        "frames": {
            "expected": len(cuadros),
            "evaluated": len(cuadros),
            "ok": estados["ok"],
            "negative": sum(not img["gt"] for img in imagenes),
            "missing": estados["missing"],
            "error": estados["error"],
            "stale": estados["stale"],
            "invalid": estados["invalid"],
            "duplicate": estados["duplicate"],
        },
        "gt_annotations": {
            "total": len(coco["annotations"]),
            "evaluated": micro["support"],
            "out_of_scope": fuera_alcance,
        },
        "per_class": por_clase,
        "micro": micro,
        "warnings": avisos,
        "invalid_records": invalidos,
        "unknown_predictions": [_resumen_registro(r) for r in desconocidos],
        "prediction_runs": _corridas(registros),
        "frame_details": cuadros,
    }


def _referencia(path: Path, contenido: bytes) -> dict:
    return {
        "file": path.name,
        "bytes": len(contenido),
        "sha256": hashlib.sha256(contenido).hexdigest(),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--gt", type=Path, required=True)
    parser.add_argument("--pred", type=Path, required=True)
    parser.add_argument("--iou", type=float, default=0.5)
    parser.add_argument("--salida", type=Path, required=True)
    parser.add_argument("--cuadros-esperados", type=int, help="exige ese numero de imagenes COCO")
    parser.add_argument(
        "--manifiesto", type=Path, help="CSV congelado de #58; cotejo exacto por ruta"
    )
    args = parser.parse_args(argv)
    try:
        archivos = {"gt": args.gt, "pred": args.pred}
        if args.manifiesto:
            archivos["manifest"] = args.manifiesto
        contenidos = {k: p.read_bytes() for k, p in archivos.items()}
        coco = _json(contenidos["gt"].decode("utf-8-sig"))
        informe = evaluar(
            coco,
            contenidos["pred"].decode("utf-8-sig"),
            args.iou,
            manifiesto=contenidos["manifest"].decode("utf-8-sig") if args.manifiesto else None,
        )
        if args.cuadros_esperados is not None:
            _exigir(
                args.cuadros_esperados > 0
                and informe["frames"]["expected"] == args.cuadros_esperados,
                "numero de cuadros COCO distinto de --cuadros-esperados",
            )
        informe["parameters"]["expected_frame_count"] = args.cuadros_esperados
        informe["inputs"] = {k: _referencia(p, contenidos[k]) for k, p in archivos.items()}
        fuentes = {
            "metricas": Path(__file__),
            "contrato": Path(__file__).with_name("contrato.py"),
            "event_schema": SCHEMAS_DIR / "evento_percepcion.schema.json",
        }
        informe["implementation"] = {k: _referencia(p, p.read_bytes()) for k, p in fuentes.items()}
        informe["implementation"]["python"] = sys.version.split()[0]
        salida = args.salida / "metricas.json"
        texto = (
            json.dumps(informe, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
            + "\n"
        )
        args.salida.mkdir(parents=True, exist_ok=True)
        with salida.open("x", encoding="utf-8", newline="\n") as archivo:
            archivo.write(texto)
    except (EntradaError, OSError, UnicodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(f"{informe['evidence']}: {informe['frames']['expected']} cuadros -> {salida}")
    print(json.dumps(informe["micro"], sort_keys=True))
    return 0 if informe["input_integrity_ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
