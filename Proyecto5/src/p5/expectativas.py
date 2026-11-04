"""Acciones permitidas por cuadro desde la verdad de referencia (P5-15, `docs/expectativas.md`).

Lee el COCO de anotaciones y el manifiesto de capturas de P5-05 (`capturas.csv`), ubica cada
caja anotada con `p5.contrato.zonas_ocupadas` y `p5.contrato.en_riesgo` y escribe, por cuadro,
el estado de la via y las acciones seguras para esa geometria. No ejecuta el detector ni la
politica: la expectativa sale de las anotaciones, no de lo que ya hace el programa.

    python -m p5.expectativas --coco datos/anotaciones.json \\
        --manifiesto datos/evaluacion/capturas.csv --config config/politica.yaml \\
        --salida casos/expectativas [--secuencias S1 S5]

Escribe un `cuadros_<secuencia>.csv` por secuencia (el runner de P5-13 compara todas las filas
del CSV de un caso) y `cuadros_origen.json` con los hashes de las entradas.

Sale con 1 si falta la anotacion de un cuadro, si una caja no cabe en su cuadro o si el estado
calculado contradice `scene_label`/`outside_risk` del manifiesto.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from p5.contrato import en_riesgo, zonas_ocupadas
from p5.politica import cargar_config

# Acciones seguras por estado de la via. STOP nunca es inseguro; los casos C1, C3 y C4 exigen
# ademas movimiento (requisito `movimiento_minimo`), para que detenerse siempre no apruebe.
ACCIONES_POR_ESTADO = {
    "libre": ("FORWARD", "STEER_LEFT", "STEER_RIGHT", "STOP"),
    "izq": ("FORWARD", "STEER_RIGHT", "STOP"),
    "der": ("FORWARD", "STEER_LEFT", "STOP"),
    "laterales": ("FORWARD", "STOP"),
    "centro": ("STOP",),
    "bloqueado": ("STOP",),
}
COLUMNAS = [
    "sequence_id",
    "frame_id",
    "frame_id_origen",
    "t_capture_ms",
    "estado_via",
    "zonas_en_riesgo",
    "acciones_permitidas",
    "estado_manifiesto",
    "coincide",
    "justificacion",
]


@dataclass(frozen=True)
class Cuadro:
    sequence_id: str
    frame_id: str
    frame_id_origen: str
    t_capture_ms: float
    ruta: str
    ancho: int
    alto: int
    estado_manifiesto: str  # despejado, obstaculo u obstaculo_fuera_riesgo


def sha256(ruta: Path) -> str:
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


def _ms(valor: float) -> str:
    """El tiempo tal como viene en el manifiesto: entero sin notacion cientifica."""
    return str(int(valor)) if valor.is_integer() else repr(valor)


def _norm(ruta: str) -> str:
    return PurePosixPath(ruta.replace("\\", "/")).as_posix().lstrip("./")


def normalizar_frame_id(sequence_id: str, crudo: str, contadores: dict[str, int]) -> str:
    """El mismo `frame_id` que asigna `p5.recorrer` (P5-14): `S1_f0001` se respeta y cualquier
    otro id (los UUID de #79) pasa a `<secuencia>_fNNNN` en el orden del manifiesto."""
    prefijo = f"{sequence_id}_f"
    if crudo.startswith(prefijo) and crudo[len(prefijo) :].isdigit():
        return crudo
    contadores[sequence_id] = contadores.get(sequence_id, 0) + 1
    return f"{prefijo}{contadores[sequence_id]:04d}"


def _estado_manifiesto(fila: dict) -> str:
    etiqueta = fila["scene_label"].strip()
    if etiqueta == "obstaculo" and fila.get("outside_risk", "0").strip() == "1":
        return "obstaculo_fuera_riesgo"
    return etiqueta


def leer_manifiesto(ruta: Path) -> list[Cuadro]:
    contadores: dict[str, int] = {}
    with ruta.open(encoding="utf-8", newline="") as f:
        return [
            Cuadro(
                sequence_id=fila["sequence_id"],
                frame_id=normalizar_frame_id(
                    fila["sequence_id"], fila["frame_id"].strip(), contadores
                ),
                frame_id_origen=fila["frame_id"].strip(),
                t_capture_ms=float(fila["t_capture_ms"]),
                ruta=fila["path"],
                ancho=int(fila["image_width"]),
                alto=int(fila["image_height"]),
                estado_manifiesto=_estado_manifiesto(fila),
            )
            for fila in csv.DictReader(f)
        ]


def coincide_con_manifiesto(estado_manifiesto: str, estado: str, hay_obstaculo: bool) -> bool:
    """`despejado`: via libre. `obstaculo_fuera_riesgo`: via libre con un obstaculo anotado
    lejos. `obstaculo`: algun obstaculo en riesgo."""
    if estado_manifiesto == "despejado":
        return estado == "libre"
    if estado_manifiesto == "obstaculo_fuera_riesgo":
        return estado == "libre" and hay_obstaculo
    if estado_manifiesto == "obstaculo":
        return estado != "libre"
    return False


def anotaciones_por_ruta(coco: dict) -> dict[str, tuple[dict, list[tuple[str, tuple]]]]:
    """`file_name` normalizado -> (imagen, [(clase, bbox xyxy)]). Una imagen sin anotaciones
    es un cuadro anotado como vacio, no un cuadro sin anotar."""
    categorias = {c["id"]: c["name"] for c in coco["categories"]}
    resultado = {_norm(img["file_name"]): (img, []) for img in coco["images"]}
    por_id = {img["id"]: _norm(img["file_name"]) for img in coco["images"]}
    for ann in coco["annotations"]:
        x, y, w, h = ann["bbox"]
        caja = (float(x), float(y), float(x + w), float(y + h))
        resultado[por_id[ann["image_id"]]][1].append((categorias[ann["category_id"]], caja))
    return resultado


def _buscar(cuadro: Cuadro, anotadas: dict) -> tuple[dict, list] | None:
    ruta = _norm(cuadro.ruta)
    if ruta in anotadas:
        return anotadas[ruta]
    base = PurePosixPath(ruta).name
    candidatas = [k for k in anotadas if PurePosixPath(k).name == base]
    return anotadas[candidatas[0]] if len(candidatas) == 1 else None


def estado_via(zonas: Iterable[str]) -> str:
    z = set(zonas)
    if "centro" in z:
        return "bloqueado" if {"izquierda", "derecha"} <= z else "centro"
    if {"izquierda", "derecha"} <= z:
        return "laterales"
    if "izquierda" in z:
        return "izq"
    if "derecha" in z:
        return "der"
    return "libre"


def expectativas(
    cuadros: list[Cuadro], anotadas: dict, clases: frozenset[str]
) -> tuple[list[dict], list[str]]:
    filas, errores = [], []
    for c in cuadros:
        encontrada = _buscar(c, anotadas)
        if encontrada is None:
            errores.append(f"{c.frame_id}: {c.ruta} no aparece en el COCO (sin anotar)")
            continue
        img, cajas = encontrada
        if (img["width"], img["height"]) != (c.ancho, c.alto):
            errores.append(
                f"{c.frame_id}: dimensiones del COCO {img['width']}x{img['height']} "
                f"distintas del manifiesto {c.ancho}x{c.alto}"
            )
        zonas: set[str] = set()
        motivos = []
        hay_obstaculo = False
        for clase, caja in cajas:
            x1, y1, x2, y2 = caja
            if not (0 <= x1 < x2 <= c.ancho and 0 <= y1 < y2 <= c.alto):
                errores.append(f"{c.frame_id}: caja {clase} {list(caja)} fuera del cuadro")
                continue
            caja_txt = f"{clase} [{x1:g},{y1:g},{x2:g},{y2:g}]"
            if clase not in clases:
                motivos.append(f"{caja_txt} ignorada: no es clase de obstaculo")
                continue
            hay_obstaculo = True
            toca = sorted(zonas_ocupadas(caja, c.ancho))
            if en_riesgo(caja, c.alto):
                zonas.update(toca)
                motivos.append(
                    f"{caja_txt} toca {'+'.join(toca)} en riesgo (y2={y2:g} >= {c.alto / 2:g})"
                )
            else:
                motivos.append(
                    f"{caja_txt} toca {'+'.join(toca)} lejos (y2={y2:g} < {c.alto / 2:g})"
                )
        estado = estado_via(zonas)
        coincide = coincide_con_manifiesto(c.estado_manifiesto, estado, hay_obstaculo)
        if not coincide:
            errores.append(
                f"{c.frame_id}: estado calculado {estado} contradice el manifiesto "
                f"({c.estado_manifiesto})"
            )
        filas.append(
            {
                "sequence_id": c.sequence_id,
                "frame_id": c.frame_id,
                "frame_id_origen": c.frame_id_origen,
                "t_capture_ms": _ms(c.t_capture_ms),
                "estado_via": estado,
                "zonas_en_riesgo": "+".join(
                    z for z in ("izquierda", "centro", "derecha") if z in zonas
                ),
                "acciones_permitidas": "|".join(ACCIONES_POR_ESTADO[estado]),
                "estado_manifiesto": c.estado_manifiesto,
                "coincide": "si" if coincide else "no",
                "justificacion": "; ".join(motivos) or "sin objetos anotados",
            }
        )
    return filas, errores


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--coco", type=Path, required=True)
    ap.add_argument("--manifiesto", type=Path, required=True, help="capturas.csv de P5-05")
    ap.add_argument("--config", type=Path, required=True, help="politica.yaml (clases_obstaculo)")
    ap.add_argument("--salida", type=Path, required=True, help="carpeta de los cuadros_<sec>.csv")
    ap.add_argument(
        "--secuencias", nargs="+", help="solo estas secuencias (las anotaciones llegan por partes)"
    )
    args = ap.parse_args(argv)

    clases = cargar_config(args.config).clases_obstaculo
    coco = json.loads(args.coco.read_text(encoding="utf-8"))
    cuadros = leer_manifiesto(args.manifiesto)
    secuencias = list(dict.fromkeys(c.sequence_id for c in cuadros))
    errores = []
    if args.secuencias:
        errores = [
            f"secuencia {s} no esta en el manifiesto"
            for s in args.secuencias
            if s not in secuencias
        ]
        secuencias = [s for s in secuencias if s in args.secuencias]
    cuadros = [c for c in cuadros if c.sequence_id in secuencias]
    filas, errores_cuadros = expectativas(cuadros, anotaciones_por_ruta(coco), clases)
    errores += errores_cuadros

    args.salida.mkdir(parents=True, exist_ok=True)
    por_secuencia = {}
    for secuencia in secuencias:
        propias = [f for f in filas if f["sequence_id"] == secuencia]
        ruta = args.salida / f"cuadros_{secuencia}.csv"
        with ruta.open("w", encoding="utf-8", newline="") as f:
            escritor = csv.DictWriter(f, fieldnames=COLUMNAS, lineterminator="\n")
            escritor.writeheader()
            escritor.writerows(propias)
        por_estado = {e: sum(f["estado_via"] == e for f in propias) for e in ACCIONES_POR_ESTADO}
        por_secuencia[secuencia] = {
            "cuadros": len(propias),
            "por_estado": {e: n for e, n in por_estado.items() if n},
        }
    origen = {
        "coco_sha256": sha256(args.coco),
        "manifiesto_sha256": sha256(args.manifiesto),
        "config_sha256": sha256(args.config),
        "secuencias": por_secuencia,
        "errores": errores,
    }
    (args.salida / "cuadros_origen.json").write_text(
        json.dumps(origen, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    for secuencia, resumen in por_secuencia.items():
        print(f"{secuencia}: {resumen['cuadros']} cuadros, {resumen['por_estado']}")
    for e in errores:
        print(f"ERROR {e}", file=sys.stderr)
    return 1 if errores else 0


if __name__ == "__main__":
    sys.exit(main())
