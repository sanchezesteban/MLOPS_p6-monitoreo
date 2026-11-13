"""Inferencia real con el detector YOLOX-Nano del Proyecto 5 (reutilizado).

Se reutilizan de `Proyecto5/src/p5/detector_onnx.py`: carga de configuracion, verificacion
del SHA-256 de los pesos contra el descriptor, lectura de imagen, letterbox y decodificacion
con NMS. Lo propio de P6 es medir por separado cada etapa (lectura, preprocesamiento,
`session.run` y posprocesamiento), necesario para la metrica de G1 (tiempo de inferencia).
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from pathlib import Path

from p6 import RAIZ_REPO

_P5_SRC = RAIZ_REPO / "Proyecto5" / "src"
if str(_P5_SRC) not in sys.path:
    sys.path.insert(0, str(_P5_SRC))

from p5 import detector_onnx as p5det  # noqa: E402
from p5.contrato import Detection  # noqa: E402

DetectorError = p5det.DetectorError


@dataclass(frozen=True)
class ResultadoInferencia:
    ancho: int
    alto: int
    detecciones: list[Detection]
    lectura_ms: float
    pre_ms: float
    inferencia_ms: float  # solo session.run (metrica base G1)
    post_ms: float


class Detector:
    nombre = p5det.NOMBRE
    synthetic = False

    def __init__(self, config_yaml: Path) -> None:
        self.config = p5det.cargar_config(config_yaml)
        self._det = p5det.DetectorONNX.desde_config(self.config)
        self.model_sha256 = self._det.model_sha256
        self.detector_config_sha256 = self.config.config_sha256
        self.clases = self._det.clases
        self.modelo_archivo = self.config.modelo.name

    def inferir(self, ruta: Path) -> ResultadoInferencia:
        t0 = time.perf_counter()
        rgb = p5det.leer_imagen(ruta)  # DetectorError si no se puede decodificar
        t1 = time.perf_counter()
        alto, ancho = rgb.shape[:2]
        tensor, r = p5det.letterbox(rgb, self.config.tamano_entrada, self.config.relleno)
        t2 = time.perf_counter()
        try:
            salida = self._det._sesion.run(None, {self._det._entrada: tensor})[0]
        except Exception as exc:  # cualquier fallo del runtime es fallo del detector
            raise DetectorError(f"onnxruntime: {type(exc).__name__}: {exc}") from exc
        t3 = time.perf_counter()
        dets = p5det.decodificar(salida, r, ancho, alto, self.config, self.clases)
        t4 = time.perf_counter()
        ms = 1000.0
        return ResultadoInferencia(
            ancho, alto, dets, (t1 - t0) * ms, (t2 - t1) * ms, (t3 - t2) * ms, (t4 - t3) * ms
        )
