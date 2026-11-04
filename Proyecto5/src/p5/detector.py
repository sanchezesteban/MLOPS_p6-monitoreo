"""Interfaz de detector para el recorrido integral (P5-14).

El contrato solo pide detecciones por cuadro; `p5.recorrer` arma el `PerceptionEvent`
completo. El detector real de P5-04 (#56) debe implementar esta misma interfaz. Mientras
tanto, `DetectorSimulado` permite ejercitar C1-C5/C7 y la inyeccion de fallos sin esperar
a Edith: lee un guion de detecciones, nunca las anotaciones COCO.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import yaml

from p5.contrato import Detection

HASH_CERO = "0" * 64


@dataclass(frozen=True)
class Frame:
    """Un cuadro del manifiesto, antes de pasar por el detector."""

    sequence_id: str
    frame_id: str
    t_capture_ms: float
    image_path: str
    image_width: int
    image_height: int
    image_sha256: str
    status: str = "ok"
    error_msg: str | None = None
    t_capture_origen_ms: float | None = None
    session_id: str | None = None


class Detector(Protocol):
    """Lo unico que necesita `p5.recorrer` de un detector."""

    nombre: str
    model_sha256: str
    synthetic: bool

    def detectar(self, frame: Frame) -> list[Detection]: ...


class DetectorSimulado:
    """Detector de guion: devuelve las cajas escritas para cada `frame_id`.

    No abre imagenes ni anotaciones. El guion es datos de simulacion (YAML) y vive en
    `datos/simulacion/`, no en el COCO de P5-06. Cuando llegue el detector real, se
    reemplaza esta clase sin cambiar `p5.recorrer`.
    """

    nombre = "simulado"
    model_sha256 = HASH_CERO
    synthetic = True

    def __init__(self, guion: dict[str, list[dict[str, Any]]] | None = None) -> None:
        self._guion = guion or {}

    @classmethod
    def desde_yaml(cls, ruta: str | Path) -> DetectorSimulado:
        datos = yaml.safe_load(Path(ruta).read_text(encoding="utf-8"))
        if datos is None:
            datos = {}
        if not isinstance(datos, dict):
            raise ValueError(f"{ruta}: el guion debe ser un mapa frame_id -> detecciones")
        if isinstance(datos.get("frames"), dict):
            datos = datos["frames"]
        guion: dict[str, list[dict[str, Any]]] = {}
        for frame_id, detecciones in datos.items():
            if not isinstance(frame_id, str) or not isinstance(detecciones, list):
                raise ValueError(f"{ruta}: {frame_id!r} debe mapear a una lista")
            if not all(isinstance(d, dict) for d in detecciones):
                raise ValueError(f"{ruta}: las detecciones de {frame_id} deben ser mapas")
            guion[frame_id] = detecciones
        return cls(guion)

    def detectar(self, frame: Frame) -> list[Detection]:
        return [
            Detection(
                class_name=str(d["class_name"]),
                class_id=int(d["class_id"]),
                confidence=float(d["confidence"]),
                bbox=tuple(float(v) for v in d["bbox"]),
            )
            for d in self._guion.get(frame.frame_id, [])
        ]
