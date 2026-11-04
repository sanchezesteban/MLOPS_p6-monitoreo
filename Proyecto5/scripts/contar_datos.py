"""Conteos de la verdad de referencia y metas de E3 / #58 (P5-06).

    cd Proyecto5
    python scripts/contar_datos.py --secuencias S1 S5 AJ1   # fase 1
    python scripts/contar_datos.py                          # todas

Escribe `docs/conteo_datos.md` y `docs/conteo_datos.json`:

- cuadros unicos por SHA-256 de los bytes (la cifra oficial para la meta de >= 60);
- casi duplicados por pHash (informativo, adaptado del analizador de P2 en
  `src/p5/duplicados.py`; requiere `requirements-datos.txt`, si falta se indica y se omite);
- positivos (>= 1 caja de `clases_obstaculo`) y negativos (sin cajas) por secuencia y total;
- instancias por clase, cajas en riesgo y fuera de riesgo, estados esperados por secuencia;
- pares casi duplicados entre ajuste y evaluacion (deben ser 0: no se reparten copias).

Las cifras salen de las mismas cajas que el manifiesto (`p5.datos.construir_manifiesto`). Sale
con 1 si hay errores de integridad; las metas incumplidas se reportan, no cambian la salida.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from p5.contrato import en_riesgo  # noqa: E402
from p5.datos import (  # noqa: E402
    CONJUNTOS,
    ESTADOS,
    cajas_por_ruta,
    cargar_coco,
    construir_manifiesto,
    leer_capturas,
    sha256_archivo,
)
from p5.politica import cargar_config  # noqa: E402

METAS = {"unicos_sha256": 60, "secuencias": 6, "positivos": 20, "negativos": 20}


def _phash(rutas: dict[str, Path]) -> dict[str, int] | None:
    from p5.duplicados import perceptual_hash  # importa ImageHash al primer uso

    try:
        return {k: perceptual_hash(p) for k, p in rutas.items()}
    except ImportError:
        return None


def contar(raiz: Path, secuencias: set[str] | None, clases: frozenset[str]) -> dict[str, Any]:
    datos: dict[str, Any] = {"errores": [], "conjuntos": {}}
    rutas_jpeg: dict[str, Path] = {}
    negativos_ids: set[str] = set()
    conjunto_de: dict[str, str] = {}
    for nombre, conj in CONJUNTOS.items():
        todas = {c.sequence_id for c in leer_capturas(nombre, raiz)}
        pedidas = todas & secuencias if secuencias else todas
        if not pedidas:
            continue
        coco = cargar_coco(raiz / conj.coco, nombre, raiz)
        res = construir_manifiesto(nombre, coco, clases, raiz, pedidas)
        datos["errores"] += [f"{nombre}: {e}" for e in res.errores]
        cajas = cajas_por_ruta(coco)
        por_seq: dict[str, dict[str, Any]] = {}
        clases_n: Counter = Counter()
        riesgo = Counter()
        for f in res.filas:
            s = por_seq.setdefault(
                f["sequence_id"],
                {"cuadros": 0, "positivos": 0, "negativos": 0, "estados": Counter()},
            )
            s["cuadros"] += 1
            s["positivos"] += f["n_obstaculos"] > 0
            s["negativos"] += f["n_cajas"] == 0
            s["estados"][f["estado_esperado_via"]] += 1
            for clase, caja in cajas.get(f["ruta"], []):
                clases_n[clase] += 1
                riesgo["en_riesgo" if en_riesgo(caja, f["alto"]) else "fuera_de_riesgo"] += 1
            rutas_jpeg[f["frame_id"]] = raiz / f["ruta"]
            conjunto_de[f["frame_id"]] = nombre
            if f["n_cajas"] == 0:
                negativos_ids.add(f["frame_id"])
        hashes = [f["sha256"] for f in res.filas]
        recalculados = {sha256_archivo(raiz / f["ruta"]) for f in res.filas}
        datos["conjuntos"][nombre] = {
            "coco": conj.coco,
            "secuencias": {
                k: {**v, "estados": {e: v["estados"][e] for e in ESTADOS if v["estados"][e]}}
                for k, v in sorted(por_seq.items())
            },
            "cuadros": len(res.filas),
            "unicos_sha256": len(recalculados),
            "duplicados_sha256": len(hashes) - len(set(hashes)),
            "positivos": sum(v["positivos"] for v in por_seq.values()),
            "negativos": sum(v["negativos"] for v in por_seq.values()),
            "instancias_por_clase": {k: clases_n[k] for k in sorted(clases_n)},
            "cajas_por_riesgo": dict(sorted(riesgo.items())),
        }
    if "evaluacion" in datos["conjuntos"] and "ajuste" in datos["conjuntos"]:
        ev = {c.sha256 for c in leer_capturas("evaluacion", raiz)}
        aj = {c.sha256 for c in leer_capturas("ajuste", raiz)}
        datos["sha256_compartidos_ajuste_evaluacion"] = len(ev & aj)

    hashes = _phash(rutas_jpeg)
    if hashes is None:
        datos["phash"] = None
    else:
        from p5.duplicados import UMBRAL_P2, grupos, pares

        gs = grupos(hashes)
        cruzados = [p for p in pares(hashes) if conjunto_de[p[0]] != conjunto_de[p[1]]]
        ev_gs = [g for g in gs if conjunto_de[g[0]] == "evaluacion"]
        datos["phash"] = {
            "umbral_hamming": UMBRAL_P2,
            "grupos_evaluacion": len(ev_gs),
            "grupos_negativos_evaluacion": sum(all(x in negativos_ids for x in g) for g in ev_gs),
            "grupos_con_mas_de_un_cuadro": [g for g in gs if len(g) > 1],
            "pares_ajuste_evaluacion": [list(p) for p in cruzados],
        }
    ev = datos["conjuntos"].get("evaluacion")
    if ev:
        datos["metas"] = {
            "unicos_sha256": [ev["unicos_sha256"], METAS["unicos_sha256"]],
            "secuencias": [len(ev["secuencias"]), METAS["secuencias"]],
            "positivos": [ev["positivos"], METAS["positivos"]],
            "negativos": [ev["negativos"], METAS["negativos"]],
        }
    return datos


def markdown(d: dict[str, Any], secuencias: list[str] | None) -> str:
    alcance = f"`--secuencias {' '.join(secuencias)}`" if secuencias else "todas las secuencias"
    out = [
        "# Conteo de la verdad de referencia (P5-06)",
        "",
        f"Generado por `scripts/contar_datos.py` con {alcance}. No editar a mano: se regenera.",
        "Positivo = cuadro con al menos una caja de `clases_obstaculo` (incluidas laterales y",
        "fuera de riesgo); negativo = cuadro sin cajas (vacio explicito).",
        "",
    ]
    if d["errores"]:
        out += ["## Errores de integridad", ""] + [f"- {e}" for e in d["errores"]] + [""]
    if "metas" in d:
        out += ["## Metas de E3 / #58 (evaluacion)", "", "| Meta | Valor | Minimo | Cumple |"]
        out += ["|---|---:|---:|---|"]
        for k, (v, m) in d["metas"].items():
            out.append(f"| {k} | {v} | {m} | {'si' if v >= m else '**no**'} |")
        out.append("")
    for nombre, c in d["conjuntos"].items():
        out += [
            f"## {nombre}",
            "",
            f"Cuadros {c['cuadros']}, unicos por SHA-256 {c['unicos_sha256']} "
            f"(duplicados exactos {c['duplicados_sha256']}), positivos {c['positivos']}, "
            f"negativos {c['negativos']}.",
            "",
            "| Secuencia | Cuadros | Positivos | Negativos | Estados esperados |",
            "|---|---:|---:|---:|---|",
        ]
        for s, v in c["secuencias"].items():
            est = ", ".join(f"{e} {n}" for e, n in v["estados"].items())
            out.append(f"| {s} | {v['cuadros']} | {v['positivos']} | {v['negativos']} | {est} |")
        clases = ", ".join(f"{k} {n}" for k, n in c["instancias_por_clase"].items()) or "ninguna"
        riesgo = ", ".join(f"{k} {n}" for k, n in c["cajas_por_riesgo"].items()) or "ninguna"
        out += ["", f"Instancias por clase: {clases}. Cajas: {riesgo}.", ""]
    if "sha256_compartidos_ajuste_evaluacion" in d:
        n = d["sha256_compartidos_ajuste_evaluacion"]
        out += [f"JPEG con el mismo SHA-256 en ajuste y evaluacion: {n}.", ""]
    out += ["## Casi duplicados por pHash (informativo)", ""]
    p = d["phash"]
    if p is None:
        out += ["No calculado: falta `ImageHash` (`pip install -r requirements-datos.txt`).", ""]
    else:
        out += [
            f"Umbral de Hamming <= {p['umbral_hamming']} bits (el de P2). Grupos en evaluacion: "
            f"{p['grupos_evaluacion']}; grupos formados solo por negativos: "
            f"{p['grupos_negativos_evaluacion']}. Pares entre ajuste y evaluacion: "
            f"{len(p['pares_ajuste_evaluacion'])}.",
            "",
        ]
        grandes = p["grupos_con_mas_de_un_cuadro"]
        out += ["Grupos con mas de un cuadro:", ""]
        out += [f"- {', '.join(g)}" for g in grandes] or ["- ninguno"]
        out.append("")
    return "\n".join(out).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--secuencias", nargs="+", help="p. ej. S1 S5 AJ1; por defecto, todas")
    ap.add_argument("--config", type=Path, default=RAIZ / "config" / "politica.yaml")
    ap.add_argument("--salida", type=Path, default=RAIZ / "docs", help="carpeta de conteo_datos.*")
    ap.add_argument("--raiz", type=Path, default=RAIZ, help="copia de Proyecto5/ para pruebas")
    args = ap.parse_args(argv)
    clases = cargar_config(args.config).clases_obstaculo
    d = contar(args.raiz.resolve(), set(args.secuencias) if args.secuencias else None, clases)
    md = markdown(d, args.secuencias)
    args.salida.mkdir(parents=True, exist_ok=True)
    (args.salida / "conteo_datos.md").write_text(md, encoding="utf-8", newline="\n")
    texto = json.dumps(d, indent=2, ensure_ascii=False, default=list) + "\n"
    (args.salida / "conteo_datos.json").write_text(texto, encoding="utf-8", newline="\n")
    print(md)
    return 1 if d["errores"] else 0


if __name__ == "__main__":
    sys.exit(main())
