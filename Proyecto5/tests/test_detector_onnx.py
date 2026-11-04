"""Runtime del detector (P5-04) sin pesos: decodificacion, NMS, fallos y config con sesion falsa."""

from __future__ import annotations

import math
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import yaml

from p5.detector_onnx import (
    DetectorError,
    DetectorONNX,
    ModeloInvalidoError,
    cargar_config,
    decodificar,
    letterbox,
    nms,
)

CONFIG = Path(__file__).resolve().parents[1] / "config" / "detector.yaml"
POLITICA = CONFIG.with_name("politica.yaml")
GATO = Path(__file__).resolve().parent / "datos" / "gato.jpg"
CLASES = [f"c{i}" for i in range(80)]
CLASES[0], CLASES[15], CLASES[16] = "person", "cat", "dog"
ANCLAS = 52 * 52 + 26 * 26 + 13 * 13


def salida_con(*objetos: tuple[int, int, float, float, int, float]) -> np.ndarray:
    """Salida cruda de YOLOX con objetos en la rejilla de stride 8: (gx, gy, w, h, clase, score)."""
    o = np.zeros((1, ANCLAS, 85), dtype=np.float32)
    for gx, gy, w, h, clase, score in objetos:
        fila = o[0, gy * 52 + gx]
        fila[0:2] = 0.5
        fila[2:4] = (math.log(w / 8), math.log(h / 8))
        fila[4] = 1.0
        fila[5 + clase] = score
    return o


@pytest.fixture
def config():
    return cargar_config(CONFIG)


class SesionFalsa:
    def __init__(self, salida=None, error=None):
        self.salida, self.error, self.entradas = salida, error, []

    def run(self, _nombres, feed):
        self.entradas.append(feed)
        if self.error:
            raise self.error
        return [self.salida]


def test_config_del_repo_es_valida_y_no_filtra_lo_que_la_politica_usa(config):
    politica = yaml.safe_load(POLITICA.read_text(encoding="utf-8"))
    assert config.umbral_confianza <= politica["confianza"]["minimo_incierto"]
    assert config.tamano_entrada == 416
    assert len(config.config_sha256) == 64


@pytest.mark.parametrize(
    ("cambio", "mensaje"),
    [
        (lambda d: d["posprocesamiento"].update(umbral_confianza=1.5), "umbral_confianza"),
        (lambda d: d["posprocesamiento"].update(nms_iou=0), "nms_iou"),
        (lambda d: d["posprocesamiento"].update(max_detecciones=True), "max_detecciones"),
        (lambda d: d["preprocesamiento"].update(tamano_entrada=400), "multiplo de 32"),
        (lambda d: d["preprocesamiento"].update(relleno=300), "relleno"),
        (lambda d: d.update(extra=1), "claves desconocidas"),
        (lambda d: d["posprocesamiento"].update(umbral="0.3"), "claves desconocidas"),
        (lambda d: d.update(version=2), "version"),
    ],
)
def test_config_invalida_se_rechaza(tmp_path, cambio, mensaje):
    data = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    cambio(data)
    ruta = tmp_path / "detector.yaml"
    ruta.write_text(yaml.safe_dump(data), encoding="utf-8")
    with pytest.raises(ModeloInvalidoError, match=mensaje):
        cargar_config(ruta)


def test_modelo_con_otro_sha256_se_rechaza(tmp_path, config):
    falso = tmp_path / "modelo.onnx"
    falso.write_bytes(b"no son los pesos")
    with pytest.raises(ModeloInvalidoError, match="SHA-256"):
        DetectorONNX.desde_config(replace(config, modelo=falso))


def test_modelo_faltante_indica_como_descargarlo(tmp_path, config):
    with pytest.raises(ModeloInvalidoError, match="descargar_modelo"):
        DetectorONNX.desde_config(replace(config, modelo=tmp_path / "no.onnx"))


def test_letterbox_conserva_proporcion_y_rellena_abajo_a_la_derecha():
    rgb = np.zeros((296, 400, 3), dtype=np.uint8)
    rgb[..., 0] = 255  # rojo puro en RGB
    tensor, r = letterbox(rgb, 416, 114)
    assert tensor.shape == (1, 3, 416, 416) and tensor.dtype == np.float32
    assert r == pytest.approx(1.04)
    assert tensor[0, 2, 0, 0] == 255 and tensor[0, 0, 0, 0] == 0  # canal 2 = R (BGR)
    assert (tensor[0, :, 400:, :] == 114).all()  # 296 * 1.04 = 307 filas de imagen


def test_decodifica_caja_en_pixeles_del_cuadro_original(config):
    # centro de la celda (10, 20) en stride 8 = (84, 164) en el tensor; caja 40x80
    salida = salida_con((10, 20, 40, 80, 15, 0.9))
    [d] = decodificar(salida, 0.5, 832, 832, config, CLASES)
    assert (d.class_name, d.class_id) == ("cat", 15)
    assert d.confidence == pytest.approx(0.9)
    assert d.bbox == pytest.approx((128.0, 248.0, 208.0, 408.0))  # (84±20, 164±40) / 0.5


