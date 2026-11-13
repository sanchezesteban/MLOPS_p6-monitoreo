"""python -m p6.portal --db evidencias/monitoreo.db [--puerto 8060]"""

from __future__ import annotations

import argparse
from pathlib import Path

import uvicorn

from p6 import RAIZ_P6
from p6.portal.app import crear_app


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--db", default=str(RAIZ_P6 / "evidencias/monitoreo.db"))
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--puerto", type=int, default=8060)
    a = p.parse_args()
    uvicorn.run(crear_app(Path(a.db).resolve()), host=a.host, port=a.puerto)


if __name__ == "__main__":
    main()
