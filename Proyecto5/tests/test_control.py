"""P5-11: `AdaptadorVirtual` registra en JSONL sin mover motores."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from p5.contrato import validar_comando
from p5.control import AdaptadorVirtual, construir_controlador

EJEMPLOS = Path(__file__).resolve().parents[1] / "config" / "ejemplos"


def ejemplo(nombre: str) -> dict:
    return json.loads((EJEMPLOS / f"{nombre}.json").read_text(encoding="utf-8"))


def leer_lineas(log_path: Path) -> list[dict]:
    return [json.loads(linea) for linea in log_path.read_text(encoding="utf-8").splitlines()]


def _reloj_fijo(valor: float):
    return lambda: valor


def test_comando_valido_se_registra_con_received_true(tmp_path):
    log_path = tmp_path / "comandos.jsonl"
    adaptador = AdaptadorVirtual(log_path, run_id="run-ejemplo-001")

    adaptador.enviar(ejemplo("comando_forward"))
    adaptador.cerrar()

    (linea,) = leer_lineas(log_path)
    assert linea["received"] is True
    assert linea["action"] == "FORWARD"
    assert linea["speed"] == 0.4
    assert linea["steering"] == 0.0
    assert linea["valid_until_ms"] == 1013.0
    validar_comando(linea)  # sigue siendo un comando valido del contrato


def test_comando_stop_tambien_se_registra(tmp_path):
    log_path = tmp_path / "comandos.jsonl"
    adaptador = AdaptadorVirtual(log_path, run_id="run-ejemplo-001")

    adaptador.enviar(ejemplo("comando_stop"))
    adaptador.cerrar()

    (linea,) = leer_lineas(log_path)
    assert linea["action"] == "STOP" and linea["received"] is True


def test_varios_comandos_se_acumulan_sin_pisarse(tmp_path):
    log_path = tmp_path / "comandos.jsonl"
    adaptador = AdaptadorVirtual(log_path, run_id="run-ejemplo-001")

    adaptador.enviar(ejemplo("comando_forward"))
    adaptador.enviar(ejemplo("comando_stop"))
    adaptador.cerrar()

    lineas = leer_lineas(log_path)
    assert [linea["action"] for linea in lineas] == ["FORWARD", "STOP"]


COMANDOS_INVALIDOS = {
    "velocidad_fuera_de_rango": lambda d: d.update(speed=1.5),
    "velocidad_no_finita": lambda d: d.update(speed=float("nan")),
    "direccion_fuera_de_rango": lambda d: d.update(steering=-2.0),
    "direccion_no_finita": lambda d: d.update(steering=float("inf")),
    "stop_con_velocidad": lambda d: d.update(action="STOP", speed=0.5, valid_until_ms=None),
    "run_id_de_otra_corrida": lambda d: d.update(run_id="run-otra-corrida"),
}


@pytest.mark.parametrize("caso", sorted(COMANDOS_INVALIDOS))
def test_comando_invalido_no_se_ejecuta_y_termina_en_stop(tmp_path, caso):
    log_path = tmp_path / "comandos.jsonl"
    adaptador = AdaptadorVirtual(log_path, run_id="run-ejemplo-001")
    base = copy.deepcopy(ejemplo("comando_forward"))
    COMANDOS_INVALIDOS[caso](base)

    adaptador.enviar(base)  # nunca lanza
    adaptador.cerrar()

    (linea,) = leer_lineas(log_path)
    assert linea["action"] == "STOP"
    assert linea["speed"] == 0.0 and linea["steering"] == 0.0
    assert linea["received"] is True
    assert linea["error"] is not None
    validar_comando(linea)  # el STOP de rechazo tambien es valido


def test_stop_directo_registra_razon_y_usa_el_reloj_inyectado(tmp_path):
    log_path = tmp_path / "comandos.jsonl"
    adaptador = AdaptadorVirtual(log_path, run_id="run-test", reloj=_reloj_fijo(4242.0))

    adaptador.stop("vencimiento")
    adaptador.cerrar()

    (linea,) = leer_lineas(log_path)
    assert linea["action"] == "STOP"
    assert linea["reason"] == "vencimiento"
    assert linea["t_decision_ms"] == 4242.0 and linea["t_command_ms"] == 4242.0
    assert linea["valid_until_ms"] is None
    validar_comando(linea)


def test_stop_despues_de_un_comando_arrastra_el_ultimo_estado(tmp_path):
    log_path = tmp_path / "comandos.jsonl"
    adaptador = AdaptadorVirtual(log_path, run_id="run-ejemplo-001")

    adaptador.enviar(ejemplo("comando_forward"))
    adaptador.stop("emergencia")
    adaptador.cerrar()

    _, stop = leer_lineas(log_path)
    assert stop["state_before"] == "ADVANCING"
    assert stop["state_after"] == "STOPPED"


def test_cerrar_es_idempotente(tmp_path):
    adaptador = AdaptadorVirtual(tmp_path / "comandos.jsonl", run_id="run-test")
    adaptador.cerrar()
    adaptador.cerrar()  # no debe lanzar


def test_construir_controlador_virtual_devuelve_adaptador_virtual(tmp_path):
    controlador = construir_controlador(
        "virtual", log_path=tmp_path / "comandos.jsonl", run_id="run-test"
    )
    assert isinstance(controlador, AdaptadorVirtual)
    controlador.cerrar()


def test_construir_controlador_real_no_esta_implementado_y_no_importa_nada(tmp_path):
    with pytest.raises(NotImplementedError):
        construir_controlador("real", log_path=tmp_path / "comandos.jsonl", run_id="run-test")


def test_construir_controlador_modo_desconocido_lanza_value_error(tmp_path):
    with pytest.raises(ValueError, match="modo desconocido"):
        construir_controlador("fantasia", log_path=tmp_path / "comandos.jsonl", run_id="run-test")
