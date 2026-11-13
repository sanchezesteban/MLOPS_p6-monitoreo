from pathlib import Path

import pytest

from p6.config import ConfigError, cargar
from p6.reglas import MotorReglas, Ventana

CFG = Path(__file__).resolve().parents[1] / "config" / "monitoreo.yaml"


def v(seq, puntuados, bajos):
    cfg = cargar(CFG)
    return Ventana(
        seq,
        f"w{seq}",
        10,
        puntuados,
        bajos,
        puntuados >= cfg.minimo_puntuados,
        (bajos / puntuados) if puntuados else None,
    )


def motor(pref=0.15):
    cfg = cargar(CFG)
    return MotorReglas(cfg, {"proporcion_baja": pref}, True)


def test_config_rechaza_umbrales_invertidos(tmp_path):
    texto = CFG.read_text().replace("umbral_inferior: 0.25", "umbral_inferior: 0.70")
    (tmp_path / "detector.yaml").write_text("")
    p = tmp_path / "m.yaml"
    p.write_text(texto)
    with pytest.raises(ConfigError):
        cargar(p)


def test_baja_confianza_no_evaluable_si_ventana_insuficiente():
    d = motor().evaluar(v(0, 3, 3))
    assert d[0].condicion is None


def test_baja_confianza_cumple_en_el_limite():
    assert motor().evaluar(v(0, 6, 3))[0].condicion is True
    assert motor().evaluar(v(0, 10, 4))[0].condicion is False


def test_cambio_sostenido_requiere_racha_y_las_insuficientes_no_reinician():
    m = motor(pref=0.15)
    res = [
        m.evaluar(x)[1].condicion
        for x in [v(0, 10, 5), v(1, 2, 2), v(2, 10, 5), v(3, 10, 5), v(4, 10, 1)]
    ]
    # 0.5-0.15 >= 0.25 excede; la ventana 1 es insuficiente (None) y conserva la racha
    assert res == [False, None, False, True, False]


def test_cambio_sostenido_sin_referencia_no_evaluable():
    m = MotorReglas(cargar(CFG), None, False)
    assert m.evaluar(v(0, 10, 9))[1].condicion is None


def test_evidencia_insuficiente_tras_tres_ventanas():
    m = motor()
    res = [m.evaluar(x)[2].condicion for x in [v(0, 1, 0), v(1, 0, 0), v(2, 5, 0), v(3, 9, 0)]]
    assert res == [False, False, True, False]
