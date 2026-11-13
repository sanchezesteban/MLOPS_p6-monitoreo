"""Metricas ADICIONALES (extras M), calculadas fuera de linea desde la evidencia exportada.

Cada metrica usa observaciones primarias ya registradas por el monitor (eventos.jsonl,
ventanas.jsonl, alertas.jsonl), el manifiesto del stream y la referencia. Ninguna es la
metrica base de su grupo (ver docs/metricas.md). Sin observaciones -> None.

    PYTHONPATH=src python -m p6.extras --run evidencias/escenarios/s-sostenido \
        [--salida evidencias/escenarios/s-sostenido/metricas_extra.json]
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any

from p6 import RAIZ_P6

TAM_MIN_KS = 6  # mismo minimo de frames puntuados que una ventana suficiente


def _jl(p: Path) -> list[dict[str, Any]]:
    if not p.is_file():
        return []
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]


def _iso(t: str) -> datetime:
    return datetime.fromisoformat(t.replace("Z", "+00:00"))


def _pct(v: list[float], p: float) -> float | None:
    if not v:
        return None
    s = sorted(v)
    return s[max(1, math.ceil(p * len(s))) - 1]


# --- M-FPSCAP (G2): FPS de captura ------------------------------------------------------
def fps_captura(evs: list[dict[str, Any]]) -> float | None:
    """(frames emitidos - 1) / (emision del ultimo - emision del primero). <2 frames -> None.

    Mide la etapa de la FUENTE (ritmo de emision), distinta de la base G2 (procesamiento).
    """
    if len(evs) < 2:
        return None
    t = sorted(e["t_captura_mono"] for e in evs)
    dur = t[-1] - t[0]
    return (len(t) - 1) / dur if dur > 0 else None


# --- M-E2E (G2): latencia extremo a extremo ---------------------------------------------
def latencia_e2e(evs: list[dict[str, Any]]) -> dict[str, Any]:
    """t_fin_mono - t_captura_mono (ms), de la emision del frame al evento listo.

    Poblacion: frames inferidos (ok o sin_detecciones); mismo reloj monotono del proceso.
    """
    v = [
        (e["t_fin_mono"] - e["t_captura_mono"]) * 1000
        for e in evs
        if e["estado"] in ("ok", "sin_detecciones")
    ]
    return {"n": len(v), "p50_ms": _pct(v, 0.5), "p95_ms": _pct(v, 0.95)}


# --- M-SINDET (G4): proporcion de frames sin detecciones --------------------------------
def proporcion_sin_detecciones(evs: list[dict[str, Any]]) -> float | None:
    """sin_detecciones / frames inferidos (ok + sin_detecciones). Excluye errores."""
    inf = [e for e in evs if e["estado"] in ("ok", "sin_detecciones")]
    return (sum(e["estado"] == "sin_detecciones" for e in inf) / len(inf)) if inf else None


# --- M-ERR (G1): tasa de errores tecnicos -----------------------------------------------
def tasa_errores(evs: list[dict[str, Any]]) -> float | None:
    """frames con estado error / frames intentados (todos los emitidos por la fuente)."""
    return (sum(e["estado"] == "error" for e in evs) / len(evs)) if evs else None


# --- M-CPU (G3): CPU del proceso --------------------------------------------------------
def cpu_proceso(ventanas: list[dict[str, Any]]) -> dict[str, Any]:
    """psutil cpu_percent del proceso entre cierres de ventana (100 = 1 nucleo)."""
    v = [w["cpu_pct"] for w in ventanas if w.get("cpu_pct") is not None]
    if not v:
        return {"n": 0, "max_pct": None, "media_pct": None}
    return {"n": len(v), "max_pct": max(v), "media_pct": sum(v) / len(v)}


# --- M-KS (G4): distancia de la distribucion de confianza a la referencia ---------------
def ks(a: list[float], b: list[float]) -> float | None:
    """Estadistico de Kolmogorov-Smirnov de dos muestras: max |F_a(x) - F_b(x)|."""
    if not a or not b:
        return None
    a, b = sorted(a), sorted(b)
    i = j = 0
    d = 0.0
    for x in sorted(set(a) | set(b)):
        while i < len(a) and a[i] <= x:
            i += 1
        while j < len(b) and b[j] <= x:
            j += 1
        d = max(d, abs(i / len(a) - j / len(b)))
    return d


def ks_por_ventana(evs: list[dict[str, Any]], ref_scores: list[float]) -> list[dict[str, Any]]:
    """KS entre los scores principales de cada ventana y los de la referencia.

    Supuestos/limites: es descriptivo (los frames consecutivos no son independientes, por eso
    no se reporta p-valor); con < 6 frames puntuados la ventana no tiene KS (None).
    """
    out = []
    ventanas: dict[str, list[dict[str, Any]]] = {}
    for e in evs:
        ventanas.setdefault(e["window_id"], []).append(e)
    for wid, w in ventanas.items():
        s = [e["score_principal"] for e in w if e["estado"] == "ok"]
        out.append(
            {
                "window_id": wid,
                "n": len(s),
                "ks": ks(s, ref_scores) if len(s) >= TAM_MIN_KS else None,
            }
        )
    return out


# --- M-TDET y M-TREC (G7): tiempo de deteccion y de recuperacion ------------------------
def fases(manifiesto: Path) -> list[str] | None:
    with manifiesto.open(encoding="utf-8", newline="") as f:
        filas = list(csv.DictReader(f))
    if not filas or "fase" not in filas[0]:
        return None
    return [r["fase"] for r in filas]


def tiempos_incidente(
    evs: list[dict[str, Any]], alertas: list[dict[str, Any]], fase: list[str] | None
) -> dict[str, Any]:
    """Correlaciona el registro de incidente (fases del manifiesto) con eventos y alertas.

    inicio  = t_captura del primer frame cuya fase no es `normal` ni `recuperacion`
    fin     = t_captura del primer frame en fase `recuperacion`
    deteccion(regla)    = t_apertura de la primera alerta de esa regla abierta >= inicio
    recuperacion(regla) = t_resolucion de esa alerta - fin
    Sin fases, sin incidente o sin alerta -> None.
    """
    if not fase:
        return {"incidente": None, "por_regla": {}}
    por_seq = {e["seq"]: e for e in evs}
    ini = next((i for i, f in enumerate(fase) if f not in ("normal", "recuperacion")), None)
    fin = next((i for i, f in enumerate(fase) if f == "recuperacion"), None)
    if ini is None or ini not in por_seq:
        return {"incidente": None, "por_regla": {}}
    t_ini = _iso(por_seq[ini]["t_captura"])
    t_fin = _iso(por_seq[fin]["t_captura"]) if fin is not None and fin in por_seq else None
    res: dict[str, Any] = {}
    for a in sorted(alertas, key=lambda x: x["t_apertura"]):
        if a["rule_id"] in res or _iso(a["t_apertura"]) < t_ini:
            continue
        rec = None
        if t_fin is not None and a.get("t_resolucion"):
            rec = (_iso(a["t_resolucion"]) - t_fin).total_seconds()
        res[a["rule_id"]] = {
            "alert_id": a["alert_id"],
            "tiempo_deteccion_s": (_iso(a["t_apertura"]) - t_ini).total_seconds(),
            "tiempo_recuperacion_s": rec,
        }
    return {
        "incidente": {
            "frame_inicio": ini,
            "t_inicio": por_seq[ini]["t_captura"],
            "frame_fin": fin,
            "t_fin": por_seq[fin]["t_captura"] if t_fin else None,
        },
        "por_regla": res,
    }


def calcular(run_dir: Path) -> dict[str, Any]:
    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    return calcular_desde(
        run,
        _jl(run_dir / "eventos.jsonl"),
        _jl(run_dir / "ventanas.jsonl"),
        _jl(run_dir / "alertas.jsonl"),
    )


def calcular_desde(
    run: dict[str, Any],
    evs: list[dict[str, Any]],
    ves: list[dict[str, Any]],
    als: list[dict[str, Any]],
) -> dict[str, Any]:
    """Mismo calculo desde registros ya cargados (lo usa tambien el portal)."""
    ref_path = RAIZ_P6 / "evidencias/referencia/referencia.json"
    ref = json.loads(ref_path.read_text()) if ref_path.is_file() else {}
    ref_ok = (
        ref.get("model_sha256") == run["model_sha256"]
        and ref.get("detector_config_sha256") == run["detector_config_sha256"]
    )
    manifiesto = RAIZ_P6 / run["manifiesto"]
    por_ventana = []
    for w in ves:
        we = [e for e in evs if e["window_id"] == w["window_id"]]
        por_ventana.append(
            {
                "window_id": w["window_id"],
                "fps_captura": fps_captura(we),
                "latencia_e2e_p95_ms": latencia_e2e(we)["p95_ms"],
                "proporcion_sin_detecciones": proporcion_sin_detecciones(we),
                "tasa_errores": tasa_errores(we),
                "cpu_pct": w.get("cpu_pct"),
            }
        )
    ksv = ks_por_ventana(evs, ref.get("scores_ordenados", [])) if ref_ok else []
    for pv, k in zip(por_ventana, ksv, strict=False):
        pv["ks_vs_referencia"] = k["ks"]
    run_scores = [e["score_principal"] for e in evs if e["estado"] == "ok"]
    return {
        "run_id": run["run_id"],
        "referencia_compatible": ref_ok,
        "corrida": {
            "M-FPSCAP_fps_captura": fps_captura(evs),
            "M-E2E_latencia_e2e": latencia_e2e(evs),
            "M-SINDET_proporcion_sin_detecciones": proporcion_sin_detecciones(evs),
            "M-ERR_tasa_errores": tasa_errores(evs),
            "M-CPU_cpu_proceso": cpu_proceso(ves),
            "M-KS_ks_vs_referencia": ks(run_scores, ref.get("scores_ordenados", []))
            if ref_ok and len(run_scores) >= TAM_MIN_KS
            else None,
            "M-TDET_M-TREC_incidente": tiempos_incidente(
                evs, als, fases(manifiesto) if manifiesto.is_file() else None
            ),
        },
        "por_ventana": por_ventana,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--run", required=True)
    p.add_argument("--salida")
    a = p.parse_args(argv)
    r = calcular(Path(a.run))
    texto = json.dumps(r, indent=2, ensure_ascii=False)
    if a.salida:
        Path(a.salida).write_text(texto + "\n", encoding="utf-8")
    print(texto)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
