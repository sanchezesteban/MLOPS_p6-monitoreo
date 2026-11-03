"""P5-12: watchdog de vencimiento, emergencia enclavada con rearme y cierre, con reloj controlado.

Arma el `Command` desde la `Decision` de la politica y lo manda al adaptador virtual.
"""

from __future__ import annotations

import copy
import json
import signal
from pathlib import Path

import pytest

from p5.contrato import validar_comando, validar_evento
from p5.control import AdaptadorVirtual
from p5.politica import Politica
from p5.politica import cargar_config as cargar_config_politica
from p5.watchdog import (
    ConfigWatchdog,
    ConfigWatchdogError,
    RelojControlado,
    Watchdog,
    cargar_config,
    validar_config,
)

RAIZ = Path(__file__).resolve().parents[1]
POLITICA_YAML = RAIZ / "config" / "politica.yaml"
WATCHDOG_YAML = RAIZ / "config" / "watchdog.yaml"
W, H = 640, 480
HASH = "0" * 64
CENTRO_RIESGO = [250.0, 120.0, 390.0, 470.0]


def leer_lineas(log_path: Path) -> list[dict]:
    return [json.loads(linea) for linea in log_path.read_text(encoding="utf-8").splitlines()]


def _det(bbox, confidence=0.9, class_name="person"):
    return {"class_name": class_name, "class_id": 0, "confidence": confidence, "bbox": bbox}


