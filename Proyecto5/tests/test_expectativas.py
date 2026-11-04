"""Expectativas C1-C7: script de acciones por cuadro (con 3 cuadros anotados a mano) y casos."""

from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path

import pytest
import yaml

from p5.contrato import validar_evento
from p5.expectativas import (
    ACCIONES_POR_ESTADO,
    estado_via,
    leer_manifiesto,
    main,
    normalizar_frame_id,
)
from p5.politica import Politica, cargar_config

RAIZ = Path(__file__).resolve().parents[1]
DATOS = Path(__file__).resolve().parent / "datos_expectativas"
CASOS = RAIZ / "casos"
CONFIG = RAIZ / "config" / "politica.yaml"
HASH = "0" * 64


def correr(tmp_path, coco=None, manifiesto=None, secuencias=None):
    salida = tmp_path / "expectativas"
    codigo = main(
        [
            "--coco", str(coco or DATOS / "coco.json"),
            "--manifiesto", str(manifiesto or DATOS / "manifiesto.csv"),
            "--config", str(CONFIG),
            "--salida", str(salida),
        ]
        + (["--secuencias", *secuencias] if secuencias else [])
    )  # fmt: skip
    filas = {}
    for ruta in sorted(salida.glob("cuadros_*.csv")):
        with ruta.open(encoding="utf-8", newline="") as f:
            filas.update({fila["frame_id"]: fila for fila in csv.DictReader(f)})
    origen = json.loads((salida / "cuadros_origen.json").read_text(encoding="utf-8"))
    return codigo, filas, origen


def copia(tmp_path, nombre, cambio):
    destino = tmp_path / "entrada"
    destino.mkdir(exist_ok=True)
    ruta = destino / nombre
    shutil.copy(DATOS / nombre, ruta)
    ruta.write_text(cambio(ruta.read_text(encoding="utf-8")), encoding="utf-8")
    return ruta


# --- Script de acciones por cuadro --------------------------------------------------------------


def test_cuadros_anotados_a_mano(tmp_path):
    codigo, filas, origen = correr(tmp_path)
    assert codigo == 0 and origen["errores"] == []
    libre, izq, centro = filas["S1_f0001"], filas["S1_f0002"], filas["S5_f0001"]

    assert (libre["estado_via"], libre["justificacion"]) == ("libre", "sin objetos anotados")
    assert "STOP" in libre["acciones_permitidas"]

    # persona a la izquierda en riesgo; el perro del centro esta lejos y no bloquea
    assert (izq["estado_via"], izq["zonas_en_riesgo"]) == ("izq", "izquierda")
    assert izq["acciones_permitidas"].split("|") == ["FORWARD", "STEER_RIGHT", "STOP"]
    assert "dog" in izq["justificacion"] and "lejos" in izq["justificacion"]

    # perro al centro en riesgo; el semaforo no es clase de obstaculo
    assert (centro["estado_via"], centro["acciones_permitidas"]) == ("centro", "STOP")
    assert "traffic light" in centro["justificacion"] and "ignorada" in centro["justificacion"]

    assert all(f["coincide"] == "si" for f in filas.values())
    assert len(origen["coco_sha256"]) == 64
    assert origen["secuencias"]["S5"] == {"cuadros": 1, "por_estado": {"centro": 1}}


def test_frame_id_normalizado_como_el_recorrido_y_uuid_conservado(tmp_path):
    _, filas, _ = correr(tmp_path)
    assert [(f["frame_id"], f["frame_id_origen"]) for f in filas.values()] == [
        ("S1_f0001", "aaaa0001"),
        ("S1_f0002", "aaaa0002"),
        ("S5_f0001", "bbbb0001"),
    ]


def test_t_capture_ms_se_escribe_como_en_el_manifiesto(tmp_path):
    # con :g, 3781241 salia como 3.78124e+06 y perdia precision
    manifiesto = copia(
        tmp_path, "manifiesto.csv", lambda t: t.replace(",aaaa0002,100,", ",aaaa0002,3781241,")
    )
    _, filas, _ = correr(tmp_path, manifiesto=manifiesto)
    assert filas["S1_f0002"]["t_capture_ms"] == "3781241"


def test_normalizar_frame_id_respeta_ids_ya_normalizados():
    contadores: dict[str, int] = {}
    assert normalizar_frame_id("S2", "S2_f0007", contadores) == "S2_f0007"
    assert normalizar_frame_id("S2", "S2_feded6ba", contadores) == "S2_f0001"
    assert normalizar_frame_id("S2", "uuid", contadores) == "S2_f0002"
    assert normalizar_frame_id("S3", "uuid", contadores) == "S3_f0001"


