"""Verifica CSV, JPEG, hashes y mínimos sin conectarse a la cámara."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from capturas_core import inspect, read_rows

DATA = Path(__file__).resolve().parents[1] / "datos"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--datos", type=Path, default=DATA / "evaluacion")
    parser.add_argument("--ajuste", type=Path, default=DATA / "ajuste")
    parser.add_argument(
        "--issue57",
        action="store_true",
        help="También exige etiquetas 20/20, fuera de riesgo y ajuste separado",
    )
    parser.add_argument(
        "--solo-integridad",
        action="store_true",
        help="Permite revisar ajuste o capturas parciales sin exigir 6 x 10",
    )
    parser.add_argument("--reporte", type=Path, help="JSON generado con los datos verificados")
    args = parser.parse_args()
    if args.issue57 and args.solo_integridad:
        parser.error("--issue57 y --solo-integridad son excluyentes")
    try:
        report = inspect(args.datos, minimums=not args.solo_integridad)
        if args.issue57:
            errors = report["errors"]
            for label in ("obstaculo", "despejado"):
                if report.get("labels", {}).get(label, 0) < 20:
                    errors.append(f"Se necesitan >=20 cuadros etiquetados {label}")
            if report.get("labels", {}).get("pendiente", 0):
                errors.append("Quedan etiquetas de escena pendientes de revisión")
            if not report.get("outside_risk"):
                errors.append("Faltan cuadros marcados con objetos fuera de riesgo")
            adjustment = inspect(args.ajuste, minimums=False)
            report["ajuste"] = adjustment
            errors.extend(f"Ajuste: {error}" for error in adjustment["errors"])
            if sum(count > 0 for count in adjustment["counts"].values()) not in (1, 2):
                errors.append("Ajuste requiere 1-2 secuencias no vacías")
            if set(report.get("sessions", [])) & set(adjustment.get("sessions", [])):
                errors.append("Evaluación y ajuste comparten session_id")
            if adjustment["ok"] and report.get("total", 0):
                eval_hashes = {row["sha256"] for row in read_rows(args.datos)}
                adjustment_hashes = {row["sha256"] for row in read_rows(args.ajuste)}
                if eval_hashes & adjustment_hashes:
                    errors.append("Evaluación y ajuste contienen JPEG idénticos")
            report["ok"] = not errors
        output = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
        print(output, end="")
        if args.reporte:
            # Un informe no debe sobrescribir el CSV, los JPEG ni otra evidencia.
            if args.reporte.suffix.lower() != ".json":
                parser.error("--reporte debe terminar en .json")
            if args.reporte.exists():
                parser.error("El reporte ya existe; elegir un nombre nuevo")
            args.reporte.parent.mkdir(parents=True, exist_ok=True)
            with args.reporte.open("x", encoding="utf-8", newline="\n") as handle:
                handle.write(output)
        return 0 if report["ok"] else 1
    except (OSError, ValueError, ImportError) as exc:
        print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
