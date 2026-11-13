"""Fuente visual: reproduce una secuencia de imagenes como stream a una frecuencia declarada.

Politica de muestreo: cada imagen del manifiesto se entrega una sola vez, en orden, con un
intervalo objetivo de `1/fps` segundos. No hay descartes: si el consumidor tarda mas que el
intervalo, el siguiente frame sale de inmediato (el retraso queda en los tiempos registrados).

Cada frame lleva identidad (`frame_id`), la ruta y el SHA-256 de la imagen de origen y los
instantes de emision (`t_captura`). La fuente no abre la imagen: el detector la lee.
"""

from __future__ import annotations

import csv
import hashlib
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass(frozen=True)
class Frame:
    indice: int
    frame_id: str
    source_id: str
    ruta: Path
    ruta_rel: str
    sha256_declarado: str | None
    t_captura: str  # ISO-8601 UTC del instante de emision
    t_captura_mono: float  # reloj monotono (perf_counter) del mismo instante


def ahora_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def sha256_archivo(ruta: Path) -> str:
    h = hashlib.sha256()
    with ruta.open("rb") as f:
        while bloque := f.read(1 << 20):
            h.update(bloque)
    return h.hexdigest()


def leer_manifiesto(ruta: Path, raiz: Path) -> list[tuple[Path, str, str | None]]:
    """Filas `path,sha256` (sha256 opcional); rutas relativas a `raiz` (raiz del repositorio)."""
    filas = []
    with ruta.open(encoding="utf-8", newline="") as f:
        for fila in csv.DictReader(f):
            rel = fila["path"].strip()
            filas.append((raiz / rel, rel, (fila.get("sha256") or "").strip() or None))
    if not filas:
        raise ValueError(f"{ruta}: manifiesto vacio")
    return filas


class SecuenciaFuente:
    """Stream reproducido desde un manifiesto, a `fps` frames por segundo."""

    tipo = "secuencia"

    def __init__(
        self,
        manifiesto: Path,
        raiz: Path,
        source_id: str,
        fps: float,
        dormir: Callable[[float], None] = time.sleep,
        reloj: Callable[[], float] = time.perf_counter,
    ) -> None:
        if fps <= 0:
            raise ValueError("fps debe ser positivo")
        self.manifiesto = manifiesto
        self.filas = leer_manifiesto(manifiesto, raiz)
        self.source_id = source_id
        self.fps = fps
        self._dormir = dormir
        self._reloj = reloj

    def __len__(self) -> int:
        return len(self.filas)

    def frames(self) -> Iterator[Frame]:
        intervalo = 1.0 / self.fps
        inicio = self._reloj()
        for i, (ruta, rel, sha) in enumerate(self.filas):
            objetivo = inicio + i * intervalo
            espera = objetivo - self._reloj()
            if espera > 0:
                self._dormir(espera)
            yield Frame(
                indice=i,
                frame_id=f"{self.source_id}-f{i:05d}",
                source_id=self.source_id,
                ruta=ruta,
                ruta_rel=rel,
                sha256_declarado=sha,
                t_captura=ahora_iso(),
                t_captura_mono=self._reloj(),
            )
