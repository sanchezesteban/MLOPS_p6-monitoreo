"""Detector real con los pesos de `modelo/` (P5-04): varios, negativa, ilegible, renombrada.

Se omiten si los pesos no estan descargados (`python scripts/descargar_modelo.py --destino
modelo/`); el CI los descarga antes de correr pytest.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from PIL import Image

from p5.contrato import validar_evento, validar_run_header
from p5.detectar import main
from p5.detector_onnx import DetectorONNX, cargar_config

RAIZ = Path(__file__).resolve().parents[1]
CONFIG = RAIZ / "config" / "detector.yaml"
GATO = Path(__file__).resolve().parent / "datos" / "gato.jpg"

pytestmark = pytest.mark.skipif(
    not (RAIZ / "modelo" / "yolox_nano.onnx").is_file(), reason="pesos no descargados"
)


def _argv(imagenes: Path, salida: Path) -> list[str]:
    return ["--imagenes", str(imagenes), "--config", str(CONFIG), "--salida", str(salida)]


@pytest.fixture(scope="module")
def detector():
    return DetectorONNX.desde_config(cargar_config(CONFIG))


@pytest.fixture
def imagenes(tmp_path):
    carpeta = tmp_path / "imagenes"
    carpeta.mkdir()
    shutil.copy(GATO, carpeta / "a_gato.jpg")
    gato = Image.open(GATO).convert("RGB")
    lienzo = Image.new("RGB", (640, 240), (200, 200, 200))
    lienzo.paste(gato, (0, 60))
    lienzo.paste(gato, (400, 60))
    lienzo.save(carpeta / "b_varios.png")
    Image.new("RGB", (400, 296), (90, 120, 150)).save(carpeta / "c_negativa.png")
    (carpeta / "d_ilegible.jpg").write_bytes(b"no es una imagen")
    return carpeta


def test_pesos_cargados_son_los_del_descriptor(detector):
    assert detector.model_sha256 == (
        "c789161ed43c8269fcd4e67c67eeeb4e80c622da2eb296a20bc6007bd18a0b7d"
    )


def test_gato_real_en_pixeles_del_cuadro(detector):
    ancho, alto, dets = detector.detectar_imagen(GATO)
    assert (ancho, alto) == (240, 112)
    gatos = [d for d in dets if d.class_name == "cat"]
    assert gatos and gatos[0].confidence >= 0.5
    x1, y1, x2, y2 = gatos[0].bbox
    assert 0 <= x1 < x2 <= ancho and 0 <= y1 < y2 <= alto
    assert (x2 - x1) * (y2 - y1) > 0.5 * ancho * alto  # el gato ocupa casi todo el recorte


def test_varios_objetos_a_izquierda_y_derecha(detector, imagenes):
    _, _, dets = detector.detectar_imagen(imagenes / "b_varios.png")
    gatos = sorted((d for d in dets if d.class_name == "cat"), key=lambda d: d.bbox[0])
    assert len(gatos) >= 2
    assert gatos[0].bbox[2] < 320 < gatos[-1].bbox[0]


def test_negativa_sin_detecciones(detector, imagenes):
    assert detector.detectar_imagen(imagenes / "c_negativa.png")[2] == []


def test_renombrar_no_cambia_el_resultado(detector, tmp_path):
    copia = tmp_path / "otro_nombre_person_dog.bmp.jpg"
    shutil.copy(GATO, copia)
    assert detector.detectar_imagen(copia) == detector.detectar_imagen(GATO)


def test_cli_escribe_eventos_del_contrato(imagenes, tmp_path, capsys):
    salida = tmp_path / "salida"
    assert main(_argv(imagenes, salida)) == 0
    validar_run_header(json.loads((salida / "run.json").read_text(encoding="utf-8")))
    lineas = (salida / "detecciones.jsonl").read_text(encoding="utf-8").splitlines()
    eventos = {e["image_path"]: e for e in map(json.loads, lineas)}
    for evento in eventos.values():
        validar_evento(evento)
    assert eventos["c_negativa.png"]["status"] == "ok"
    assert eventos["c_negativa.png"]["detections"] == []
    assert eventos["d_ilegible.jpg"]["status"] == "error"
    assert "ilegible" in eventos["d_ilegible.jpg"]["error_msg"]
    assert len(eventos["b_varios.png"]["detections"]) >= 2
    assert "1 con error" in capsys.readouterr().out


def test_cli_no_escribe_sobre_una_carpeta_con_archivos(imagenes, tmp_path):
    salida = tmp_path / "salida"
    salida.mkdir()
    (salida / "previo.txt").write_text("x")
    assert main(_argv(imagenes, salida)) == 2


def test_cli_con_pesos_alterados_sale_con_2(imagenes, tmp_path):
    falso = tmp_path / "falso.onnx"
    falso.write_bytes(b"x")
    assert main([*_argv(imagenes, tmp_path / "s"), "--modelo", str(falso)]) == 2
