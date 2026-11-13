import pytest

from p6 import metricas, politica


@pytest.mark.parametrize(
    ("score", "zona"),
    [
        (0.80, "aceptada"),
        (0.50, "aceptada"),
        (0.4999, "duda"),
        (0.25, "duda"),
        (0.2499, "baja"),
        (0.0, "baja"),
    ],
)
def test_zonas_con_igualdades(score, zona):
    # igualdad con el inferior -> duda; con el superior -> aceptada
    assert politica.zona(score, 0.25, 0.50) == zona


def test_frame_sin_detecciones_no_recibe_score_cero():
    assert politica.clasificar_frame([], 0.25, 0.5) == ("sin_detecciones", None, None)


def test_frame_usa_maximo_de_candidatas():
    assert politica.clasificar_frame([0.1, 0.3, 0.2], 0.25, 0.5) == ("ok", 0.3, "duda")


def test_percentil_rango_mas_cercano():
    v = [5.0, 1.0, 3.0, 2.0, 4.0]
    assert metricas.percentil_rango(v, 0.5) == 3.0
    assert metricas.percentil_rango(v, 0.95) == 5.0
    assert metricas.percentil_rango([], 0.5) is None


def test_g4_excluye_estados_aparte_y_sin_datos_es_none():
    ev = [
        {"estado": "ok", "zona": "baja"},
        {"estado": "ok", "zona": "aceptada"},
        {"estado": "sin_detecciones", "zona": None},
        {"estado": "error", "zona": None},
    ]
    assert metricas.g4_baja(ev) == {"puntuados": 2, "bajos": 1, "proporcion": 0.5}
    assert metricas.g4_baja(ev[2:])["proporcion"] is None


def test_g2_sin_frames_suficientes_es_none():
    assert metricas.g2_fps_procesamiento([])["fps"] is None


def test_g7_cuenta_abiertas_en_la_ventana():
    al = [
        {"abierta_ventana": 0, "resuelta_ventana": 2},
        {"abierta_ventana": 1, "resuelta_ventana": None},
    ]
    assert [metricas.g7_activas(al, w) for w in range(4)] == [1, 2, 1, 1]
