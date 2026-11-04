"""Manifiesto de la verdad de referencia (P5-06, #58) desde `capturas.csv` y el COCO.

    cd Proyecto5
    python scripts/construir_manifiesto.py --secuencias S1 S5 AJ1   # fase 1
    python scripts/construir_manifiesto.py                          # todas

Escribe `datos/manifiesto.csv` (evaluacion) y `datos/manifiesto_ajuste.csv` (ajuste) con las
columnas de #58 mas columnas de trazabilidad, y `docs/discrepancias_datos.md`.

- `estado_esperado_via` sale de las cajas anotadas con `p5.contrato.zonas_ocupadas` y
  `p5.contrato.en_riesgo` (solo `clases_obstaculo` de `config/politica.yaml`).
- SHA-256 y dimensiones se recalculan desde los bytes del JPEG y se comparan con el CSV.
- Errores de integridad (cuadro sin anotar, caja fuera del cuadro, hash o dimensiones
  distintas, COCO con imagenes ajenas): no se escribe el manifiesto y sale con 1.
- Discrepancias semanticas (estado distinto de la intencion de la secuencia o de
  `scene_label`/`outside_risk` de P5-05): se listan para revisarlas con quien anota; nunca se
  corrigen solas. No cambian el codigo de salida.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from p5.datos import (  # noqa: E402
    COLUMNAS_MANIFIESTO,
    CONJUNTOS,
    cargar_coco,
    construir_manifiesto,
    escribir_csv,
    leer_capturas,
    sha256_archivo,
)
from p5.politica import cargar_config  # noqa: E402


def _reporte(resultados: dict, secuencias: list[str] | None, raiz: Path) -> str:
    lineas = [
        "# Discrepancias de la verdad de referencia (P5-06)",
        "",
        "Generado por `scripts/construir_manifiesto.py`"
        + (f" con `--secuencias {' '.join(secuencias)}`" if secuencias else "")
        + ". No editar a mano: se regenera.",
        "",
        "Las discrepancias se revisan con quien anota. Si la caja es correcta, la discrepancia",
        "se queda y se explica en `docs/datos.md`; nunca se mueven cajas para que cuadre.",
        "",
    ]
    for conjunto, (res, coco_rel) in resultados.items():
        coco = raiz / coco_rel
        sha = sha256_archivo(coco)[:12] if coco.is_file() else "no existe"
        lineas += [
            f"## {conjunto}",
            "",
            f"- COCO: `{coco_rel}` (SHA-256 `{sha}…`), cuadros en el manifiesto: {len(res.filas)}",
            f"- Errores de integridad: {len(res.errores)}",
            f"- Discrepancias a revisar: {len(res.discrepancias)}",
            "",
        ]
        for titulo, lista in (("Errores", res.errores), ("Discrepancias", res.discrepancias)):
            if lista:
                lineas += [f"### {titulo}", ""] + [f"- {x}" for x in lista] + [""]
    return "\n".join(lineas).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--secuencias", nargs="+", help="p. ej. S1 S5 AJ1; por defecto, todas")
    ap.add_argument("--config", type=Path, default=RAIZ / "config" / "politica.yaml")
    ap.add_argument("--reporte", type=Path, default=RAIZ / "docs" / "discrepancias_datos.md")
    ap.add_argument("--raiz", type=Path, default=RAIZ, help="copia de Proyecto5/ para pruebas")
    args = ap.parse_args(argv)
    raiz = args.raiz.resolve()
    clases = cargar_config(args.config).clases_obstaculo

    resultados = {}
    codigo = 0
    for nombre, conj in CONJUNTOS.items():
        todas = {c.sequence_id for c in leer_capturas(nombre, raiz)}
        pedidas = todas & set(args.secuencias) if args.secuencias else todas
        if not pedidas:
            continue
        coco = cargar_coco(raiz / conj.coco, nombre, raiz)
        res = construir_manifiesto(nombre, coco, clases, raiz, pedidas)
        resultados[nombre] = (res, conj.coco)
        if res.errores:
            codigo = 1
            print(f"{nombre}: {len(res.errores)} errores; no se escribe {conj.manifiesto}")
        else:
            escribir_csv(raiz / conj.manifiesto, res.filas, COLUMNAS_MANIFIESTO)
            print(f"{nombre}: {len(res.filas)} cuadros -> {conj.manifiesto}")
        for e in res.errores:
            print(f"  ERROR {e}", file=sys.stderr)
        for d in res.discrepancias:
            print(f"  REVISAR {d}")
    if args.secuencias:
        conocidas = set().union(
            *({c.sequence_id for c in leer_capturas(n, raiz)} for n in CONJUNTOS)
        )
        for s in sorted(set(args.secuencias) - conocidas):
            print(f"ERROR secuencia desconocida: {s}", file=sys.stderr)
            codigo = 1
    args.reporte.parent.mkdir(parents=True, exist_ok=True)
    texto = _reporte(resultados, args.secuencias, raiz)
    args.reporte.write_text(texto, encoding="utf-8", newline="\n")
    print(f"reporte -> {args.reporte}")
    return codigo


if __name__ == "__main__":
    sys.exit(main())
