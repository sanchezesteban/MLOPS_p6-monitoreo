"""Verifica `datos/HASHES.sha256` contra los bytes en disco (Linux y Windows) (P5-06).

    cd Proyecto5
    python scripts/verificar_hashes.py

Sale con 1 si un archivo falta, cambio su SHA-256 o hay un dato de evaluacion/ajuste
(JPEG, capturas.csv, manifiesto o COCO) que no esta registrado. Equivale a
`sha256sum -c datos/HASHES.sha256` mas la comprobacion de archivos no registrados.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from p5.datos import ARCHIVO_HASHES, verificar_hashes  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--raiz", type=Path, default=RAIZ, help="copia de Proyecto5/ para pruebas")
    raiz = ap.parse_args(argv).raiz.resolve()
    problemas = verificar_hashes(raiz)
    for p in problemas:
        print(f"FALLA {p}", file=sys.stderr)
    n = len((raiz / ARCHIVO_HASHES).read_text(encoding="utf-8").splitlines())
    print(f"{ARCHIVO_HASHES}: {n} archivos, {len(problemas)} problemas")
    return 1 if problemas else 0


if __name__ == "__main__":
    sys.exit(main())
