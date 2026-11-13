"""Inferencia real con YOLOX-Nano sobre una captura del carrito (se omite sin el modelo)."""

from pathlib import Path

import pytest

from p6 import RAIZ_REPO
from p6.config import cargar

CFG = Path(__file__).resolve().parents[1] / "config" / "monitoreo.yaml"
MODELO = RAIZ_REPO / "Proyecto5" / "modelo" / "yolox_nano.onnx"
IMG = RAIZ_REPO / "Proyecto5/datos/evaluacion/S5"


@pytest.mark.skipif(not MODELO.is_file(), reason="modelo no descargado")
def test_inferencia_real_atribuible():
    from p6.detector import Detector

    det = Detector(cargar(CFG).detector_config)
    assert det.model_sha256.startswith("c789161e") and det.synthetic is False
    r = det.inferir(sorted(IMG.glob("*.jpg"))[0])
    assert (r.ancho, r.alto) == (400, 296)
    assert r.inferencia_ms > 0
    assert all(d.confidence >= 0.05 for d in r.detecciones)
