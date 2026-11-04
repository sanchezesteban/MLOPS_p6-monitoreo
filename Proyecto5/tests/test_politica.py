"""Politica temporal: una prueba por regla y escenarios sinteticos C1-C7 (`synthetic=true`)."""

from __future__ import annotations

import ast
import copy
import json
from pathlib import Path

import pytest
import yaml

from p5.contrato import validar_comando, validar_evento
from p5.contrato import zonas_ocupadas as zonas_contrato
from p5.politica import (
    ConfigPoliticaError,
    Politica,
    cargar_config,
    validar_config,
    zonas_ocupadas,
)

RAIZ = Path(__file__).resolve().parents[1]
CONFIG = RAIZ / "config" / "politica.yaml"
W, H = 640, 480
HASH = "0" * 64

# Cajas sobre un cuadro de 640x480: tercios en x=213.3 y 426.7; riesgo si y2 >= 240.
CENTRO = [250.0, 120.0, 390.0, 470.0]
CENTRO_LEJOS = [280.0, 50.0, 360.0, 200.0]
IZQUIERDA = [20.0, 250.0, 180.0, 460.0]
DERECHA = [460.0, 250.0, 620.0, 460.0]
IZQ_Y_CENTRO = [100.0, 250.0, 300.0, 460.0]


@pytest.fixture
def cfg():
    return cargar_config(CONFIG)


@pytest.fixture
def pol(cfg):
    return Politica(cfg)


def _det(bbox, confidence=0.9, class_name="person"):
    return {"class_name": class_name, "class_id": 0, "confidence": confidence, "bbox": bbox}


_n = iter(range(10**6))


def evento(*detecciones, status="ok"):
    i = next(_n)
    data = {
        "schema_version": "1.0",
        "run_id": "run-test",
        "sequence_id": "seqT",
        "frame_id": f"seqT_f{i:05d}",
        "t_capture_ms": 100 * i,
        "image_path": f"cuadros/seqT/f{i:05d}.jpg",
        "image_sha256": HASH,
        "image_width": W,
        "image_height": H,
        "model_sha256": HASH,
        "config_sha256": HASH,
        "status": status,
        "error_msg": None if status == "ok" else f"falla de prueba ({status})",
        "synthetic": True,
        "detections": list(detecciones),
    }
    if status == "error":
        data.update(image_sha256=None, image_width=None, image_height=None)
    return validar_evento(data)


def liberar(pol, n=None):
    """Lleva la politica a AVANCE con cuadros despejados."""
    for _ in range(n or pol.cfg.cuadros_liberar):
        d = pol.decidir(evento())
    assert d.action == "FORWARD"
    return d


def como_comando(d):
    """La decision completada con tiempos de prueba debe ser un comando valido del contrato."""
    mueve = d.action != "STOP"
    return validar_comando(
        {
            "schema_version": "1.0",
            "run_id": "run-test",
            "frame_id": d.frame_id,
            "event": d.event,
            "detections_ref": d.detections_ref,
            "state_before": d.state_before,
            "state_after": d.state_after,
            "action": d.action,
            "reason": d.reason,
            "speed": d.speed,
            "steering": d.steering,
            "t_decision_ms": 0,
            "t_command_ms": 1,
            "valid_until_ms": 300 if mueve else None,
            "received": True,
            "error": None,
            "synthetic": d.synthetic,
        }
    )


# --- Configuracion ---------------------------------------------------------------------------


def test_config_del_repo_es_valida(cfg):
    assert "person" in cfg.clases_obstaculo
    assert 0 <= cfg.minimo_incierto < cfg.umbral <= 1


def _cfg_con(cambio):
    data = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    cambio(data)
    return data


