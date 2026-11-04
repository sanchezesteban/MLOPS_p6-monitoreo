"""Imagenes de revision de la verdad de referencia (P5-06): cajas, tercios y linea de riesgo.

    cd Proyecto5
    python scripts/revisar_anotaciones.py --salida <carpeta nueva fuera de datos/>
    python scripts/revisar_anotaciones.py --hojas docs/revision --secuencias S1 S5 AJ1

`--salida` escribe una copia PNG por cuadro con lo anotado dibujado; `--hojas` escribe una hoja
de contacto JPEG por secuencia (lo que va a `docs/revision/`). Las guias y cajas se dibujan
sobre una copia en memoria: los JPEG de `datos/` se abren en modo lectura y nunca se escriben,
y el script se niega a escribir dentro de `datos/`. Ninguna de estas imagenes es dato de
evaluacion ni entra en `datos/HASHES.sha256`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageDraw

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from p5.contrato import RISK_Y_FRACTION  # noqa: E402
from p5.datos import (  # noqa: E402
    CONJUNTOS,
    cajas_por_ruta,
    cargar_coco,
    estado_esperado,
    leer_capturas,
)
from p5.politica import cargar_config  # noqa: E402

COLORES = {"person": (255, 59, 48), "dog": (255, 204, 0), "cat": (52, 199, 255)}
COLUMNAS_HOJA = 4
ALTO_TITULO = 30


def _fuera_de_datos(destino: Path, raiz: Path) -> Path:
    destino = destino.resolve()
    if destino.is_relative_to((raiz / "datos").resolve()):
        raise SystemExit(f"se niega a escribir dentro de datos/: {destino}")
    return destino


def dibujar(ruta: Path, cajas: list, titulo: str, sub: str) -> Image.Image:
    with Image.open(ruta) as original:
        base = original.convert("RGB")  # copia en memoria
    w, h = base.size
    lienzo = Image.new("RGB", (w, h + ALTO_TITULO), "white")
    lienzo.paste(base, (0, ALTO_TITULO))
    d = ImageDraw.Draw(lienzo)
    y0 = ALTO_TITULO
    for x in (w / 3, 2 * w / 3):
        d.line([(x, y0), (x, y0 + h)], fill=(255, 255, 255), width=1)
    yr = y0 + RISK_Y_FRACTION * h
    d.line([(0, yr), (w, yr)], fill=(255, 80, 80), width=1)
    for i, (clase, (x1, y1, x2, y2)) in enumerate(cajas, 1):
        color = COLORES.get(clase, (255, 255, 255))
        d.rectangle([x1, y0 + y1, x2, y0 + y2], outline=color, width=2)
        d.text((x1 + 2, y0 + max(0, y1 - 11)), f"{i} {clase}", fill=color)
    d.text((4, 2), titulo, fill=(0, 0, 0))
    d.text((4, 15), sub, fill=(80, 80, 80))
    return lienzo


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--salida", type=Path, help="una copia PNG por cuadro")
    ap.add_argument("--hojas", type=Path, help="una hoja de contacto por secuencia")
    ap.add_argument("--secuencias", nargs="+", help="por defecto, todas")
    ap.add_argument("--config", type=Path, default=RAIZ / "config" / "politica.yaml")
    ap.add_argument("--raiz", type=Path, default=RAIZ, help="copia de Proyecto5/ para pruebas")
    args = ap.parse_args(argv)
    if not args.salida and not args.hojas:
        ap.error("indique --salida, --hojas o ambos")
    raiz = args.raiz.resolve()
    salida = _fuera_de_datos(args.salida, raiz) if args.salida else None
    hojas = _fuera_de_datos(args.hojas, raiz) if args.hojas else None
    clases = cargar_config(args.config).clases_obstaculo

    for nombre, conj in CONJUNTOS.items():
        coco = cargar_coco(raiz / conj.coco, nombre, raiz)
        revisadas = {i["file_name"] for i in coco["images"]}
        cajas = cajas_por_ruta(coco)
        por_seq: dict[str, list[Image.Image]] = {}
        for c in leer_capturas(nombre, raiz):
            if args.secuencias and c.sequence_id not in args.secuencias:
                continue
            propias = cajas.get(c.ruta, [])
            if c.ruta in revisadas:
                est = estado_esperado(propias, c.ancho, c.alto, clases)
                zonas = "+".join(est.zonas_en_riesgo) or "-"
                estado = f"{est.estado} [{zonas}] cajas={est.n_cajas}"
            else:
                estado = "SIN ANOTAR"
            titulo = f"{c.frame_id}  t={c.t_capture_ms}  {estado}"
            sub = f"P5-05: {c.scene_label}, outside_risk={c.outside_risk}"
            img = dibujar(raiz / c.ruta, propias, titulo, sub)
            if salida:
                destino = salida / c.sequence_id / f"{c.frame_id}.png"
                destino.parent.mkdir(parents=True, exist_ok=True)
                img.save(destino)
            por_seq.setdefault(c.sequence_id, []).append(img)
        if hojas:
            hojas.mkdir(parents=True, exist_ok=True)
            for seq, imgs in por_seq.items():
                w, h = imgs[0].size
                filas = (len(imgs) + COLUMNAS_HOJA - 1) // COLUMNAS_HOJA
                hoja = Image.new("RGB", (COLUMNAS_HOJA * w, filas * h), "white")
                for i, im in enumerate(imgs):
                    hoja.paste(im, ((i % COLUMNAS_HOJA) * w, (i // COLUMNAS_HOJA) * h))
                hoja.save(hojas / f"hoja_{seq}.jpg", quality=85)
                print(f"{seq}: {len(imgs)} cuadros -> {hojas / f'hoja_{seq}.jpg'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
