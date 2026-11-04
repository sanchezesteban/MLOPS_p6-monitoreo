"""P5-06 (#58): lectura de capturas, COCO de la verdad de referencia y anotador local."""

from __future__ import annotations

import csv
import importlib.util
import json
import shutil
from pathlib import Path

import pytest

from p5.contrato import en_riesgo, zonas_ocupadas
from p5.datos import (
    CONJUNTOS,
    DatosError,
    cajas_por_ruta,
    cargar_coco,
    categorias,
    coco_vacio,
    estado_esperado,
    estado_via,
    guardar_coco,
    id_imagen,
    leer_capturas,
    registrar_cuadro,
    sha256_archivo,
    sincronizar,
)
from p5.politica import cargar_config

RAIZ = Path(__file__).resolve().parents[1]
CLASES = cargar_config(RAIZ / "config" / "politica.yaml").clases_obstaculo


# --- Cuadros de P5-05 ---------------------------------------------------------------------


@pytest.mark.parametrize("conjunto", sorted(CONJUNTOS))
def test_frame_id_consecutivo_por_secuencia_en_orden_temporal(conjunto):
    cuadros = leer_capturas(conjunto)
    assert cuadros
    por_seq: dict[str, list] = {}
    for c in cuadros:
        por_seq.setdefault(c.sequence_id, []).append(c)
    for seq, propios in por_seq.items():
        assert [c.frame_id for c in propios] == [
            f"{seq}_f{n:04d}" for n in range(1, len(propios) + 1)
        ]
        tiempos = [c.t_capture_ms for c in propios]
        assert tiempos == sorted(set(tiempos)), f"{seq}: t_capture_ms no estrictamente creciente"
    assert len({c.frame_id for c in cuadros}) == len(cuadros)


def test_ajuste_nunca_comparte_frame_id_ni_ruta_con_evaluacion():
    ev, aj = leer_capturas("evaluacion"), leer_capturas("ajuste")
    assert {c.sequence_id for c in aj} == {"AJ1"}
    assert not {c.frame_id for c in ev} & {c.frame_id for c in aj}
    assert not {c.ruta for c in ev} & {c.ruta for c in aj}
    assert not {c.sha256 for c in ev} & {c.sha256 for c in aj}


def test_ruta_relativa_a_proyecto5_y_hash_del_csv_coincide_con_los_bytes():
    for c in leer_capturas("evaluacion") + leer_capturas("ajuste"):
        assert c.ruta == f"{CONJUNTOS[c.conjunto].carpeta}/{c.path_capturas}"
        assert sha256_archivo(RAIZ / c.ruta) == c.sha256


def _copiar_csv(tmp_path: Path, filas_fn) -> Path:
    destino = tmp_path / "datos" / "evaluacion"
    destino.mkdir(parents=True)
    with (RAIZ / "datos/evaluacion/capturas.csv").open(encoding="utf-8", newline="") as f:
        lector = csv.DictReader(f)
        campos, filas = lector.fieldnames, list(lector)
    with (destino / "capturas.csv").open("w", encoding="utf-8", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=campos)
        escritor.writeheader()
        escritor.writerows(filas_fn(filas))
    return tmp_path


def test_csv_desordenado_se_rechaza_en_lugar_de_numerar_distinto(tmp_path):
    def invertir_s1(filas):
        s1 = [f for f in filas if f["sequence_id"] == "S1"]
        return s1[::-1] + [f for f in filas if f["sequence_id"] != "S1"]

    raiz = _copiar_csv(tmp_path, invertir_s1)
    with pytest.raises(DatosError, match="no viene ordenada"):
        leer_capturas("evaluacion", raiz)


def test_id_imagen_estable():
    assert id_imagen("S5_f0012") == 5012
    assert id_imagen("AJ1_f0003") == 1003
    with pytest.raises(DatosError):
        id_imagen("S1_3ca02f25")


# --- COCO ---------------------------------------------------------------------------------


