"""Verdad de referencia de P5-06 (#58): cuadros de P5-05, anotaciones COCO y estado esperado.

Solo lo usan el anotador (`scripts/anotador/`), el manifiesto, los conteos y las pruebas de
datos. El detector, la politica y el recorrido nunca importan este modulo ni leen
`datos/anotaciones*.json` o `datos/manifiesto*.csv` (`docs/datos.md`).

- Los cuadros salen de los `capturas.csv` de Bryan (P5-05), que no se modifican. Cada
  secuencia debe venir ordenada por `t_capture_ms`. Si el id del CSV ya es
  `<secuencia>_fNNNN` (S2, S3, S4 y S6 de P5-05b, con huecos) se conserva tal cual; si es un
  UUID (S1, S5 y ajuste) se numera `<secuencia>_f0001`, ... por posicion en ese orden. Es la
  misma regla que `p5.recorrer` (P5-14) y `normalizar_frame_id` de `p5.expectativas` (P5-15).
  El id original queda siempre en `frame_id_origen`.
- Ajuste usa `sequence_id` `AJ<n>` (de su `S<n>`) para que sus `frame_id` nunca choquen con
  evaluacion y cumplan el prefijo del contrato.
- COCO: `bbox` en `xywh` pixeles del cuadro original; `categories` con los indices COCO del
  detector (`modelo/descriptor.yaml`: person=0, cat=15, dog=16). Una imagen solo entra al COCO
  cuando un humano la reviso. **Vacio explicito = entrada en `images` sin ninguna anotacion**
  (la convencion COCO que leen `p5.expectativas` y `p5.metricas`); una imagen ausente es un
  cuadro sin anotar. `sin_objetos: true` es solo un campo extra informativo que pone el
  anotador; ningun calculo depende de el, y se verifica que sea coherente con las anotaciones.
- El estado esperado de la via sale de las cajas con `p5.contrato.zonas_ocupadas` y
  `p5.contrato.en_riesgo`; no se reimplementa la geometria.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import tempfile
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from p5.contrato import en_riesgo, zonas_ocupadas

RAIZ = Path(__file__).resolve().parents[2]  # Proyecto5/


@dataclass(frozen=True)
class Conjunto:
    nombre: str
    carpeta: str  # relativa a Proyecto5/, contiene capturas.csv y S<n>/
    coco: str  # relativa a Proyecto5/
    manifiesto: str  # relativa a Proyecto5/
    prefijo: str  # "S" conserva el sequence_id; "AJ" lo renombra S1 -> AJ1


CONJUNTOS = {
    "evaluacion": Conjunto(
        "evaluacion", "datos/evaluacion", "datos/anotaciones.json", "datos/manifiesto.csv", "S"
    ),
    "ajuste": Conjunto(
        "ajuste",
        "datos/ajuste",
        "datos/anotaciones_ajuste.json",
        "datos/manifiesto_ajuste.csv",
        "AJ",
    ),
}

# Valores de `estado_esperado_via`: los cinco de #58 mas `laterales` (izquierda y derecha en
# riesgo con el centro libre), el mismo criterio que `p5.expectativas` (P5-15).
ESTADOS = ("libre", "izq", "der", "laterales", "centro", "bloqueado")


class DatosError(ValueError):
    """Insumo de datos incoherente (CSV desordenado, caja invalida, COCO roto)."""


@dataclass(frozen=True)
class Cuadro:
    conjunto: str
    sequence_id: str
    sequence_id_origen: str
    frame_id: str
    frame_id_origen: str
    t_capture_ms: int
    ruta: str  # relativa a Proyecto5/, igual al file_name del COCO
    path_capturas: str  # columna `path` del capturas.csv (relativa a la carpeta del conjunto)
    ancho: int
    alto: int
    sha256: str
    session_id: str
    scene_label: str
    outside_risk: int

    @property
    def id_imagen(self) -> int:
        return id_imagen(self.frame_id)


def id_imagen(frame_id: str) -> int:
    """Id entero estable del COCO: `S5_f0012` -> 5012, `AJ1_f0003` -> 1003."""
    m = re.fullmatch(r"[A-Z]+(\d+)_f(\d{4})", frame_id)
    if not m:
        raise DatosError(f"frame_id sin el formato <secuencia>_fNNNN: {frame_id}")
    return int(m.group(1)) * 1000 + int(m.group(2))


def _sequence_id(conjunto: Conjunto, origen: str) -> str:
    if conjunto.prefijo == "S":
        return origen
    m = re.fullmatch(r"S(\d+)", origen)
    if not m:
        raise DatosError(f"sequence_id de {conjunto.nombre} inesperado: {origen}")
    return f"{conjunto.prefijo}{m.group(1)}"


def _frame_id(seq: str, origen: str, crudo: str) -> str | None:
    """`frame_id` conservado si el CSV ya trae `<origen>_fNNNN` (None si es un UUID)."""
    m = re.fullmatch(rf"{re.escape(origen)}_f(\d{{4}})", crudo)
    return f"{seq}_f{m.group(1)}" if m else None


def leer_capturas(conjunto: str, raiz: Path = RAIZ) -> list[Cuadro]:
    """Cuadros del `capturas.csv` del conjunto con su `frame_id` canonico.

    Regla acordada con P5-14 y P5-15 (instruccion del PM: conservar el `frame_id` de origen):
    si el id del CSV ya es `<secuencia>_fNNNN` se conserva, con sus huecos; si es un UUID se
    numera por posicion dentro de la secuencia, en orden de `t_capture_ms`. Una secuencia no
    puede mezclar ambos tipos, y los numeros conservados deben crecer con el tiempo.

    Exige que cada secuencia ya venga ordenada por `t_capture_ms` estrictamente creciente:
    `p5.recorrer` y `p5.expectativas` numeran en el orden de las filas, asi que un CSV
    desordenado daria `frame_id` distintos entre equipos. En ese caso se detiene.
    """
    conj = CONJUNTOS[conjunto]
    ruta_csv = raiz / conj.carpeta / "capturas.csv"
    with ruta_csv.open(encoding="utf-8", newline="") as f:
        filas = list(csv.DictReader(f))
    cuadros: list[Cuadro] = []
    contadores: dict[str, int] = {}
    previo: dict[str, int] = {}
    tipo: dict[str, bool] = {}  # secuencia -> trae ids `_fNNNN` conservados
    vistos: set[str] = set()
    previo_id: dict[str, str] = {}
    for n, fila in enumerate(filas, 2):
        origen = fila["sequence_id"].strip()
        t = int(fila["t_capture_ms"])
        if origen in previo and t <= previo[origen]:
            raise DatosError(
                f"{ruta_csv}:{n}: {origen} no viene ordenada por t_capture_ms "
                f"({t} <= {previo[origen]}); avisar a P5-05 antes de numerar"
            )
        previo[origen] = t
        seq = _sequence_id(conj, origen)
        contadores[seq] = contadores.get(seq, 0) + 1
        crudo = fila["frame_id"].strip()
        conservado = _frame_id(seq, origen, crudo)
        if tipo.setdefault(seq, conservado is not None) != (conservado is not None):
            raise DatosError(
                f"{ruta_csv}:{n}: {origen} mezcla ids `{origen}_fNNNN` y UUID ({crudo}); "
                "avisar a P5-05 antes de numerar"
            )
        frame_id = conservado or f"{seq}_f{contadores[seq]:04d}"
        if frame_id in vistos:
            raise DatosError(f"{ruta_csv}:{n}: frame_id repetido {frame_id}")
        if conservado and seq in previo_id and id_imagen(frame_id) <= id_imagen(previo_id[seq]):
            raise DatosError(
                f"{ruta_csv}:{n}: {crudo} no sigue el orden temporal de {previo_id[seq]}"
            )
        vistos.add(frame_id)
        previo_id[seq] = frame_id
        path = fila["path"].strip().replace("\\", "/")
        cuadros.append(
            Cuadro(
                conjunto=conjunto,
                sequence_id=seq,
                sequence_id_origen=origen,
                frame_id=frame_id,
                frame_id_origen=crudo,
                t_capture_ms=t,
                ruta=f"{conj.carpeta}/{path}",
                path_capturas=path,
                ancho=int(fila["image_width"]),
                alto=int(fila["image_height"]),
                sha256=fila["sha256"].strip().lower(),
                session_id=fila["session_id"].strip(),
                scene_label=fila["scene_label"].strip(),
                outside_risk=int(fila["outside_risk"]),
            )
        )
    return cuadros


def sha256_archivo(ruta: Path) -> str:
    h = hashlib.sha256()
    with ruta.open("rb") as f:
        for bloque in iter(lambda: f.read(1 << 16), b""):
            h.update(bloque)
    return h.hexdigest()


# --- Categorias -------------------------------------------------------------------------


def categorias(raiz: Path = RAIZ) -> list[dict[str, Any]]:
    """`categories` del COCO con los indices del detector (`modelo/descriptor.yaml`)."""
    descriptor = yaml.safe_load((raiz / "modelo" / "descriptor.yaml").read_text(encoding="utf-8"))
    cats = [
        {"id": int(c["class_id"]), "name": str(c["class_name"]), "supercategory": "obstaculo"}
        for c in descriptor["clases_obstaculo"]
    ]
    return sorted(cats, key=lambda c: c["id"])


# --- COCO -------------------------------------------------------------------------------


def coco_vacio(conjunto: str, raiz: Path = RAIZ) -> dict[str, Any]:
    return {
        "info": {
            "description": f"Verdad de referencia P5-06 (#58), conjunto {conjunto}",
            "version": "1",
            "contributor": "Emilio (A2), anotacion manual; ver docs/datos.md",
            "bbox": "xywh en pixeles del cuadro original, origen arriba-izquierda",
            "vacio_explicito": "imagen en images sin anotaciones (sin_objetos es informativo)",
        },
        "licenses": [],
        "categories": categorias(raiz),
        "images": [],
        "annotations": [],
    }


def cargar_coco(ruta: Path, conjunto: str, raiz: Path = RAIZ) -> dict[str, Any]:
    if not ruta.is_file():
        return coco_vacio(conjunto, raiz)
    coco = json.loads(ruta.read_text(encoding="utf-8"))
    for campo in ("images", "annotations", "categories"):
        if campo not in coco:
            raise DatosError(f"{ruta}: falta {campo}")
    return coco


def guardar_coco(ruta: Path, coco: dict[str, Any]) -> None:
    """Escritura atomica y ordenada (diffs estables en Git)."""
    coco["images"].sort(key=lambda i: i["id"])
    coco["annotations"].sort(key=lambda a: a["id"])
    texto = json.dumps(coco, indent=1, ensure_ascii=False) + "\n"
    ruta.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=ruta.parent, prefix=".anotaciones-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(texto)
        os.replace(tmp, ruta)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def _imagen(cuadro: Cuadro, sin_objetos: bool) -> dict[str, Any]:
    return {
        "id": cuadro.id_imagen,
        "file_name": cuadro.ruta,
        "width": cuadro.ancho,
        "height": cuadro.alto,
        "sequence_id": cuadro.sequence_id,
        "frame_id": cuadro.frame_id,
        "frame_id_origen": cuadro.frame_id_origen,
        "t_capture_ms": cuadro.t_capture_ms,
        "sha256": cuadro.sha256,
        "sin_objetos": sin_objetos,
    }


def validar_caja(bbox: Iterable[float], ancho: int, alto: int) -> tuple[float, float, float, float]:
    """`xywh` finita, con area positiva y dentro del cuadro; redondeada a 0.1 px."""
    x, y, w, h = (round(float(v), 1) for v in bbox)
    if not (w > 0 and h > 0 and x >= 0 and y >= 0 and x + w <= ancho and y + h <= alto):
        raise DatosError(f"caja {[x, y, w, h]} fuera del cuadro {ancho}x{alto} o sin area")
    return x, y, w, h


def registrar_cuadro(
    coco: dict[str, Any], cuadro: Cuadro, cajas: list[dict[str, Any]], sin_objetos: bool
) -> None:
    """Reemplaza la revision humana de un cuadro: `cajas` = [{"clase": str, "bbox": xywh}]."""
    if sin_objetos and cajas:
        raise DatosError(f"{cuadro.frame_id}: 'sin objetos' con cajas")
    if not sin_objetos and not cajas:
        raise DatosError(f"{cuadro.frame_id}: sin cajas; marque 'sin objetos' explicitamente")
    if len(cajas) > 99:
        raise DatosError(f"{cuadro.frame_id}: mas de 99 cajas")
    por_nombre = {c["name"]: c["id"] for c in coco["categories"]}
    nuevas = []
    for k, caja in enumerate(cajas, 1):
        if caja["clase"] not in por_nombre:
            raise DatosError(f"{cuadro.frame_id}: clase {caja['clase']!r} no evaluada")
        x, y, w, h = validar_caja(caja["bbox"], cuadro.ancho, cuadro.alto)
        nuevas.append(
            {
                "id": cuadro.id_imagen * 100 + k,
                "image_id": cuadro.id_imagen,
                "category_id": por_nombre[caja["clase"]],
                "bbox": [x, y, w, h],
                "area": round(w * h, 2),
                "iscrowd": 0,
            }
        )
    quitar_cuadro(coco, cuadro.ruta)
    coco["images"].append(_imagen(cuadro, sin_objetos))
    coco["annotations"].extend(nuevas)


def quitar_cuadro(coco: dict[str, Any], file_name: str) -> None:
    ids = {i["id"] for i in coco["images"] if i["file_name"] == file_name}
    coco["images"] = [i for i in coco["images"] if i["file_name"] != file_name]
    coco["annotations"] = [a for a in coco["annotations"] if a["image_id"] not in ids]


def sincronizar(coco: dict[str, Any], cuadros: list[Cuadro]) -> list[str]:
    """Rehace los metadatos de cada imagen anotada desde el CSV (por `file_name`), conservando
    sus cajas. Devuelve avisos: imagenes del COCO que ya no estan en el CSV (no se borran)."""
    por_ruta = {c.ruta: c for c in cuadros}
    avisos = []
    for img in list(coco["images"]):
        cuadro = por_ruta.get(img["file_name"])
        if cuadro is None:
            avisos.append(f"{img['file_name']}: anotada pero ya no esta en capturas.csv")
            continue
        if img["id"] != cuadro.id_imagen:
            avisos.append(f"{img['file_name']}: id {img['id']} -> {cuadro.id_imagen}")
            for k, ann in enumerate(
                sorted(
                    (a for a in coco["annotations"] if a["image_id"] == img["id"]),
                    key=lambda a: a["id"],
                ),
                1,
            ):
                ann["image_id"] = cuadro.id_imagen
                ann["id"] = cuadro.id_imagen * 100 + k
        sin_objetos = bool(img.get("sin_objetos", False))
        img.clear()
        img.update(_imagen(cuadro, sin_objetos))
    return avisos


def cajas_por_ruta(coco: dict[str, Any]) -> dict[str, list[tuple[str, tuple[float, ...]]]]:
    """`file_name` -> [(clase, bbox xyxy)] de las imagenes revisadas (vacias incluidas)."""
    nombres = {c["id"]: c["name"] for c in coco["categories"]}
    rutas = {i["id"]: i["file_name"] for i in coco["images"]}
    res: dict[str, list[tuple[str, tuple[float, ...]]]] = {r: [] for r in rutas.values()}
    for a in coco["annotations"]:
        x, y, w, h = a["bbox"]
        res[rutas[a["image_id"]]].append((nombres[a["category_id"]], (x, y, x + w, y + h)))
    return res


# --- Estado esperado ---------------------------------------------------------------------


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


@dataclass(frozen=True)
class Estado:
    estado: str
    zonas_en_riesgo: tuple[str, ...]
    n_cajas: int  # todas las cajas anotadas del cuadro
    n_obstaculos: int  # cajas de clases_obstaculo
    n_en_riesgo: int  # obstaculos con y2 >= H/2


def estado_esperado(
    cajas: list[tuple[str, tuple[float, ...]]], ancho: int, alto: int, clases: Iterable[str]
) -> Estado:
    clases = frozenset(clases)
    zonas: set[str] = set()
    obst = riesgo = 0
    for clase, caja in cajas:
        if clase not in clases:
            continue
        obst += 1
        if en_riesgo(caja, alto):
            riesgo += 1
            zonas |= zonas_ocupadas(caja, ancho)
    orden = tuple(z for z in ("izquierda", "centro", "derecha") if z in zonas)
    return Estado(estado_via(zonas), orden, len(cajas), obst, riesgo)


# --- Manifiesto (#58) -----------------------------------------------------------------------

# Columnas exigidas por #58 y, despues, columnas extra de trazabilidad (csv.DictReader las
# ignora si no las pide; `p5.metricas` exige solo las siete primeras).
COLUMNAS_MANIFIESTO = [
    "sequence_id",
    "frame_id",
    "t_capture_ms",
    "ruta",
    "ancho",
    "alto",
    "sha256",
    "estado_esperado_via",
    "frame_id_origen",
    "sequence_id_origen",
    "session_id",
    "n_cajas",
    "n_obstaculos",
    "n_en_riesgo",
    "zonas_en_riesgo",
    "scene_label_p505",
    "outside_risk_p505",
]

# Intencion de cada secuencia segun #57/#58 (S6: libre -> centro -> libre por scene_label).
# Solo sirve para el reporte de discrepancias: el estado del manifiesto sale de las cajas.
INTENCION = {"S1": "libre", "S2": "centro", "S3": "izq", "S4": "der", "S5": "bloqueado"}


def intencion(c: Cuadro) -> str:
    if c.conjunto == "ajuste" or c.scene_label == "despejado" or c.outside_risk == 1:
        return "libre"
    if c.sequence_id == "S6":
        return "centro"
    return INTENCION.get(c.sequence_id, "?")


@dataclass
class ResultadoManifiesto:
    filas: list[dict[str, Any]]
    errores: list[str]  # integridad: impiden escribir el manifiesto
    discrepancias: list[str]  # semanticas: se revisan con quien anota, no se corrigen solas


def construir_manifiesto(
    conjunto: str,
    coco: dict[str, Any],
    clases: Iterable[str],
    raiz: Path = RAIZ,
    secuencias: set[str] | None = None,
) -> ResultadoManifiesto:
    """Une `capturas.csv` y el COCO. Recalcula SHA-256 y dimensiones desde los bytes."""
    from PIL import Image

    clases = frozenset(clases)
    cuadros = leer_capturas(conjunto, raiz)
    if secuencias:
        desconocidas = secuencias - {c.sequence_id for c in cuadros}
        if desconocidas:
            raise DatosError(f"secuencias que no estan en {conjunto}: {sorted(desconocidas)}")
        cuadros = [c for c in cuadros if c.sequence_id in secuencias]
    imgs = {i["file_name"]: i for i in coco["images"]}
    n_ann: dict[int, int] = {}
    for a in coco["annotations"]:
        n_ann[a["image_id"]] = n_ann.get(a["image_id"], 0) + 1
    cajas = cajas_por_ruta(coco)
    filas: list[dict[str, Any]] = []
    errores: list[str] = []
    discrepancias: list[str] = []
    for c in cuadros:
        ruta = raiz / c.ruta
        if not ruta.is_file():
            errores.append(f"{c.frame_id}: falta {c.ruta}")
            continue
        if sha256_archivo(ruta) != c.sha256:
            errores.append(f"{c.frame_id}: SHA-256 de {c.ruta} distinto del capturas.csv")
        with Image.open(ruta) as im:
            if im.size != (c.ancho, c.alto):
                errores.append(f"{c.frame_id}: JPEG {im.size} distinto del CSV {c.ancho}x{c.alto}")
        img = imgs.get(c.ruta)
        if img is None:
            errores.append(f"{c.frame_id}: {c.ruta} sin anotar (no esta en el COCO)")
            continue
        if (img["width"], img["height"]) != (c.ancho, c.alto):
            errores.append(f"{c.frame_id}: dimensiones del COCO distintas del CSV")
        for clave, valor in (
            ("id", c.id_imagen),
            ("frame_id", c.frame_id),
            ("sequence_id", c.sequence_id),
            ("sha256", c.sha256),
        ):
            if img.get(clave, valor) != valor:
                errores.append(f"{c.frame_id}: COCO {clave}={img.get(clave)!r} != {valor!r}")
        n = n_ann.get(img["id"], 0)
        if img.get("sin_objetos") and n:
            errores.append(f"{c.frame_id}: sin_objetos=true pero tiene {n} anotaciones")
        propias = cajas.get(c.ruta, [])
        for clase, (x1, y1, x2, y2) in propias:
            if not (0 <= x1 < x2 <= c.ancho and 0 <= y1 < y2 <= c.alto):
                errores.append(f"{c.frame_id}: caja {clase} {[x1, y1, x2, y2]} fuera del cuadro")
        est = estado_esperado(propias, c.ancho, c.alto, clases)
        esperado = intencion(c)
        if est.estado != esperado:
            discrepancias.append(
                f"{c.frame_id}: estado {est.estado} ({'+'.join(est.zonas_en_riesgo) or '-'}) "
                f"!= intencion {esperado} (scene_label={c.scene_label}, "
                f"outside_risk={c.outside_risk})"
            )
        if c.scene_label == "despejado" and est.n_obstaculos:
            discrepancias.append(
                f"{c.frame_id}: P5-05 lo marca despejado pero tiene {est.n_obstaculos} "
                "obstaculo(s) anotado(s): pasa a positivo"
            )
        if c.outside_risk == 1 and not est.n_obstaculos:
            discrepancias.append(f"{c.frame_id}: outside_risk=1 sin caja anotada lejos")
        filas.append(
            {
                "sequence_id": c.sequence_id,
                "frame_id": c.frame_id,
                "t_capture_ms": c.t_capture_ms,
                "ruta": c.ruta,
                "ancho": c.ancho,
                "alto": c.alto,
                "sha256": c.sha256,
                "estado_esperado_via": est.estado,
                "frame_id_origen": c.frame_id_origen,
                "sequence_id_origen": c.sequence_id_origen,
                "session_id": c.session_id,
                "n_cajas": est.n_cajas,
                "n_obstaculos": est.n_obstaculos,
                "n_en_riesgo": est.n_en_riesgo,
                "zonas_en_riesgo": "+".join(est.zonas_en_riesgo),
                "scene_label_p505": c.scene_label,
                "outside_risk_p505": c.outside_risk,
            }
        )
    incluidas = {c.ruta for c in cuadros}
    for nombre in sorted(set(imgs) - incluidas):
        errores.append(f"{nombre}: esta en el COCO pero no en el manifiesto")
    return ResultadoManifiesto(filas, errores, discrepancias)


def escribir_csv(ruta: Path, filas: list[dict[str, Any]], columnas: list[str]) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("w", encoding="utf-8", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=columnas, lineterminator="\n")
        escritor.writeheader()
        escritor.writerows(filas)


# --- Congelado (HASHES.sha256) ---------------------------------------------------------------

ARCHIVO_HASHES = "datos/HASHES.sha256"


def archivos_congelados(raiz: Path = RAIZ) -> list[str]:
    """JPEG y capturas.csv de evaluacion y ajuste, manifiestos y COCO (rutas de Proyecto5/)."""
    rutas = set()
    for conj in CONJUNTOS.values():
        carpeta = raiz / conj.carpeta
        rutas |= {p.relative_to(raiz).as_posix() for p in carpeta.glob("S*/*.jpg")}
        rutas.add(f"{conj.carpeta}/capturas.csv")
        for extra in (conj.coco, conj.manifiesto):
            if (raiz / extra).is_file():
                rutas.add(extra)
    return sorted(rutas)


def escribir_hashes(raiz: Path = RAIZ) -> Path:
    """Formato `sha256sum` (dos espacios), verificable con `sha256sum -c` desde Proyecto5/."""
    lineas = [f"{sha256_archivo(raiz / r)}  {r}\n" for r in archivos_congelados(raiz)]
    destino = raiz / ARCHIVO_HASHES
    with destino.open("w", encoding="utf-8", newline="\n") as f:
        f.writelines(lineas)
    return destino


def verificar_hashes(raiz: Path = RAIZ) -> list[str]:
    """Problemas: hash distinto, archivo faltante o archivo de datos sin registrar."""
    problemas = []
    registrados = set()
    texto = (raiz / ARCHIVO_HASHES).read_text(encoding="utf-8")
    for n, linea in enumerate(texto.splitlines(), 1):
        m = re.fullmatch(r"([0-9a-f]{64}) [ *](.+)", linea)
        if not m:
            problemas.append(f"linea {n} con formato invalido")
            continue
        esperado, ruta = m.groups()
        registrados.add(ruta)
        if not (raiz / ruta).is_file():
            problemas.append(f"{ruta}: falta")
        elif sha256_archivo(raiz / ruta) != esperado:
            problemas.append(f"{ruta}: SHA-256 distinto")
    for ruta in sorted(set(archivos_congelados(raiz)) - registrados):
        problemas.append(f"{ruta}: no esta en {ARCHIVO_HASHES}")
    return problemas