def test_un_csv_por_secuencia(tmp_path):
    correr(tmp_path)
    salida = tmp_path / "expectativas"
    assert sorted(p.name for p in salida.glob("cuadros_*.csv")) == [
        "cuadros_S1.csv",
        "cuadros_S5.csv",
    ]
    with (salida / "cuadros_S5.csv").open(encoding="utf-8", newline="") as f:
        assert {fila["sequence_id"] for fila in csv.DictReader(f)} == {"S5"}


def test_solo_las_secuencias_pedidas(tmp_path):
    # S1 sin anotar no es error si solo se pide S5 (las anotaciones llegan por partes)
    coco = copia(tmp_path, "coco.json", lambda t: t.replace("aaaa0001.jpg", "otro.jpg"))
    codigo, filas, origen = correr(tmp_path, coco=coco, secuencias=["S5"])
    assert codigo == 0 and list(filas) == ["S5_f0001"] and list(origen["secuencias"]) == ["S5"]


def test_secuencia_pedida_que_no_existe_sale_con_error(tmp_path):
    codigo, _, origen = correr(tmp_path, secuencias=["S9"])
    assert codigo == 1 and any("S9" in e for e in origen["errores"])


@pytest.mark.parametrize(
    "cambio",
    [
        # despejado, pero la persona anotada esta a la izquierda en riesgo
        (",obstaculo,0,640,480\nS5", ",despejado,0,640,480\nS5"),
        # marcado fuera de riesgo, pero la persona esta en riesgo
        (",obstaculo,0,640,480\nS5", ",obstaculo,1,640,480\nS5"),
    ],
)
def test_estado_que_contradice_el_manifiesto_sale_con_error(tmp_path, cambio):
    manifiesto = copia(tmp_path, "manifiesto.csv", lambda t: t.replace(*cambio))
    codigo, filas, origen = correr(tmp_path, manifiesto=manifiesto)
    assert codigo == 1 and filas["S1_f0002"]["coincide"] == "no"
    assert any("S1_f0002" in e for e in origen["errores"])


def test_obstaculo_marcado_en_riesgo_sin_caja_en_riesgo_sale_con_error(tmp_path):
    manifiesto = copia(
        tmp_path, "manifiesto.csv", lambda t: t.replace(",despejado,0,", ",obstaculo,0,")
    )
    codigo, filas, _ = correr(tmp_path, manifiesto=manifiesto)
    assert codigo == 1 and filas["S1_f0001"]["coincide"] == "no"


def test_cuadro_sin_anotar_no_cuenta_como_vacio(tmp_path):
    coco = copia(tmp_path, "coco.json", lambda t: t.replace("aaaa0001.jpg", "otro.jpg"))
    codigo, filas, origen = correr(tmp_path, coco=coco)
    assert codigo == 1 and "S1_f0001" not in filas
    assert any("sin anotar" in e for e in origen["errores"])


def test_caja_fuera_del_cuadro_sale_con_error(tmp_path):
    coco = copia(
        tmp_path, "coco.json", lambda t: t.replace("[250, 120, 140, 350]", "[600, 120, 140, 350]")
    )
    codigo, _, origen = correr(tmp_path, coco=coco)
    assert codigo == 1 and any("fuera del cuadro" in e for e in origen["errores"])


def test_dimensiones_distintas_salen_con_error(tmp_path):
    manifiesto = copia(
        tmp_path, "manifiesto.csv", lambda t: t.replace(",0,640,480", ",0,320,240", 1)
    )
    codigo, _, origen = correr(tmp_path, manifiesto=manifiesto)
    assert codigo == 1 and any("dimensiones" in e for e in origen["errores"])


def test_el_manifiesto_real_de_p5_05_se_lee():
    ruta = RAIZ / "datos" / "evaluacion" / "capturas.csv"
    cuadros = leer_manifiesto(ruta)
    assert {c.sequence_id for c in cuadros} == {"S1", "S2", "S3", "S4", "S5", "S6"}
    assert all(c.frame_id.startswith(f"{c.sequence_id}_f") for c in cuadros)
    assert len({c.frame_id for c in cuadros}) == len(cuadros)
    # el conteo sale del propio CSV, para no romperse con una recaptura
    with ruta.open(encoding="utf-8", newline="") as f:
        fuera = sum(fila["outside_risk"] == "1" for fila in csv.DictReader(f))
    assert fuera > 0
    assert sum(c.estado_manifiesto == "obstaculo_fuera_riesgo" for c in cuadros) == fuera