def test_categorias_son_los_indices_del_detector_y_las_clases_de_la_politica():
    cats = categorias()
    assert {c["name"]: c["id"] for c in cats} == {"person": 0, "cat": 15, "dog": 16}
    assert {c["name"] for c in cats} == set(CLASES)


def _cuadro(frame_id: str = "S5_f0001"):
    return next(c for c in leer_capturas("evaluacion") if c.frame_id == frame_id)


def test_registrar_cuadro_con_cajas_y_vacio_explicito():
    coco = coco_vacio("evaluacion")
    c5, c1 = _cuadro("S5_f0001"), _cuadro("S1_f0001")
    registrar_cuadro(coco, c5, [{"clase": "cat", "bbox": [10, 150, 50.04, 100]}], False)
    registrar_cuadro(coco, c1, [], True)
    img5 = next(i for i in coco["images"] if i["frame_id"] == "S5_f0001")
    img1 = next(i for i in coco["images"] if i["frame_id"] == "S1_f0001")
    assert img5["file_name"] == c5.ruta and img5["sin_objetos"] is False
    assert img1["sin_objetos"] is True and img1["id"] == 1001
    (ann,) = coco["annotations"]
    assert ann == {
        "id": 500101,
        "image_id": 5001,
        "category_id": 15,
        "bbox": [10.0, 150.0, 50.0, 100.0],
        "area": 5000.0,
        "iscrowd": 0,
    }
    assert cajas_por_ruta(coco) == {c5.ruta: [("cat", (10.0, 150.0, 60.0, 250.0))], c1.ruta: []}


def test_volver_a_guardar_reemplaza_las_cajas_del_cuadro():
    coco = coco_vacio("evaluacion")
    c = _cuadro()
    registrar_cuadro(coco, c, [{"clase": "cat", "bbox": [1, 1, 5, 5]}] * 3, False)
    registrar_cuadro(coco, c, [{"clase": "dog", "bbox": [1, 1, 5, 5]}], False)
    assert len(coco["images"]) == 1
    assert [a["category_id"] for a in coco["annotations"]] == [16]


@pytest.mark.parametrize(
    ("cajas", "sin_objetos", "error"),
    [
        ([], False, "sin cajas"),
        ([{"clase": "cat", "bbox": [1, 1, 5, 5]}], True, "sin objetos"),
        ([{"clase": "tv", "bbox": [1, 1, 5, 5]}], False, "no evaluada"),
        ([{"clase": "cat", "bbox": [390, 10, 20, 20]}], False, "fuera del cuadro"),
        ([{"clase": "cat", "bbox": [-1, 10, 20, 20]}], False, "fuera del cuadro"),
        ([{"clase": "cat", "bbox": [10, 10, 0, 20]}], False, "sin area"),
    ],
)
def test_registrar_cuadro_rechaza_entradas_invalidas(cajas, sin_objetos, error):
    with pytest.raises(DatosError, match=error):
        registrar_cuadro(coco_vacio("evaluacion"), _cuadro(), cajas, sin_objetos)


def test_guardar_y_cargar_coco_ida_y_vuelta(tmp_path):
    coco = coco_vacio("evaluacion")
    registrar_cuadro(coco, _cuadro("S1_f0002"), [], True)
    registrar_cuadro(coco, _cuadro("S1_f0001"), [], True)
    ruta = tmp_path / "anotaciones.json"
    guardar_coco(ruta, coco)
    leido = cargar_coco(ruta, "evaluacion")
    assert [i["id"] for i in leido["images"]] == [1001, 1002]
    assert list(tmp_path.iterdir()) == [ruta]  # sin temporales sueltos


def test_sincronizar_conserva_vacio_explicito_y_cajas_y_avisa_huerfanas():
    coco = coco_vacio("evaluacion")
    registrar_cuadro(coco, _cuadro("S1_f0001"), [], True)
    registrar_cuadro(coco, _cuadro(), [{"clase": "dog", "bbox": [1, 1, 5, 5]}], False)
    coco["images"].append({"id": 9001, "file_name": "datos/evaluacion/S9/x.jpg"})
    avisos = sincronizar(coco, leer_capturas("evaluacion"))
    assert avisos == ["datos/evaluacion/S9/x.jpg: anotada pero ya no esta en capturas.csv"]
    img1 = next(i for i in coco["images"] if i["id"] == 1001)
    assert img1["sin_objetos"] is True
    assert len(coco["annotations"]) == 1