def test_varios_objetos_y_nms_por_clase(config):
    salida = salida_con(
        (10, 20, 40, 80, 0, 0.9),
        (11, 20, 40, 80, 0, 0.6),  # casi la misma caja y clase: la suprime el NMS
        (11, 20, 40, 80, 16, 0.7),  # misma caja, otra clase: se queda
        (40, 40, 30, 30, 15, 0.5),
    )
    dets = decodificar(salida, 1.0, 416, 416, config, CLASES)
    assert [(d.class_name, round(d.confidence, 2)) for d in dets] == [
        ("person", 0.9),
        ("dog", 0.7),
        ("cat", 0.5),
    ]


def test_bajo_umbral_da_lista_vacia(config):
    assert decodificar(salida_con((10, 20, 40, 80, 0, 0.29)), 1.0, 416, 416, config, CLASES) == []
    assert decodificar(salida_con(), 1.0, 416, 416, config, CLASES) == []


def test_cajas_se_recortan_al_cuadro(config):
    [d] = decodificar(salida_con((0, 0, 100, 100, 0, 0.9)), 1.0, 300, 200, config, CLASES)
    assert d.bbox[0] == 0 and d.bbox[1] == 0
    [d] = decodificar(salida_con((51, 51, 100, 100, 0, 0.9)), 1.0, 416, 416, config, CLASES)
    assert d.bbox[2] == 416 and d.bbox[3] == 416


@pytest.mark.parametrize("valor", [float("nan"), float("inf")])
def test_salida_no_finita_es_fallo(config, valor):
    salida = salida_con((10, 20, 40, 80, 0, 0.9))
    salida[0, 5, 7] = valor
    with pytest.raises(DetectorError, match="no finita"):
        decodificar(salida, 1.0, 416, 416, config, CLASES)


def test_caja_que_desborda_al_decodificar_es_fallo(config):
    salida = salida_con((10, 20, 40, 80, 0, 0.9))
    salida[0, 20 * 52 + 10, 2] = 1000.0  # exp(1000) = inf
    with pytest.raises(DetectorError, match="no finita"):
        decodificar(salida, 1.0, 416, 416, config, CLASES)


def test_salida_con_forma_inesperada_es_fallo(config):
    with pytest.raises(DetectorError, match="malformada"):
        decodificar(np.zeros((1, 10, 85), np.float32), 1.0, 416, 416, config, CLASES)


def test_nms_conserva_cajas_separadas():
    cajas = np.array([[0, 0, 10, 10], [1, 1, 11, 11], [50, 50, 60, 60]], dtype=float)
    assert nms(cajas, np.array([0.9, 0.8, 0.7]), 0.45) == [0, 2]


def _detector(config, sesion):
    return DetectorONNX(sesion, config, CLASES, "a" * 64)


def test_detectar_pasa_el_cuadro_completo_y_regresa_cajas(config):
    sesion = SesionFalsa(salida_con((10, 20, 40, 80, 15, 0.9)))
    ancho, alto, [d] = _detector(config, sesion).detectar_imagen(GATO)
    assert (ancho, alto) == (240, 112)
    assert sesion.entradas[0]["images"].shape == (1, 3, 416, 416)
    r = 416 / 240
    assert d.bbox == pytest.approx(((84 - 20) / r, (164 - 40) / r, (84 + 20) / r, 112), abs=0.01)


def test_imagen_ilegible_es_fallo(tmp_path, config):
    rota = tmp_path / "rota.jpg"
    rota.write_bytes(b"no es una imagen")
    truncada = tmp_path / "truncada.jpg"
    truncada.write_bytes(GATO.read_bytes()[:500])
    detector = _detector(config, SesionFalsa(salida_con()))
    for ruta in (rota, truncada, tmp_path / "no-existe.jpg"):
        with pytest.raises(DetectorError, match="ilegible"):
            detector.detectar_imagen(ruta)


def test_excepcion_del_runtime_es_fallo_del_detector(config):
    detector = _detector(config, SesionFalsa(error=RuntimeError("timeout")))
    with pytest.raises(DetectorError, match="timeout"):
        detector.detectar_imagen(GATO)


def test_interfaz_del_recorrido_y_dimensiones_del_manifiesto(config):
    detector = _detector(config, SesionFalsa(salida_con()))
    assert detector.synthetic is False and detector.nombre == "yolox_nano"
    frame = SimpleNamespace(image_path=str(GATO), image_width=240, image_height=112)
    assert detector.detectar(frame) == []
    with pytest.raises(DetectorError, match="manifiesto"):
        detector.detectar(SimpleNamespace(image_path=str(GATO), image_width=640, image_height=480))