@pytest.mark.parametrize(
    ("zonas", "estado"),
    [
        (set(), "libre"),
        ({"izquierda"}, "izq"),
        ({"derecha"}, "der"),
        ({"izquierda", "derecha"}, "laterales"),
        ({"centro"}, "centro"),
        ({"izquierda", "centro"}, "centro"),
        ({"izquierda", "centro", "derecha"}, "bloqueado"),
    ],
)
def test_estado_via_por_zonas(zonas, estado):
    assert estado_via(zonas) == estado


def test_nunca_se_permite_girar_hacia_la_zona_ocupada():
    assert "STEER_LEFT" not in ACCIONES_POR_ESTADO["izq"]
    assert "STEER_RIGHT" not in ACCIONES_POR_ESTADO["der"]
    assert ACCIONES_POR_ESTADO["centro"] == ACCIONES_POR_ESTADO["bloqueado"] == ("STOP",)


# --- Casos C01-C07 ------------------------------------------------------------------------------

IDS = [f"C0{i}" for i in range(1, 8)]


def caso(cid):
    entrada = yaml.safe_load((CASOS / f"{cid}.yaml").read_text(encoding="utf-8"))
    expectativa = yaml.safe_load((CASOS / entrada["expectativa"]).read_text(encoding="utf-8"))
    return entrada, expectativa


@pytest.mark.parametrize("cid", IDS)
def test_caso_separa_entrada_y_expectativa(cid):
    entrada, expectativa = caso(cid)
    assert entrada["id"] == expectativa["id"] == cid
    assert entrada["tipo"] in {"real", "sintetico"}
    texto = yaml.safe_dump(entrada["entrada"])
    assert "acciones_permitidas" not in texto and "estado_via" not in texto
    # el recorrido de P5-14 reproduce a 100 ms fijos: el plazo es un cuadro, como el watchdog
    assert expectativa["plazo_reaccion_ms"] == 100 and expectativa["plazo_reaccion_cuadros"] >= 0


@pytest.mark.parametrize("cid", [c for c in IDS if c != "C06"])
def test_casos_reales_usan_secuencias_distintas_y_estados_conocidos(cid):
    entrada, expectativa = caso(cid)
    assert entrada["tipo"] == "real"
    secuencia = entrada["entrada"]["secuencia"]
    assert secuencia == expectativa["secuencia"]
    assert expectativa["acciones_por_cuadro"] == f"cuadros_{secuencia}.csv"
    assert (RAIZ / entrada["entrada"]["manifiesto"]).is_file()
    assert set(expectativa["estados_requeridos"]) <= set(ACCIONES_POR_ESTADO)
    secuencias = [caso(c)[0]["entrada"]["secuencia"] for c in IDS if c != "C06"]
    assert len(set(secuencias)) == len(secuencias)


def eventos_c06():
    entrada, _ = caso("C06")
    e = entrada["entrada"]
    for ev in e["eventos"]:
        yield validar_evento(
            {
                "schema_version": "1.0",
                "run_id": "run-c06",
                "sequence_id": e["sequence_id"],
                "frame_id": ev["frame_id"],
                "t_capture_ms": ev["t_capture_ms"],
                "image_path": f"sinteticos/{ev['frame_id']}.jpg",
                "image_sha256": HASH,
                "image_width": e["image_width"],
                "image_height": e["image_height"],
                "model_sha256": HASH,
                "config_sha256": HASH,
                "status": "ok",
                "error_msg": None,
                "synthetic": True,
                "detections": ev["detections"],
            }
        )


def test_c06_es_sintetico_y_sus_eventos_cumplen_el_contrato():
    entrada, expectativa = caso("C06")
    eventos = list(eventos_c06())
    assert entrada["tipo"] == "sintetico" and all(ev.synthetic for ev in eventos)
    assert [ev.frame_id for ev in eventos] == [c["frame_id"] for c in expectativa["cuadros"]]


def test_c06_la_politica_actual_cumple_la_expectativa():
    _, expectativa = caso("C06")
    pol = Politica(cargar_config(CONFIG))
    for ev, esperado in zip(eventos_c06(), expectativa["cuadros"], strict=True):
        d = pol.decidir(ev)
        assert d.action in esperado["acciones_permitidas"], ev.frame_id
        assert d.speed <= esperado.get("velocidad_max", 1.0), ev.frame_id