CONFIGS_INVALIDAS = {
    "umbral_mayor_a_1": lambda d: d["confianza"].update(umbral=1.5),
    "umbral_cero": lambda d: d["confianza"].update(umbral=0),
    "minimo_incierto_sobre_umbral": lambda d: d["confianza"].update(minimo_incierto=0.8),
    "zonas_solapadas": lambda d: d["zonas"].update(limite_izquierda=0.7, limite_derecha=0.4),
    "zona_fuera_del_cuadro": lambda d: d["zonas"].update(limite_derecha=1.2),
    "riesgo_y_cero": lambda d: d["zonas"].update(riesgo_y=0),
    "cuadros_liberar_cero": lambda d: d["histeresis"].update(cuadros_liberar=0),
    "cuadros_liberar_decimal": lambda d: d["histeresis"].update(cuadros_liberar=2.5),
    "velocidad_cero": lambda d: d["comandos"].update(velocidad_crucero=0),
    "precaucion_sobre_crucero": lambda d: d["comandos"].update(velocidad_precaucion=0.9),
    "giro_mayor_a_1": lambda d: d["comandos"].update(giro_correccion=2),
    "numero_nan": lambda d: d["confianza"].update(umbral=float("nan")),
    "booleano_como_numero": lambda d: d["comandos"].update(giro_correccion=True),
    "texto_como_numero": lambda d: d["confianza"].update(umbral="0.5"),
    "clases_vacias": lambda d: d.update(clases_obstaculo=[]),
    "clases_repetidas": lambda d: d.update(clases_obstaculo=["person", "person"]),
    "clave_desconocida": lambda d: d.update(distancia_m=2),
    "clave_desconocida_en_seccion": lambda d: d["zonas"].update(ancho_m=1),
    "falta_seccion": lambda d: d.pop("histeresis"),
    "falta_clave": lambda d: d["comandos"].pop("giro_correccion"),
    "version_desconocida": lambda d: d.update(version=2),
}


@pytest.mark.parametrize("nombre", sorted(CONFIGS_INVALIDAS))
def test_config_invalida_se_rechaza_antes_de_decidir(nombre):
    with pytest.raises(ConfigPoliticaError):
        validar_config(_cfg_con(CONFIGS_INVALIDAS[nombre]))


def test_yaml_ilegible_es_config_invalida(tmp_path):
    ruta = tmp_path / "politica.yaml"
    ruta.write_text("confianza: [sin cerrar", encoding="utf-8")
    with pytest.raises(ConfigPoliticaError):
        cargar_config(ruta)
    with pytest.raises(ConfigPoliticaError):
        cargar_config(tmp_path / "no_existe.yaml")


@pytest.mark.parametrize(
    "bbox",
    [
        CENTRO,
        CENTRO_LEJOS,
        IZQUIERDA,
        DERECHA,
        IZQ_Y_CENTRO,
        [0.0, 0.0, 640.0, 480.0],
        [213.0, 0.0, 214.0, 10.0],
        [426.0, 0.0, 427.0, 10.0],
    ],
)
def test_zonas_por_defecto_coinciden_con_el_contrato(cfg, bbox):
    assert zonas_ocupadas(tuple(bbox), W, cfg) == zonas_contrato(tuple(bbox), W)


# --- Reglas ------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("status", "event", "razon"),
    [("error", "detector_error", "error_percepcion"), ("stale", "stale_frame", "cuadro_vencido")],
)
def test_error_o_vencido_es_stop_y_no_via_libre(pol, status, event, razon):
    liberar(pol)
    d = pol.decidir(evento(status=status))
    assert (d.action, d.speed, d.state_after, d.event, d.reason) == (
        "STOP",
        0.0,
        "FALLA",
        event,
        razon,
    )
    assert d.detections_ref is None
    como_comando(d)


def test_arranque_detenido_hasta_n_cuadros_libres(pol):
    n = pol.cfg.cuadros_liberar
    for _ in range(n - 1):
        d = pol.decidir(evento())
        assert (d.action, d.state_after, d.reason) == ("STOP", "INICIO", "esperando_liberacion")
    d = pol.decidir(evento())
    assert (d.action, d.state_after, d.speed) == ("FORWARD", "AVANCE", pol.cfg.velocidad_crucero)


def test_obstaculo_centro_en_riesgo_es_stop_inmediato(pol):
    liberar(pol)
    d = pol.decidir(evento(_det(CENTRO)))
    assert (d.action, d.speed, d.state_after, d.reason) == (
        "STOP",
        0.0,
        "BLOQUEADO",
        "obstaculo_centro_riesgo",
    )
    como_comando(d)


def test_caja_que_cruza_lateral_y_centro_bloquea_el_centro(pol):
    liberar(pol)
    assert pol.decidir(evento(_det(IZQ_Y_CENTRO))).action == "STOP"


def test_considera_todas_las_detecciones_no_solo_la_mas_confiable(pol):
    liberar(pol)
    d = pol.decidir(evento(_det(IZQUIERDA, 0.95), _det(CENTRO, 0.6)))
    assert d.action == "STOP"


