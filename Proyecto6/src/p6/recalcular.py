"""Recalcula, desde la evidencia exportada, las metricas base G1-G7 y las zonas/ventanas.

No usa la base de datos ni el estado del monitor: lee `run.json`, `eventos.jsonl`,
`ventanas.jsonl`, `alertas.jsonl` y las capturas en disco, recalcula con formulas escritas
aqui (independientes de `p6.metricas`) y compara con lo que reporto el monitor.

    PYTHONPATH=src python -m p6.recalcular --run evidencias/escenarios/c1-normal \
        --config config/monitoreo.yaml [--salida recalculo.json]

Sale con codigo 1 si alguna comprobacion no coincide.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import yaml

P6 = Path(__file__).resolve().parents[2]
TOL = 1e-9


def jl(p: Path) -> list[dict[str, Any]]:
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]


def pct(v: list[float], p: float) -> float | None:
    if not v:
        return None
    s = sorted(v)
    return s[max(1, math.ceil(p * len(s))) - 1]


def igual(a: Any, b: Any) -> bool:
    if a is None or b is None:
        return a is b
    if isinstance(a, float | int) and isinstance(b, float | int):
        return abs(a - b) <= TOL * max(1.0, abs(a), abs(b))
    return a == b


def recalcular(run_dir: Path, config: Path) -> dict[str, Any]:
    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    ev = jl(run_dir / "eventos.jsonl")
    ve = jl(run_dir / "ventanas.jsonl")
    al = jl(run_dir / "alertas.jsonl")
    texto = config.read_text(encoding="utf-8")
    cfg = yaml.safe_load(texto)
    inf, sup = cfg["politica"]["umbral_inferior"], cfg["politica"]["umbral_superior"]
    tam, minimo = cfg["ventanas"]["tamano_frames"], cfg["ventanas"]["minimo_puntuados"]
    checks: list[dict[str, Any]] = []

    def check(nombre: str, reportado: Any, recalculado: Any) -> None:
        checks.append(
            {
                "comprobacion": nombre,
                "reportado": reportado,
                "recalculado": recalculado,
                "coincide": igual(reportado, recalculado),
            }
        )

    check(
        "config_sha256 del run = SHA-256 de la config dada",
        run["config_sha256"],
        hashlib.sha256(texto.encode()).hexdigest(),
    )

    # Zonas por frame a partir de las candidatas y los umbrales
    malas = 0
    for e in ev:
        dets = e["detecciones"] or []
        if e["estado"] == "error":
            esperado = (None, None)
        elif not dets:
            esperado = (None, None)
        else:
            s = max(d["score"] for d in dets)
            esperado = (s, "aceptada" if s >= sup else "duda" if s >= inf else "baja")
        rep = (None if e["score_principal"] is None else round(e["score_principal"], 6), e["zona"])
        if (
            esperado[0] is not None
            and (rep[0] is None or abs(rep[0] - esperado[0]) > 1e-6 or rep[1] != esperado[1])
        ) or (esperado[0] is None and rep != (None, None)):
            malas += 1
    check("frames con zona/score inconsistente", 0, malas)

    # Ventanas
    for v in ve:
        w = [e for e in ev if e["window_id"] == v["window_id"]]
        p = [e for e in w if e["estado"] == "ok"]
        b = sum(e["score_principal"] < inf for e in p)
        check(f"{v['window_id']} frames", v["frames"], len(w))
        check(f"{v['window_id']} puntuados/bajos", [v["puntuados"], v["bajos"]], [len(p), b])
        check(f"{v['window_id']} suficiente", bool(v["suficiente"]), len(p) >= minimo)
        check(
            f"{v['window_id']} proporcion_baja", v["proporcion_baja"], (b / len(p)) if p else None
        )
        tiempos = [e["inferencia_ms"] for e in w if e["inferencia_ms"] is not None]
        check(f"{v['window_id']} G1 p95_ms", v["inferencia_p95_ms"], pct(tiempos, 0.95))
    check(
        "tamano de ventana respetado",
        True,
        all(v["frames"] <= tam for v in ve) and sum(v["frames"] for v in ve) == len(ev),
    )

    m = run["metricas"]
    t = [e["inferencia_ms"] for e in ev if e["inferencia_ms"] is not None]
    check("G1 tiempo de inferencia p50_ms", m["G1_tiempo_inferencia"]["p50_ms"], pct(t, 0.5))
    check("G1 tiempo de inferencia p95_ms", m["G1_tiempo_inferencia"]["p95_ms"], pct(t, 0.95))
    dur = max(e["t_fin_mono"] for e in ev) - min(e["t_captura_mono"] for e in ev)
    check("G2 FPS de procesamiento", m["G2_fps_procesamiento"]["fps"], len(t) / dur)
    rss = [v["rss_mib"] for v in ve]
    check("G3 RSS max MiB", m["G3_rss_proceso"]["max_mib"], max(rss))
    pun = [e for e in ev if e["estado"] == "ok"]
    check(
        "G4 proporcion de baja confianza",
        m["G4_proporcion_baja"]["proporcion"],
        (sum(e["score_principal"] < inf for e in pun) / len(pun)) if pun else None,
    )

    campos = (
        "event_id",
        "run_id",
        "frame_id",
        "source_id",
        "t_captura",
        "image_source_sha256",
        "model_sha256",
        "detector_config_sha256",
        "config_sha256",
        "estado",
        "window_id",
    )
    traz = 0
    capturas = {"declaradas": 0, "resuelven": 0}
    for e in ev:
        ok = all(e.get(c) not in (None, "") for c in campos)
        if e["estado"] == "ok" and (e["score_principal"] is None or e["zona"] is None):
            ok = False
        if e["image_ref"]:
            capturas["declaradas"] += 1
            f = P6 / e["image_ref"]
            resuelve = (
                f.is_file() and hashlib.sha256(f.read_bytes()).hexdigest() == e["image_sha256"]
            )
            capturas["resuelven"] += resuelve
            ok = ok and resuelve
        traz += ok
    check(
        "G5 cobertura de trazabilidad", m["G5_cobertura_trazabilidad"]["cobertura"], traz / len(ev)
    )
    check(
        "G6 version esperada = reportada",
        m["G6_version_esperada"]["proporcion"],
        sum(e["model_sha256"] == run["model_sha256"] for e in ev) / len(ev),
    )

    ultima = len(ve) - 1
    activas = sum(
        1
        for a in al
        if a["abierta_ventana"] <= ultima
        and (a["resuelta_ventana"] is None or a["resuelta_ventana"] > ultima)
    )
    check("G7 alertas activas al final", m["G7_alertas_activas"]["al_final"], activas)
    for v in ve:
        n = sum(
            1
            for a in al
            if a["abierta_ventana"] <= v["seq"]
            and (a["resuelta_ventana"] is None or a["resuelta_ventana"] > v["seq"])
        )
        check(f"G7 activas al cerrar {v['window_id']}", v["alertas_activas"], n)

    # Alertas: vinculos resolubles y coherentes con la regla
    ids = {e["event_id"]: e for e in ev}
    for a in al:
        evs = [ids.get(i) for i in a["event_ids"]]
        check(
            f"{a['alert_id']} eventos vinculados existen",
            True,
            bool(evs) and all(x is not None for x in evs),
        )
        if a["regla"] == "baja_confianza":
            prim = next(v for v in ve if v["seq"] == a["abierta_ventana"])
            check(
                f"{a['alert_id']} ventana de apertura cumple la condicion",
                True,
                bool(prim["suficiente"])
                and prim["proporcion_baja"] >= cfg["reglas"]["baja_confianza"]["proporcion_minima"],
            )
            check(
                f"{a['alert_id']} eventos vinculados en zona baja",
                True,
                all(x["zona"] == "baja" for x in evs),
            )
        if a["evidencia_image_ref"]:
            check(
                f"{a['alert_id']} captura de evidencia existe",
                True,
                (P6 / a["evidencia_image_ref"]).is_file(),
            )

    return {
        "run_id": run["run_id"],
        "capturas": capturas,
        "comprobaciones": len(checks),
        "fallidas": [c for c in checks if not c["coincide"]],
        "detalle": checks,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--run", required=True)
    p.add_argument("--config", default=str(P6 / "config/monitoreo.yaml"))
    p.add_argument("--salida")
    a = p.parse_args(argv)
    r = recalcular(Path(a.run), Path(a.config))
    if a.salida:
        Path(a.salida).write_text(
            json.dumps(r, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    print(
        f"{r['run_id']}: {r['comprobaciones']} comprobaciones, "
        f"{len(r['fallidas'])} fallidas; capturas {r['capturas']}"
    )
    for c in r["fallidas"]:
        print("  FALLA", c)
    return 1 if r["fallidas"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
