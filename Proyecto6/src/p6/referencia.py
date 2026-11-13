"""Construye `referencia.json` a partir de una corrida de referencia exportada.

    PYTHONPATH=src python -m p6.referencia --run evidencias/escenarios/ref-carrito \
        --config config/monitoreo.yaml --salida evidencias/referencia/referencia.json

La referencia conserva la identidad de la comparacion (modelo, configuracion del detector y
umbral inferior) y la proporcion de frames en zona baja entre frames puntuados. La regla de
cambio sostenido solo compara contra una referencia con la misma identidad.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from p6 import metricas
from p6.config import cargar


def construir(run_dir: Path, config: Path) -> dict:
    cfg = cargar(config)
    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    eventos = [json.loads(x) for x in (run_dir / "eventos.jsonl").read_text().splitlines() if x]
    scores = sorted(e["score_principal"] for e in eventos if e["estado"] == "ok")
    bajos = sum(s < cfg.umbral_inferior for s in scores)
    ventanas = [json.loads(x) for x in (run_dir / "ventanas.jsonl").read_text().splitlines() if x]
    suf = [v["proporcion_baja"] for v in ventanas if v["suficiente"]]
    return {
        "run_id": run["run_id"],
        "git_commit": run["git_commit"],
        "manifiesto": run["manifiesto"],
        "manifiesto_sha256": run["manifiesto_sha256"],
        "model_sha256": run["model_sha256"],
        "detector_config_sha256": run["detector_config_sha256"],
        "config_sha256_corrida": run["config_sha256"],
        "umbral_inferior": cfg.umbral_inferior,
        "umbral_superior": cfg.umbral_superior,
        "unidad": "frame (score principal = maximo de sus candidatas)",
        "frames": len(eventos),
        "puntuados": len(scores),
        "bajos": bajos,
        "proporcion_baja": (bajos / len(scores)) if scores else None,
        "sin_detecciones": sum(e["estado"] == "sin_detecciones" for e in eventos),
        "errores": sum(e["estado"] == "error" for e in eventos),
        "cuantiles_score": {
            f"p{int(p * 100)}": metricas.percentil_rango(scores, p)
            for p in (0.10, 0.15, 0.25, 0.50, 0.75, 0.90)
        },
        "scores_ordenados": scores,
        "ventanas_suficientes": len(suf),
        "proporcion_baja_max_ventana": max(suf) if suf else None,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--run", required=True)
    p.add_argument("--config", required=True)
    p.add_argument("--salida", required=True)
    a = p.parse_args(argv)
    ref = construir(Path(a.run), Path(a.config))
    Path(a.salida).parent.mkdir(parents=True, exist_ok=True)
    Path(a.salida).write_text(json.dumps(ref, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in ref.items() if k != "scores_ordenados"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