def test_clase_no_relevante_se_ignora(pol):
    liberar(pol)
    d = pol.decidir(evento(_det(CENTRO, 0.99, class_name="traffic light")))
    assert (d.action, d.reason) == ("FORWARD", "via_libre")


def test_confianza_bajo_minimo_se_ignora(pol):
    liberar(pol)
    d = pol.decidir(evento(_det(CENTRO, pol.cfg.minimo_incierto - 0.01)))
    assert (d.action, d.reason) == ("FORWARD", "via_libre")


def test_obstaculo_incierto_en_centro_reduce_velocidad(pol):
    liberar(pol)
    d = pol.decidir(evento(_det(CENTRO, 0.4)))
    assert (d.action, d.state_after, d.reason) == (
        "FORWARD",
        "PRECAUCION",
        "obstaculo_incierto_centro",
    )
    assert d.speed == pol.cfg.velocidad_precaucion


def test_obstaculo_cierto_lejos_en_centro_reduce_velocidad(pol):
    liberar(pol)
    d = pol.decidir(evento(_det(CENTRO_LEJOS)))
    assert (d.action, d.state_after, d.reason) == (
        "FORWARD",
        "PRECAUCION",
        "obstaculo_centro_lejos",
    )


def test_obstaculo_izquierda_corrige_a_la_derecha(pol):
    liberar(pol)
    d = pol.decidir(evento(_det(IZQUIERDA)))
    assert (d.action, d.state_after, d.reason) == (
        "STEER_RIGHT",
        "CORRECCION",
        "obstaculo_izquierda",
    )
    assert d.steering > 0 and d.speed > 0
    como_comando(d)


def test_obstaculo_derecha_corrige_a_la_izquierda(pol):
    liberar(pol)
    d = pol.decidir(evento(_det(DERECHA)))
    assert (d.action, d.state_after, d.reason) == ("STEER_LEFT", "CORRECCION", "obstaculo_derecha")
    assert d.steering < 0 and d.speed > 0
    como_comando(d)


def test_no_corrige_hacia_zona_destino_con_obstaculo_incierto(pol):
    liberar(pol)
    d = pol.decidir(evento(_det(IZQUIERDA), _det(DERECHA, 0.4)))
    assert (d.action, d.steering, d.reason) == ("FORWARD", 0.0, "obstaculos_laterales_centro_libre")


@pytest.mark.parametrize("bbox", [IZQUIERDA, DERECHA], ids=["izquierda", "derecha"])
def test_obstaculo_incierto_lateral_reduce_velocidad_sin_girar(pol, bbox):
    liberar(pol)
    d = pol.decidir(evento(_det(bbox, 0.4)))
    assert (d.action, d.state_after, d.reason) == (
        "FORWARD",
        "PRECAUCION",
        "obstaculo_incierto_lateral",
    )
    assert (d.speed, d.steering) == (pol.cfg.velocidad_precaucion, 0.0)
    como_comando(d)


def test_obstaculo_incierto_lateral_lejos_se_ignora(pol):
    liberar(pol)
    d = pol.decidir(evento(_det([20.0, 50.0, 150.0, 200.0], 0.4)))
    assert (d.action, d.reason) == ("FORWARD", "via_libre")


def test_obstaculo_lateral_lejos_no_corrige(pol):
    liberar(pol)
    d = pol.decidir(evento(_det([20.0, 50.0, 150.0, 200.0])))
    assert (d.action, d.reason) == ("FORWARD", "via_libre")


def test_detener_por_evento_sin_cuadro_pasa_a_falla(pol):
    liberar(pol)
    d = pol.detener("watchdog", "sin_cuadros")
    assert (d.action, d.speed, d.state_after, d.frame_id, d.event) == (
        "STOP",
        0.0,
        "FALLA",
        None,
        "watchdog",
    )
    como_comando(d)
    assert pol.decidir(evento()).action == "STOP"


def test_la_politica_no_importa_etiquetas_ni_hardware():
    arbol = ast.parse((RAIZ / "src" / "p5" / "politica.py").read_text(encoding="utf-8"))
    modulos = {
        n.module if isinstance(n, ast.ImportFrom) else a.name
        for n in ast.walk(arbol)
        if isinstance(n, ast.Import | ast.ImportFrom)
        for a in n.names
    }
    assert modulos <= {
        "__future__",
        "math",
        "dataclasses",
        "pathlib",
        "typing",
        "yaml",
        "p5.contrato",
    }