def evento(t_capture_ms, *detecciones, status="ok", frame_id=None, i=0):
    data = {
        "schema_version": "1.0",
        "run_id": "run-test",
        "sequence_id": "seqT",
        "frame_id": frame_id or f"seqT_f{i:05d}",
        "t_capture_ms": t_capture_ms,
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


@pytest.fixture
def cfg():
    return cargar_config(WATCHDOG_YAML)


@pytest.fixture
def politica():
    return Politica(cargar_config_politica(POLITICA_YAML))


@pytest.fixture
def reloj():
    return RelojControlado()


@pytest.fixture
def adaptador(tmp_path, reloj):
    adaptador = AdaptadorVirtual(tmp_path / "comandos.jsonl", run_id="run-test", reloj=reloj)
    yield adaptador
    adaptador.cerrar()


@pytest.fixture
def wd(politica, adaptador, reloj, cfg):
    return Watchdog(politica, adaptador, reloj, cfg, run_id="run-test")


def liberar(wd, reloj, n, paso=100.0):
    """Manda `n` cuadros despejados seguidos (histeresis de la politica)."""
    i = 0
    for i in range(n):
        reloj.avanzar(paso)
        wd.procesar_evento(evento(reloj(), i=i))
    return i


# --- cuadro viejo: se rechaza sin esperar un cuadro nuevo, no reanuda movimiento ---


def test_cuadro_viejo_se_rechaza_y_no_reanuda_movimiento(wd, adaptador, reloj):
    reloj.avanzar(1000.0)
    # el cuadro "nacio" hace mas de max_edad_ms (300): vencido aunque A lo reporte status=ok
    viejo = evento(t_capture_ms=reloj() - 400.0, i=0)

    wd.procesar_evento(viejo)

    (linea,) = leer_lineas(adaptador._log_path)
    assert linea["action"] == "STOP"
    assert linea["event"] == "stale_frame"
    assert linea["reason"] == "cuadro_vencido"
    assert linea["frame_id"] == viejo.frame_id  # se conserva para saber que cuadro se rechazo
    validar_comando(linea)


def test_cuadro_viejo_no_cuenta_para_la_histeresis(wd, adaptador, reloj):
    reloj.avanzar(1000.0)
    viejo = evento(t_capture_ms=reloj() - 400.0, i=0)
    wd.procesar_evento(viejo)

    liberar(wd, reloj, 3)  # necesita las 3 seguidas: el viejo no adelanto nada

    ultima = leer_lineas(adaptador._log_path)[-1]
    assert ultima["action"] == "FORWARD"


# --- tick: perdida de cuadros y vencimiento del comando, sin esperar un cuadro nuevo ---


def test_tick_detecta_perdida_de_cuadros_sin_cuadro_nuevo(wd, adaptador, reloj):
    # un solo cuadro despejado: sigue en STOP (falta histeresis), por lo que no hay
    # ningun comando de movimiento en curso que venza primero -- aisla la perdida de cuadros.
    reloj.avanzar(100.0)
    wd.procesar_evento(evento(reloj(), i=0))
    assert leer_lineas(adaptador._log_path)[-1]["action"] == "STOP"

    reloj.avanzar(301.0)  # > max_edad_ms (300) desde el ultimo cuadro bueno
    wd.tick()

    ultima = leer_lineas(adaptador._log_path)[-1]
    assert ultima["action"] == "STOP"
    assert ultima["event"] == "watchdog"
    assert ultima["reason"] == "sin_cuadros_recientes"


def test_tick_no_repite_el_stop_mientras_sigue_sin_cuadros(wd, adaptador, reloj):
    reloj.avanzar(100.0)
    wd.procesar_evento(evento(reloj(), i=0))
    reloj.avanzar(301.0)
    wd.tick()  # primer STOP: entra a FALLA
    antes = len(leer_lineas(adaptador._log_path))

    reloj.avanzar(1000.0)  # sigue sin cuadros nuevos, mucho mas vencido todavia
    wd.tick()
    wd.tick()

    assert len(leer_lineas(adaptador._log_path)) == antes  # no repite: ya estaba en FALLA


def test_tick_detecta_vencimiento_del_comando_en_curso(wd, adaptador, reloj):
    liberar(wd, reloj, 3)

    reloj.avanzar(251.0)  # > vencimiento_ms (250) del ultimo comando, pero < max_edad_ms
    wd.tick()

    ultima = leer_lineas(adaptador._log_path)[-1]
    assert ultima["action"] == "STOP"
    assert ultima["reason"] == "comando_vencido"


def test_tick_sin_cuadros_todavia_no_hace_nada(wd, adaptador, reloj):
    reloj.avanzar(10_000.0)
    wd.tick()

    assert not adaptador._log_path.exists() or adaptador._log_path.read_text() == ""


def test_tick_no_actua_mientras_hay_margen(wd, adaptador, reloj):
    liberar(wd, reloj, 3)
    antes = len(leer_lineas(adaptador._log_path))

    reloj.avanzar(50.0)  # por debajo de ambos plazos
    wd.tick()

    assert len(leer_lineas(adaptador._log_path)) == antes


# --- emergencia: prioridad inmediata, enclavada, solo libera con rearme + cuadro fresco ---


def test_emergencia_detiene_de_inmediato_con_prioridad(wd, adaptador, reloj):
    liberar(wd, reloj, 3)

    wd.emergencia("boton_fisico")

    ultima = leer_lineas(adaptador._log_path)[-1]
    assert ultima["action"] == "STOP"
    assert ultima["event"] == "emergency"
    assert ultima["reason"] == "boton_fisico"


def test_emergencia_enclavada_no_omite_cuadros_en_silencio(wd, adaptador, reloj):
    """Cada cuadro que llega mientras esta enclavada queda en la bitacora (sin omisiones
    silenciosas), aunque llegue despejado y no se le pase a la politica."""
    liberar(wd, reloj, 3)
    wd.emergencia()
    antes = len(leer_lineas(adaptador._log_path))

    for i in range(10):
        reloj.avanzar(100.0)
        cuadro = evento(reloj(), i=100 + i)  # cuadros despejados, frescos
        wd.procesar_evento(cuadro)

    lineas = leer_lineas(adaptador._log_path)[antes:]
    assert len(lineas) == 10
    assert all(linea["action"] == "STOP" for linea in lineas)
    assert all(linea["event"] == "emergency" for linea in lineas)
    assert all(linea["reason"] == "emergencia_enclavada" for linea in lineas)
    assert lineas[-1]["frame_id"] == cuadro.frame_id


def test_rearme_queda_registrado_pero_no_libera_sin_cuadro_fresco(wd, adaptador, reloj):
    liberar(wd, reloj, 3)
    wd.emergencia()
    reloj.avanzar(1000.0)
    wd.rearme()

    rearme_log = leer_lineas(adaptador._log_path)[-1]
    assert rearme_log["action"] == "STOP" and rearme_log["event"] == "rearm"

    viejo = evento(t_capture_ms=reloj() - 400.0, i=200)  # vencido: no cuenta como "fresco"
    wd.procesar_evento(viejo)

    ultima = leer_lineas(adaptador._log_path)[-1]
    assert ultima["event"] == "emergency"  # sigue enclavada, solo registro el cuadro ignorado
    assert ultima["frame_id"] == viejo.frame_id


def test_rearme_con_cuadro_fresco_libera_y_exige_histeresis_de_nuevo(wd, adaptador, reloj):
    liberar(wd, reloj, 3)
    wd.emergencia()
    wd.rearme()

    reloj.avanzar(100.0)
    wd.procesar_evento(evento(reloj(), i=300))  # cuadro fresco: libera el enclave

    primera_tras_liberar = leer_lineas(adaptador._log_path)[-1]
    assert primera_tras_liberar["action"] == "STOP"  # FALLA: pide histeresis, no reanuda sola
    assert primera_tras_liberar["event"] is None  # ya no es la emergencia, es una decision normal

    liberar(wd, reloj, 2, paso=100.0)  # 2 mas (ya van 3 cuadros libres desde el rearme)
    assert leer_lineas(adaptador._log_path)[-1]["action"] == "FORWARD"


def test_rearme_sin_emergencia_no_hace_nada(wd, adaptador, reloj):
    wd.rearme()  # no debe lanzar ni dejar nada armado de mas
    reloj.avanzar(100.0)
    wd.procesar_evento(evento(reloj(), i=0))

    assert leer_lineas(adaptador._log_path)[-1]["action"] == "STOP"  # INICIO: histeresis normal


# --- cierre, SIGINT y SIGTERM ---


def test_cerrar_delega_en_el_adaptador_y_registra_shutdown(wd, adaptador, reloj):
    liberar(wd, reloj, 3)

    wd.cerrar()

    ultima = leer_lineas(adaptador._log_path)[-1]
    assert ultima["action"] == "STOP" and ultima["event"] == "shutdown"


def test_sigint_cierra_registra_stop_y_termina_el_programa(wd, adaptador):
    anterior = signal.getsignal(signal.SIGINT)
    try:
        with pytest.raises(SystemExit) as exc:
            wd._manejar_señal(signal.SIGINT, None)
    finally:
        signal.signal(signal.SIGINT, anterior)

    assert exc.value.code == 128 + signal.SIGINT  # convencion unix: no se queda corriendo
    ultima = leer_lineas(adaptador._log_path)[-1]
    assert ultima["action"] == "STOP" and ultima["event"] == "shutdown"


def test_sigterm_cierra_registra_stop_y_termina_el_programa(wd, adaptador):
    anterior = signal.getsignal(signal.SIGTERM)
    try:
        with pytest.raises(SystemExit) as exc:
            wd._manejar_señal(signal.SIGTERM, None)
    finally:
        signal.signal(signal.SIGTERM, anterior)

    assert exc.value.code == 128 + signal.SIGTERM
    ultima = leer_lineas(adaptador._log_path)[-1]
    assert ultima["action"] == "STOP" and ultima["event"] == "shutdown"


def test_instalar_señales_no_lanza_y_deja_sigint_y_sigterm_manejados(wd):
    previos = signal.getsignal(signal.SIGINT), signal.getsignal(signal.SIGTERM)
    try:
        wd.instalar_señales()
        assert signal.getsignal(signal.SIGINT) == wd._manejar_señal
        assert signal.getsignal(signal.SIGTERM) == wd._manejar_señal
    finally:
        signal.signal(signal.SIGINT, previos[0])
        signal.signal(signal.SIGTERM, previos[1])


# --- construccion del Command desde la Decision: tiempos y valid_until_ms ---


def test_comando_de_movimiento_tiene_valid_until_en_el_futuro(wd, adaptador, reloj):
    liberar(wd, reloj, 3)

    ultima = leer_lineas(adaptador._log_path)[-1]
    assert ultima["action"] == "FORWARD"
    assert ultima["valid_until_ms"] is not None
    assert ultima["valid_until_ms"] > ultima["t_command_ms"]
    validar_comando(ultima)


def test_comando_de_stop_no_tiene_valid_until(wd, adaptador, reloj):
    reloj.avanzar(100.0)
    wd.procesar_evento(evento(reloj(), i=0))  # INICIO: todavia no libera -> STOP

    ultima = leer_lineas(adaptador._log_path)[-1]
    assert ultima["action"] == "STOP"
    assert ultima["valid_until_ms"] is None
    validar_comando(ultima)


def test_run_id_del_comando_es_el_de_la_corrida(wd, adaptador, reloj):
    liberar(wd, reloj, 1)

    assert leer_lineas(adaptador._log_path)[-1]["run_id"] == "run-test"


# --- configuracion ---


def test_config_de_ejemplo_es_valida():
    cfg = cargar_config(WATCHDOG_YAML)
    assert isinstance(cfg, ConfigWatchdog)
    assert cfg.plazo_reaccion_ms <= cfg.max_edad_ms


CONFIG_BASE = {
    "version": 1,
    "plazos": {"plazo_reaccion_ms": 100, "max_edad_ms": 300, "vencimiento_ms": 250},
}


def _config_mal(cambio):
    data = copy.deepcopy(CONFIG_BASE)
    cambio(data)
    return data


CONFIGS_INVALIDAS = {
    "mapa_vacio": lambda d: d.clear(),
    "version_incorrecta": lambda d: d.update(version=2),
    "clave_desconocida": lambda d: d.update(otra="cosa"),
    "falta_plazos": lambda d: d.pop("plazos"),
    "plazos_no_es_mapa": lambda d: d.update(plazos="no"),
    "plazos_clave_desconocida": lambda d: d["plazos"].update(otra=1),
    "plazos_falta_clave": lambda d: d["plazos"].pop("vencimiento_ms"),
    "plazos_numero_no_positivo": lambda d: d["plazos"].update(max_edad_ms=0),
    "plazos_numero_no_finito": lambda d: d["plazos"].update(max_edad_ms=float("nan")),
    "plazos_texto": lambda d: d["plazos"].update(max_edad_ms="300"),
    "reaccion_mayor_que_max_edad": lambda d: d["plazos"].update(plazo_reaccion_ms=1000),
}


@pytest.mark.parametrize("caso", sorted(CONFIGS_INVALIDAS))
def test_config_invalida_se_rechaza(caso):
    with pytest.raises(ConfigWatchdogError):
        validar_config(_config_mal(CONFIGS_INVALIDAS[caso]))


def test_config_illegible_lanza_config_error(tmp_path):
    ruta = tmp_path / "roto.yaml"
    ruta.write_text("version: [1, 2\n", encoding="utf-8")  # YAML mal formado
    with pytest.raises(ConfigWatchdogError):
        cargar_config(ruta)
