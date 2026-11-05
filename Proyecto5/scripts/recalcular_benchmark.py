"""Recalcula P5-08 desde CSV/contexto sin inferencia; nunca sobrescribe resultados."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from p5.benchmark import escribir_json, recalcular


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mediciones", type=Path, required=True)
    parser.add_argument("--salida", type=Path, help="JSON nuevo; sin este parametro solo verifica")
    args = parser.parse_args(argv)
    try:
        resultado = recalcular(args.mediciones)
        original = json.loads((args.mediciones / "resumen.json").read_text(encoding="utf-8"))
        if resultado != original:
            print("ERROR: resumen original distinto del recalculo", file=sys.stderr)
            return 1
        if args.salida:
            escribir_json(args.salida, resultado)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print("Recalculo identico; sin modelo ni inferencia.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