# --- Escenarios C1-C7 con detecciones sinteticas -----------------------------------------------


def test_c1_via_libre_avanza_y_no_es_stop_constante(pol):
    decisiones = [pol.decidir(evento()) for _ in range(8)]
    avances = [d for d in decisiones if d.action == "FORWARD"]
    assert avances and all(0 < d.speed <= 1 for d in avances)
    assert all(d.synthetic for d in decisiones)
    assert decisiones[-1].state_after == "AVANCE"


def test_c2_obstaculo_central_detiene_en_el_mismo_cuadro(pol):
    liberar(pol)
    d = pol.decidir(evento(_det(CENTRO)))
    assert d.action == "STOP" and d.detections_ref == d.frame_id


def test_c3_obstaculo_solo_a_la_izquierda_no_gira_hacia_el(pol):
    liberar(pol)
    for _ in range(3):
        d = pol.decidir(evento(_det(IZQUIERDA)))
        assert d.action in {"FORWARD", "STEER_RIGHT"} and d.steering >= 0


def test_c4_obstaculo_solo_a_la_derecha_no_gira_hacia_el(pol):
    liberar(pol)
    for _ in range(3):
        d = pol.decidir(evento(_det(DERECHA)))
        assert d.action in {"FORWARD", "STEER_LEFT"} and d.steering <= 0


def test_c5_varios_obstaculos_sin_zona_libre_es_stop(pol):
    liberar(pol)
    d = pol.decidir(evento(_det(IZQUIERDA, 0.9), _det(CENTRO, 0.55), _det(DERECHA, 0.8)))
    assert d.action == "STOP"


def test_c5_laterales_con_centro_libre_no_gira_hacia_ninguno(pol):
    liberar(pol)
    d = pol.decidir(evento(_det(IZQUIERDA), _det(DERECHA)))
    assert (d.action, d.steering, d.state_after) == ("FORWARD", 0.0, "PRECAUCION")


def test_c6_cruzar_el_umbral_cambia_de_precaucion_a_stop(pol):
    liberar(pol)
    umbral = pol.cfg.umbral
    debil = pol.decidir(evento(_det(CENTRO, umbral - 0.05)))
    assert (debil.action, debil.state_after) == ("FORWARD", "PRECAUCION")
    fuerte = pol.decidir(evento(_det(CENTRO, umbral)))
    assert (fuerte.action, fuerte.state_after) == ("STOP", "BLOQUEADO")


def test_c6_incierto_tras_bloqueo_no_libera(pol):
    liberar(pol)
    pol.decidir(evento(_det(CENTRO)))
    for _ in range(pol.cfg.cuadros_liberar + 2):
        d = pol.decidir(evento(_det(CENTRO, 0.4)))
        assert (d.action, d.reason) == ("STOP", "obstaculo_incierto_centro")


def test_c7_aparicion_persistencia_y_desaparicion_con_histeresis(pol):
    n = pol.cfg.cuadros_liberar
    acciones = [pol.decidir(evento()).action for _ in range(n + 2)]
    acciones += [pol.decidir(evento(_det(CENTRO))).action for _ in range(4)]
    acciones += [pol.decidir(evento()).action for _ in range(n + 2)]
    esperado = (
        ["STOP"] * (n - 1) + ["FORWARD"] * 3 + ["STOP"] * 4 + ["STOP"] * (n - 1) + ["FORWARD"] * 3
    )
    assert acciones == esperado


def test_c7_un_solo_cuadro_libre_no_reanuda(pol):
    liberar(pol)
    secuencia = [_det(CENTRO), None, _det(CENTRO), None, _det(CENTRO)]
    acciones = [pol.decidir(evento(*([d] if d else []))).action for d in secuencia]
    assert acciones == ["STOP"] * 5


def test_decisiones_no_comparten_estado_entre_instancias(cfg):
    a, b = Politica(cfg), Politica(cfg)
    liberar(a)
    assert b.estado == "INICIO"


def test_ejemplo_ok_del_contrato_se_decide_sin_error(pol):
    data = json.loads((RAIZ / "config" / "ejemplos" / "ok.json").read_text(encoding="utf-8"))
    d = pol.decidir(validar_evento(copy.deepcopy(data)))
    assert d.action == "STOP" and d.detections_ref == data["frame_id"]
