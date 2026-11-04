"""Anotador local de la verdad de referencia (P5-06, #58). Solo biblioteca estandar.

    cd Proyecto5
    python scripts/anotador/servidor.py --secuencias S1 S5 AJ1   # fase 1
    python scripts/anotador/servidor.py                          # todas las secuencias

Abre http://127.0.0.1:8765. Muestra cada cuadro en orden de `t_capture_ms` con los tercios y
la linea de riesgo (y = H/2) dibujados solo en pantalla; los JPEG se abren en modo lectura y
nunca se escriben. Cada «Guardar» o «Sin objetos» reescribe `datos/anotaciones.json` (o
`datos/anotaciones_ajuste.json`) de forma atomica, asi que el avance se conserva y una
secuencia nueva de `capturas.csv` aparece como pendiente sin tocar lo ya anotado.

La verdad de referencia la decide la persona que anota: el anotador no ejecuta el detector ni
propone cajas.
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

RAIZ = Path(__file__).resolve().parents[2]  # Proyecto5/
sys.path.insert(0, str(RAIZ / "src"))

from p5.datos import (  # noqa: E402
    CONJUNTOS,
    DatosError,
    cajas_por_ruta,
    cargar_coco,
    estado_esperado,
    guardar_coco,
    leer_capturas,
    quitar_cuadro,
    registrar_cuadro,
    sincronizar,
)
from p5.politica import cargar_config  # noqa: E402

HTML = Path(__file__).with_name("index.html")
_CANDADO = threading.Lock()


class Anotador:
    def __init__(self, raiz: Path, secuencias: set[str] | None, clases: frozenset[str]) -> None:
        self.raiz = raiz
        self.secuencias = secuencias
        self.clases = clases

    def _cuadros(self, conjunto: str):
        cuadros = leer_capturas(conjunto, self.raiz)
        if self.secuencias:
            cuadros = [c for c in cuadros if c.sequence_id in self.secuencias]
        return cuadros

    def _cuadro(self, conjunto: str, idx: int):
        cuadros = self._cuadros(conjunto)
        if not 0 <= idx < len(cuadros):
            raise DatosError(f"idx {idx} fuera de 0..{len(cuadros) - 1}")
        return cuadros[idx]

    def _coco(self, conjunto: str):
        return cargar_coco(self.raiz / CONJUNTOS[conjunto].coco, conjunto, self.raiz)

    def estado(self, conjunto: str) -> dict[str, Any]:
        cuadros = self._cuadros(conjunto)
        coco = self._coco(conjunto)
        avisos = sincronizar(coco, leer_capturas(conjunto, self.raiz))
        cajas = cajas_por_ruta(coco)
        imgs = {i["file_name"]: i for i in coco["images"]}
        filas = []
        for idx, c in enumerate(cuadros):
            img = imgs.get(c.ruta)
            propias = cajas.get(c.ruta, [])
            est = estado_esperado(propias, c.ancho, c.alto, self.clases) if img else None
            filas.append(
                {
                    "idx": idx,
                    "sequence_id": c.sequence_id,
                    "frame_id": c.frame_id,
                    "frame_id_origen": c.frame_id_origen,
                    "t_capture_ms": c.t_capture_ms,
                    "ruta": c.ruta,
                    "ancho": c.ancho,
                    "alto": c.alto,
                    "scene_label": c.scene_label,
                    "outside_risk": c.outside_risk,
                    "revisado": img is not None,
                    "sin_objetos": bool(img and img.get("sin_objetos")),
                    "cajas": [
                        {"clase": k, "bbox": [x1, y1, round(x2 - x1, 1), round(y2 - y1, 1)]}
                        for k, (x1, y1, x2, y2) in propias
                    ],
                    "estado": est.estado if est else None,
                    "zonas_en_riesgo": list(est.zonas_en_riesgo) if est else [],
                }
            )
        return {
            "conjunto": conjunto,
            "coco": CONJUNTOS[conjunto].coco,
            "categorias": [c["name"] for c in coco["categories"]],
            "cuadros": filas,
            "avisos": avisos,
        }

    def imagen(self, conjunto: str, idx: int) -> bytes:
        c = self._cuadro(conjunto, idx)
        return (self.raiz / c.ruta).read_bytes()  # solo lectura

    def guardar(self, conjunto: str, idx: int, cajas: list, sin_objetos: bool) -> None:
        with _CANDADO:
            c = self._cuadro(conjunto, idx)
            coco = self._coco(conjunto)
            sincronizar(coco, leer_capturas(conjunto, self.raiz))
            registrar_cuadro(coco, c, cajas, sin_objetos)
            guardar_coco(self.raiz / CONJUNTOS[conjunto].coco, coco)

    def desmarcar(self, conjunto: str, idx: int) -> None:
        with _CANDADO:
            c = self._cuadro(conjunto, idx)
            coco = self._coco(conjunto)
            quitar_cuadro(coco, c.ruta)
            guardar_coco(self.raiz / CONJUNTOS[conjunto].coco, coco)


def fabricar_manejador(anotador: Anotador):
    class Manejador(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:  # silencioso salvo errores
            pass

        def _enviar(self, codigo: int, cuerpo: bytes, tipo: str) -> None:
            self.send_response(codigo)
            self.send_header("Content-Type", tipo)
            self.send_header("Content-Length", str(len(cuerpo)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(cuerpo)

        def _json(self, codigo: int, datos: Any) -> None:
            cuerpo = json.dumps(datos, ensure_ascii=False).encode("utf-8")
            self._enviar(codigo, cuerpo, "application/json; charset=utf-8")

        def _conjunto(self, valor: str | None) -> str:
            if valor not in CONJUNTOS:
                raise DatosError(f"conjunto desconocido: {valor}")
            return valor

        def do_GET(self) -> None:
            url = urlparse(self.path)
            q = {k: v[0] for k, v in parse_qs(url.query).items()}
            try:
                if url.path == "/":
                    self._enviar(200, HTML.read_bytes(), "text/html; charset=utf-8")
                elif url.path == "/api/estado":
                    self._json(200, anotador.estado(self._conjunto(q.get("conjunto"))))
                elif url.path == "/img":
                    datos = anotador.imagen(self._conjunto(q.get("conjunto")), int(q["idx"]))
                    self._enviar(200, datos, "image/jpeg")
                else:
                    self._json(404, {"error": "no existe"})
            except (DatosError, KeyError, ValueError, IndexError) as exc:
                self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})

        def do_POST(self) -> None:
            url = urlparse(self.path)
            try:
                largo = int(self.headers.get("Content-Length", "0"))
                datos = json.loads(self.rfile.read(largo) or b"{}")
                conjunto = self._conjunto(datos.get("conjunto"))
                idx = int(datos["idx"])
                if url.path == "/api/guardar":
                    anotador.guardar(
                        conjunto, idx, list(datos.get("cajas", [])), bool(datos["sin_objetos"])
                    )
                elif url.path == "/api/desmarcar":
                    anotador.desmarcar(conjunto, idx)
                else:
                    self._json(404, {"error": "no existe"})
                    return
                self._json(200, anotador.estado(conjunto)["cuadros"][idx])
            except (DatosError, KeyError, ValueError, IndexError, TypeError) as exc:
                self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})

    return Manejador


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--puerto", type=int, default=8765)
    ap.add_argument(
        "--secuencias", nargs="+", help="solo estas (S1 S5 AJ1); por defecto, todas las del CSV"
    )
    ap.add_argument("--config", type=Path, default=RAIZ / "config" / "politica.yaml")
    ap.add_argument(
        "--raiz", type=Path, default=RAIZ, help="copia de Proyecto5/ para pruebas (default: este)"
    )
    args = ap.parse_args(argv)
    clases = cargar_config(args.config).clases_obstaculo
    raiz = args.raiz.resolve()
    anotador = Anotador(raiz, set(args.secuencias) if args.secuencias else None, clases)
    for nombre in CONJUNTOS:
        anotador.estado(nombre)  # falla aqui, no en el navegador, si un CSV esta desordenado
    servidor = ThreadingHTTPServer(("127.0.0.1", args.puerto), fabricar_manejador(anotador))
    print(f"Anotador en http://127.0.0.1:{args.puerto}  (Ctrl+C para salir)", flush=True)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        servidor.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
