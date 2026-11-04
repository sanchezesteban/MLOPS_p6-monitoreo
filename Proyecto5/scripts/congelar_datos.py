"""Escribe `datos/HASHES.sha256` (P5-06, #58): congelado de los datos de ajuste y evaluacion.

    cd Proyecto5
    python scripts/congelar_datos.py

Incluye los JPEG y `capturas.csv` de `datos/evaluacion/` y `datos/ajuste/`, los manifiestos y
los COCO. Formato `sha256sum` con rutas relativas a `Proyecto5/`; se verifica con
`python scripts/verificar_hashes.py` (Linux y Windows) o `sha256sum -c datos/HASHES.sha256`.
No incluye configuracion (`config/*.yaml`) ni imagenes de revision de `docs/`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from p5.datos import archivos_congelados, escribir_hashes  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--raiz", type=Path, default=RAIZ, help="copia de Proyecto5/ para pruebas")
    raiz = ap.parse_args(argv).raiz.resolve()
    destino = escribir_hashes(raiz)
    print(f"{len(archivos_congelados(raiz))} archivos -> {destino}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
