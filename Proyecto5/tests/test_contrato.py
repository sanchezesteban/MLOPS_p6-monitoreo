"""Contrato v1: los ejemplos de `config/ejemplos/` son validos y lo fuera de contrato se rechaza."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from p5.contrato import (
    ContratoError,
    en_riesgo,
    esta_vencido,
    validar_comando,
    validar_evento,
    validar_run_header,
    validar_secuencia,
    zonas_ocupadas,
)

EJEMPLOS = Path(__file__).resolve().parents[1] / "config" / "ejemplos"


def ejemplo(nombre: str) -> dict:
    return json.loads((EJEMPLOS / f"{nombre}.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("nombre", ["ok", "vacio", "error", "stale"])
def test_ejemplos_de_evento_son_validos(nombre):
    ev = validar_evento(ejemplo(nombre))
    assert ev.frame_id == ejemplo(nombre)["frame_id"]


@pytest.mark.parametrize("nombre", ["comando_forward", "comando_stop"])
def test_ejemplos_de_comando_son_validos(nombre):
    validar_comando(ejemplo(nombre))


def test_ejemplo_de_run_header_es_valido():
    assert validar_run_header(ejemplo("run_header")).virtual_mode is True


def test_campos_de_procedencia_y_replay_son_opcionales():
    evento = validar_evento(ejemplo("ok"))
    header = validar_run_header(ejemplo("run_header"))

    assert evento.t_capture_origen_ms == 700
    assert header.replay_dt_ms == 100

    sin_replay = {k: v for k, v in ejemplo("run_header").items() if k != "replay_dt_ms"}
    assert validar_run_header(sin_replay).replay_dt_ms is None


def test_replay_dt_no_positivo_se_rechaza():
    data = {**ejemplo("run_header"), "replay_dt_ms": 0}
    with pytest.raises(ContratoError):
        validar_run_header(data)


def test_vacio_es_cuadro_valido_sin_objetos_y_error_no_es_via_libre():
    vacio, error = validar_evento(ejemplo("vacio")), validar_evento(ejemplo("error"))
    assert vacio.status == "ok" and vacio.detections == ()
    assert error.status == "error" and error.detections == ()


def _evento_mal(cambio):
    data = copy.deepcopy(ejemplo("ok"))
    cambio(data)
    return data


EVENTOS_INVALIDOS = {
    "confianza_mayor_a_1": lambda d: d["detections"][0].update(confidence=1.5),
    "confianza_nan": lambda d: d["detections"][0].update(confidence=float("nan")),
    "bbox_invertida": lambda d: d["detections"][0].update(bbox=[390.0, 120.0, 250.0, 470.0]),
    "bbox_fuera_del_cuadro": lambda d: d["detections"][0].update(bbox=[250.0, 120.0, 700.0, 470.0]),
    "bbox_de_3_valores": lambda d: d["detections"][0].update(bbox=[1.0, 2.0, 3.0]),
    "status_desconocido": lambda d: d.update(status="clear"),
    "error_sin_mensaje": lambda d: d.update(status="error", detections=[]),
    "error_con_detecciones": lambda d: d.update(status="error", error_msg="timeout"),
    "ok_con_mensaje_de_error": lambda d: d.update(error_msg="algo"),
    "ok_sin_dimensiones": lambda d: d.update(image_width=None),
    "hash_mal_formado": lambda d: d.update(model_sha256="abc"),
    "campo_desconocido": lambda d: d.update(etiqueta_real="person"),
    "falta_detections": lambda d: d.pop("detections"),
    "synthetic_como_texto": lambda d: d.update(synthetic="false"),
}


@pytest.mark.parametrize("caso", sorted(EVENTOS_INVALIDOS))
def test_evento_fuera_de_contrato_se_rechaza(caso):
    with pytest.raises(ContratoError):
        validar_evento(_evento_mal(EVENTOS_INVALIDOS[caso]))


def _comando_mal(base, cambio):
    data = copy.deepcopy(ejemplo(base))
    cambio(data)
    return data


COMANDOS_INVALIDOS = {
    "stop_con_velocidad": ("comando_stop", lambda d: d.update(speed=0.3)),
    "stop_con_giro": ("comando_stop", lambda d: d.update(steering=-0.5)),
    "stop_con_vencimiento": ("comando_stop", lambda d: d.update(valid_until_ms=1000.0)),
    "referencia_a_otro_cuadro": (
        "comando_forward",
        lambda d: d.update(detections_ref="seq01_f0009"),
    ),
    "forward_sin_velocidad": ("comando_forward", lambda d: d.update(speed=0.0)),
    "forward_sin_vencimiento": ("comando_forward", lambda d: d.update(valid_until_ms=None)),
    "forward_ya_vencido": ("comando_forward", lambda d: d.update(valid_until_ms=800.0)),
    "forward_con_giro": ("comando_forward", lambda d: d.update(steering=0.2)),
    "izquierda_con_signo_derecho": (
        "comando_forward",
        lambda d: d.update(action="STEER_LEFT", steering=0.5),
    ),
    "derecha_con_signo_izquierdo": (
        "comando_forward",
        lambda d: d.update(action="STEER_RIGHT", steering=-0.5),
    ),
    "velocidad_fuera_de_rango": ("comando_forward", lambda d: d.update(speed=1.5)),
    "sin_cuadro_ni_evento": ("comando_stop", lambda d: d.update(frame_id=None, event=None)),
    "comando_antes_de_decidir": ("comando_stop", lambda d: d.update(t_command_ms=700.0)),
    "accion_desconocida": ("comando_stop", lambda d: d.update(action="BRAKE")),
    "velocidad_infinita": ("comando_forward", lambda d: d.update(speed=float("inf"))),
}


@pytest.mark.parametrize("caso", sorted(COMANDOS_INVALIDOS))
def test_comando_fuera_de_contrato_se_rechaza(caso):
    base, cambio = COMANDOS_INVALIDOS[caso]
    with pytest.raises(ContratoError):
        validar_comando(_comando_mal(base, cambio))


def test_stop_por_watchdog_sin_cuadro_es_valido():
    data = ejemplo("comando_stop")
    data.update(frame_id=None, event="watchdog", detections_ref=None, reason="sin_cuadros")
    assert validar_comando(data).event == "watchdog"


def test_error_reporta_todos_los_problemas():
    data = _evento_mal(lambda d: d.update(status="error", error_msg=None))
    with pytest.raises(ContratoError) as exc:
        validar_evento(data)
    assert len(exc.value.errores) == 2


def test_secuencia_detecta_ids_repetidos_y_tiempo_no_creciente():
    ok, vacio = validar_evento(ejemplo("ok")), validar_evento(ejemplo("vacio"))
    assert validar_secuencia([ok, vacio]) == []
    assert len(validar_secuencia([vacio, ok])) == 1
    assert any("repetido" in e for e in validar_secuencia([ok, ok]))


def test_secuencia_rechaza_otro_run_id_y_frame_id_sin_prefijo():
    ok = validar_evento(ejemplo("ok"))
    otro_run = validar_evento({**ejemplo("vacio"), "run_id": "run-otro"})
    sin_prefijo = validar_evento({**ejemplo("vacio"), "frame_id": "f0008"})
    assert any("run_id" in e for e in validar_secuencia([ok, otro_run]))
    assert any("no empieza con seq01_" in e for e in validar_secuencia([ok, sin_prefijo]))


def test_secuencia_exige_tiempo_creciente_en_todo_el_run():
    a = validar_evento(ejemplo("ok"))
    b = validar_evento(
        {**ejemplo("vacio"), "sequence_id": "seq02", "frame_id": "seq02_f0001", "t_capture_ms": 0}
    )
    assert any("no supera" in e for e in validar_secuencia([a, b]))


def test_stale_con_detecciones_se_rechaza():
    data = {**ejemplo("stale"), "detections": copy.deepcopy(ejemplo("ok")["detections"])}
    with pytest.raises(ContratoError, match="status=stale"):
        validar_evento(data)


def test_vencimiento():
    assert not esta_vencido(t_capture_ms=700, t_now_ms=1000, max_frame_age_ms=300)
    assert esta_vencido(t_capture_ms=700, t_now_ms=1001, max_frame_age_ms=300)


def test_reloj_inconsistente_cuenta_como_vencido():
    assert esta_vencido(t_capture_ms=700, t_now_ms=699, max_frame_age_ms=300)
    assert not esta_vencido(t_capture_ms=700, t_now_ms=700, max_frame_age_ms=300)


@pytest.mark.parametrize(
    ("bbox", "zonas"),
    [
        ((250, 120, 390, 470), {"centro"}),
        ((20, 260, 140, 300), {"izquierda"}),
        ((500, 0, 640, 100), {"derecha"}),
        ((150, 0, 260, 100), {"izquierda", "centro"}),
        ((0, 0, 640, 100), {"izquierda", "centro", "derecha"}),
        ((0, 0, 213, 100), {"izquierda"}),
        ((427, 0, 640, 100), {"derecha"}),
    ],
)
def test_zonas_ocupadas_en_cuadro_de_640(bbox, zonas):
    assert zonas_ocupadas(bbox, 640) == zonas


def test_zona_de_riesgo_por_borde_inferior():
    assert en_riesgo((0, 0, 10, 240), 480)
    assert not en_riesgo((0, 0, 10, 239), 480)