# --- Estado esperado ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("zonas", "estado"),
    [
        (set(), "libre"),
        ({"izquierda"}, "izq"),
        ({"derecha"}, "der"),
        ({"izquierda", "derecha"}, "laterales"),
        ({"centro"}, "centro"),
        ({"centro", "izquierda"}, "centro"),
        ({"izquierda", "centro", "derecha"}, "bloqueado"),
    ],
)
def test_estado_via(zonas, estado):
    assert estado_via(zonas) == estado


def test_estado_esperado_usa_la_geometria_del_contrato():
    w, h = 400, 296
    cajas = [
        ("cat", (10.0, 150.0, 60.0, 250.0)),  # izquierda, en riesgo
        ("person", (300.0, 10.0, 390.0, 100.0)),  # derecha, lejos
        ("tv", (150.0, 150.0, 250.0, 290.0)),  # no es clase de obstaculo
    ]
    est = estado_esperado(cajas, w, h, CLASES)
    assert est.estado == "izq"
    assert est.zonas_en_riesgo == ("izquierda",)
    assert (est.n_cajas, est.n_obstaculos, est.n_en_riesgo) == (3, 2, 1)
    assert zonas_ocupadas(cajas[0][1], w) == {"izquierda"} and en_riesgo(cajas[0][1], h)
    # borde exacto del riesgo: y2 = H/2 cuenta como en riesgo
    assert estado_esperado([("dog", (150.0, 0.0, 250.0, 148.0))], w, h, CLASES).estado == "centro"


# --- Anotador local -----------------------------------------------------------------------


def _servidor():
    ruta = RAIZ / "scripts" / "anotador" / "servidor.py"
    spec = importlib.util.spec_from_file_location("anotador_servidor", ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


@pytest.fixture
def copia(tmp_path):
    for parte in ("datos/evaluacion", "datos/ajuste"):
        shutil.copytree(RAIZ / parte, tmp_path / parte)
    (tmp_path / "modelo").mkdir()
    shutil.copy(RAIZ / "modelo/descriptor.yaml", tmp_path / "modelo/descriptor.yaml")
    return tmp_path


def test_anotador_guarda_coco_sin_tocar_los_jpeg(copia):
    srv = _servidor()
    anotador = srv.Anotador(copia, {"S1", "S5"}, CLASES)
    antes = {p: p.read_bytes() for p in (copia / "datos").rglob("*.jpg")}
    filas = anotador.estado("evaluacion")["cuadros"]
    assert [f["sequence_id"] for f in filas] == ["S1"] * 12 + ["S5"] * 12
    assert not any(f["revisado"] for f in filas)

    anotador.guardar("evaluacion", 0, [], True)
    anotador.guardar("evaluacion", 12, [{"clase": "person", "bbox": [100, 150, 200, 140]}], False)
    filas = anotador.estado("evaluacion")["cuadros"]
    assert filas[0]["revisado"] and filas[0]["sin_objetos"] and filas[0]["estado"] == "libre"
    assert filas[12]["estado"] == "bloqueado" and filas[12]["zonas_en_riesgo"] == [
        "izquierda",
        "centro",
        "derecha",
    ]
    coco = json.loads((copia / "datos/anotaciones.json").read_text(encoding="utf-8"))
    assert [i["frame_id"] for i in coco["images"]] == ["S1_f0001", "S5_f0001"]

    anotador.desmarcar("evaluacion", 12)
    assert not anotador.estado("evaluacion")["cuadros"][12]["revisado"]
    with pytest.raises(DatosError):
        anotador.guardar("evaluacion", -1, [], True)
    assert {p: p.read_bytes() for p in (copia / "datos").rglob("*.jpg")} == antes
    assert not (copia / "datos/anotaciones_ajuste.json").exists()
