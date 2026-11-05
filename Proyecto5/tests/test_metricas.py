"""P5-07: cuentas calculadas a mano, sin imagenes, red, ONNX ni hardware."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from p5.metricas import CLASES, EntradaError, evaluar, iou, main

FIXTURES = Path(__file__).parent / "fixtures" / "metricas"


def gt(cajas=(), *, n=1):
    return {
        "info": {"synthetic": True},
        # IDs de categorias del export COCO NO son los indices COCO del detector.
        "categories": [{"id": i + 1, "name": nombre} for i, nombre in enumerate(CLASES)],
        "images": [
            {
                "id": i,
                "file_name": f"S1/{i}.jpg",
                "width": 100,
                "height": 100,
                "frame_id": f"S1_f{i}",
                "sequence_id": "S1",
            }
            for i in range(1, n + 1)
        ],
        "annotations": [
            {
                "id": i,
                "image_id": frame,
                "category_id": list(CLASES).index(clase) + 1,
                "bbox": caja,
                "iscrowd": 0,
            }
            for i, (frame, clase, caja) in enumerate(cajas, 1)
        ],
    }


def det(clase="person", caja=(0, 0, 10, 10), confianza=0.9):
    return {
        "class_name": clase,
        "class_id": CLASES[clase],
        "bbox": list(caja),
        "confidence": confianza,
    }


def evento(detecciones=(), *, frame=1, estado="ok", **cambios):
    return {
        "schema_version": "1.0",
        "run_id": "SINTETICO",
        "sequence_id": "S1",
        "frame_id": f"S1_f{frame}",
        "t_capture_ms": frame,
        "image_path": f"S1/{frame}.jpg",
        "image_sha256": "a" * 64,
        "image_width": 100,
        "image_height": 100,
        "model_sha256": "b" * 64,
        "config_sha256": "c" * 64,
        "status": estado,
        "error_msg": None if estado == "ok" else "fallo SINTETICO",
        "synthetic": True,
        "detections": list(detecciones),
        **cambios,
    }


def jsonl(*eventos):
    return "\n".join(json.dumps(ev) for ev in eventos)


@pytest.mark.parametrize(
    ("cajas", "pred", "esperado"),
    [
        ([(1, "person", [0, 0, 10, 10])], [evento([det(caja=(0, 0, 9, 10))])], (1, 0, 0)),
        ([], [evento([det()])], (0, 1, 0)),
        ([(1, "person", [0, 0, 10, 10])], [evento()], (0, 0, 1)),
        ([(1, "person", [0, 0, 10, 10])], [evento([det(), det(confianza=0.8)])], (1, 1, 0)),
        ([(1, "dog", [0, 0, 10, 10])], [evento([det("cat")])], (0, 1, 1)),
        ([], [evento()], (0, 0, 0)),
    ],
)
def test_seis_casos_manuales(cajas, pred, esperado):
    resultado = evaluar(gt(cajas), jsonl(*pred))
    assert tuple(resultado["micro"][k] for k in ("tp", "fp", "fn")) == esperado
    assert set(resultado["per_class"]) == {"person", "cat", "dog"}


def test_clase_incorrecta_fp_en_predicha_fn_en_real():
    r = evaluar(gt([(1, "dog", [0, 0, 10, 10])]), jsonl(evento([det("cat")])))
    assert r["per_class"]["cat"]["fp"] == 1
    assert r["per_class"]["dog"]["fn"] == 1


@pytest.mark.parametrize(
    "ids_gt",
    [
        pytest.param({"person": 0, "cat": 15, "dog": 16}, id="indices-modelo"),
        pytest.param({"person": 1, "cat": 17, "dog": 18}, id="export-coco"),
    ],
)
@pytest.mark.parametrize(("nombre", "id_detector"), [("person", 0), ("cat", 15), ("dog", 16)])
def test_clase_correcta_es_tp_con_ambas_numeraciones_coco(ids_gt, nombre, id_detector):
    verdad = gt([(1, nombre, [0, 0, 10, 10])])
    # Cambiar orden e IDs del GT no cambia la clase; no derivar la prediccion del GT.
    verdad["categories"] = [{"id": ids_gt[n], "name": n} for n in ("dog", "person", "cat")]
    verdad["annotations"][0]["category_id"] = ids_gt[nombre]
    pred = {
        "class_name": nombre,
        "class_id": id_detector,
        "confidence": 0.9,
        "bbox": [0, 0, 10, 10],
    }

    r = evaluar(verdad, jsonl(evento([pred])))

    assert r["input_integrity_ok"]
    assert (r["micro"]["tp"], r["micro"]["fp"], r["micro"]["fn"]) == (1, 0, 0)
    clase = r["per_class"][nombre]
    assert (clase["tp"], clase["fp"], clase["fn"], clase["support"]) == (1, 0, 0, 1)
    assert clase["precision"] == clase["recall"] == clase["f1"] == 1


@pytest.mark.parametrize(
    "ids_gt", [{"person": 0, "cat": 15, "dog": 16}, {"person": 1, "cat": 17, "dog": 18}]
)
def test_tres_clases_juntas_no_se_cruzan_por_los_ids_del_export(ids_gt):
    verdad = gt(
        [(1, "person", [0, 0, 10, 10]), (1, "cat", [20, 0, 10, 10]), (1, "dog", [40, 0, 10, 10])]
    )
    verdad["categories"] = [{"id": ids_gt[n], "name": n} for n in ("dog", "cat", "person")]
    for anotacion, nombre in zip(verdad["annotations"], ("person", "cat", "dog"), strict=True):
        anotacion["category_id"] = ids_gt[nombre]
    pred = [
        {"class_name": "person", "class_id": 0, "confidence": 0.9, "bbox": [0, 0, 10, 10]},
        {"class_name": "cat", "class_id": 15, "confidence": 0.8, "bbox": [20, 0, 30, 10]},
        {"class_name": "dog", "class_id": 16, "confidence": 0.7, "bbox": [40, 0, 50, 10]},
    ]

    r = evaluar(verdad, jsonl(evento(pred)))

    assert r["input_integrity_ok"]
    assert (r["micro"]["tp"], r["micro"]["fp"], r["micro"]["fn"]) == (3, 0, 0)
    assert r["micro"]["precision"] == r["micro"]["recall"] == r["micro"]["f1"] == 1
    assert all(c["tp"] == c["support"] == 1 for c in r["per_class"].values())


@pytest.mark.parametrize(("nombre", "id_export"), [("person", 1), ("cat", 17), ("dog", 18)])
def test_ids_del_export_no_se_aceptan_como_indices_del_detector(nombre, id_export):
    verdad = gt([(1, nombre, [0, 0, 10, 10])])
    pred = {"class_name": nombre, "class_id": id_export, "confidence": 0.9, "bbox": [0, 0, 10, 10]}

    r = evaluar(verdad, jsonl(evento([pred])))

    assert not r["input_integrity_ok"]
    assert r["frames"]["invalid"] == 1
    assert r["micro"]["tp"] == 0 and r["micro"]["fn"] == 1
    assert "descriptor" in r["invalid_records"][0]["errors"][0]


@pytest.mark.parametrize(
    ("a", "b", "valor"),
    [
        ([0, 0, 10, 10], [0, 0, 10, 10], 1),
        ([0, 0, 10, 10], [0, 0, 20, 10], 0.5),
        ([0, 0, 10, 10], [10, 0, 20, 10], 0),
        ([0, 0, 10, 10], [20, 20, 30, 30], 0),
        ([0, 0, 1e200, 1e200], [0, 0, 1e200, 1e200], 1),
    ],
)
def test_iou_calculado_a_mano(a, b, valor):
    assert iou(a, b) == pytest.approx(valor)
    assert iou(b, a) == pytest.approx(valor)


def test_frontera_inclusiva_y_umbral_configurable():
    verdad = gt([(1, "person", [0, 0, 10, 10])])
    pred = jsonl(evento([det(caja=(0, 0, 20, 10))]))
    assert evaluar(verdad, pred)["micro"]["tp"] == 1
    assert evaluar(verdad, pred, 0.51)["micro"]["fp"] == 1
    assert evaluar(verdad, pred, 0.51)["micro"]["fn"] == 1


def test_orden_confianza_greedy_no_optimizacion_global():
    verdad = gt([(1, "person", [0, 0, 10, 10]), (1, "person", [5, 0, 10, 10])])
    # Indice 1 tiene mayor confianza y se reserva GT1 (IoU 2/3 en empate).
    # Indice 0 solo alcanza IoU 1/3 con GT2: FP y FN, no se reoptimiza.
    r = evaluar(verdad, jsonl(evento([det(confianza=0.5), det(caja=(0, 0, 15, 10))])))
    c = r["frame_details"][0]["per_class"]["person"]
    assert (c["tp"], c["fp"], c["fn"]) == (1, 1, 1)
    assert [m["prediction_index"] for m in c["matches"]] == [1, 0]
    assert c["matches"][0]["annotation_id"] == 1


def test_se_elige_la_mejor_caja_libre_y_no_se_reutiliza():
    verdad = gt([(1, "person", [0, 0, 10, 10]), (1, "person", [2, 0, 10, 10])])
    r = evaluar(verdad, jsonl(evento([det(), det(confianza=0.8)])))
    assert r["micro"]["tp"] == 2
    assert [
        m["annotation_id"] for m in r["frame_details"][0]["per_class"]["person"]["matches"]
    ] == [1, 2]


def test_empate_confianza_y_gt_determinista_sin_mutar_entradas():
    verdad = gt([(1, "person", [0, 0, 10, 10]), (1, "person", [0, 0, 10, 10])])
    antes = copy.deepcopy(verdad)
    p = jsonl(evento([det(), det()]))
    r = evaluar(verdad, p)
    assert r == evaluar(verdad, p)
    assert verdad == antes
    assert [
        m["annotation_id"] for m in r["frame_details"][0]["per_class"]["person"]["matches"]
    ] == [1, 2]


@pytest.mark.parametrize("estado", ["error", "stale", "ilegal", "missing"])
def test_fallo_y_omision_cuentan_fn_incluso_negativas(estado):
    verdad = gt([(1, "dog", [0, 0, 10, 10])], n=2)
    p = "" if estado == "missing" else jsonl(evento(estado=estado), evento(frame=2, estado=estado))
    r = evaluar(verdad, p)
    assert r["micro"]["fn"] == 1
    assert r["micro"]["tp"] == r["micro"]["fp"] == 0
    assert r["frames"]["evaluated"] == 2
    assert r["frames"]["negative"] == 1
    assert all(c["status"] != "ok" for c in r["frame_details"])
    assert r["input_integrity_ok"] is (estado != "ilegal")


def test_error_sin_ruta_se_identifica_por_frame_id():
    ev = evento(
        estado="error", image_path=None, image_sha256=None, image_width=None, image_height=None
    )
    r = evaluar(gt([(1, "person", [0, 0, 10, 10])]), jsonl(ev))
    assert r["frames"]["error"] == 1 and r["micro"]["fn"] == 1


def test_evento_invalido_sin_ruta_conserva_la_asociacion_por_id_en_auditoria():
    ev = evento(estado="invalido", image_path=None)
    r = evaluar(gt([(1, "dog", [0, 0, 10, 10])]), jsonl(ev))
    assert r["frame_details"][0]["association"] == "frame_id"
    assert r["frames"]["invalid"] == 1 and r["micro"]["fn"] == 1


def test_sequence_id_opcional_null_en_coco_no_inventa_una_discrepancia():
    verdad = gt([(1, "person", [0, 0, 10, 10])])
    verdad["images"][0]["sequence_id"] = None
    r = evaluar(verdad, jsonl(evento([det()])))
    assert r["input_integrity_ok"] and r["micro"]["tp"] == 1


@pytest.mark.parametrize("modo", ["id", "path"])
def test_duplicados_no_seleccionan_el_mejor_resultado(modo):
    a, b = evento([det()]), evento([det()], t_capture_ms=2)
    if modo == "path":
        b["frame_id"] = "S1_otro"
    r = evaluar(gt([(1, "person", [0, 0, 10, 10])]), jsonl(a, b))
    assert not r["input_integrity_ok"]
    assert r["frames"]["duplicate"] == 1
    assert (r["micro"]["tp"], r["micro"]["fn"]) == (0, 1)


def test_desconocidos_no_entran_silenciosamente_en_las_metricas():
    r = evaluar(gt(), jsonl(evento(frame=99)))
    assert not r["input_integrity_ok"]
    assert r["frames"]["missing"] == 1
    assert r["unknown_predictions"][0]["frame_id"] == "S1_f99"


def test_ids_numericos_coco_y_cli_se_unen_por_ruta_exacta():
    verdad = gt([(1, "person", [0, 0, 10, 10])])
    ev = evento([det()], frame_id="cli_00000", sequence_id="cli")
    r = evaluar(verdad, jsonl(ev))
    assert r["micro"]["tp"] == 1
    assert r["frame_details"][0]["association"] == "path"
    assert r["frame_details"][0]["gt_frame_id"] == "S1_f1"


def test_no_se_infiere_por_nombre_base_o_numero_de_archivo():
    r = evaluar(gt(), jsonl(evento(frame_id="cli_00000", sequence_id="cli", image_path="1.jpg")))
    assert r["unknown_predictions"] and r["frames"]["missing"] == 1


def test_id_y_ruta_contradictorios_invalidan_ambas_imagenes():
    verdad = gt([(1, "person", [0, 0, 10, 10]), (2, "dog", [0, 0, 10, 10])], n=2)
    r = evaluar(verdad, jsonl(evento([det()], image_path="S1/2.jpg")))
    assert r["frames"]["invalid"] == 2 and r["micro"]["fn"] == 2


@pytest.mark.parametrize(
    "cambio",
    [
        {"image_width": 101},
        {"detections": [det(caja=(0, 0, 101, 10))]},
        {"detections": [det(confianza=float("nan"))]},
        {"detections": [det(confianza=2)]},
        {"detections": [{**det(), "class_id": 1}]},
        {"detections": [{**det(), "class_name": "tv"}]},
        {"frame_id": "sin_prefijo"},
        {"image_path": "../S1/1.jpg"},
    ],
)
def test_eventos_invalidos_no_producen_tp(cambio):
    r = evaluar(gt([(1, "person", [0, 0, 10, 10])]), jsonl(evento([det()], **cambio)))
    assert not r["input_integrity_ok"]
    assert r["micro"]["tp"] == 0 and r["micro"]["fn"] == 1


@pytest.mark.parametrize(
    "campo,valor",
    [
        ("run_id", "otro"),
        ("model_sha256", "d" * 64),
        ("config_sha256", "e" * 64),
        ("synthetic", False),
    ],
)
def test_no_se_mezclan_corridas_modelos_configs_o_origenes(campo, valor):
    r = evaluar(gt(n=2), jsonl(evento(), evento(frame=2, **{campo: valor})))
    assert not r["input_integrity_ok"] and r["frames"]["invalid"] == 2


def test_reloj_no_creciente_se_informa():
    r = evaluar(gt(n=2), jsonl(evento(), evento(frame=2, t_capture_ms=0)))
    assert r["frames"]["invalid"] == 1
    assert "reloj" in str(r["invalid_records"])


@pytest.mark.parametrize("contenido", ["{", "[]", '{"frame_id":"a","frame_id":"b"}', "null"])
def test_jsonl_malformado_se_reporta_y_no_oculta_fn(contenido):
    r = evaluar(gt([(1, "dog", [0, 0, 10, 10])]), contenido)
    assert r["micro"]["fn"] == 1 and r["invalid_records"]


@pytest.mark.parametrize(
    "cambio",
    [
        lambda d: d.pop("images"),
        lambda d: d.update(images=[]),
        lambda d: d["images"].append(d["images"][0]),
        lambda d: d["images"][0].update(width=0),
        lambda d: d["categories"].append(d["categories"][0]),
        lambda d: d["annotations"][0].update(image_id=99),
        lambda d: d["annotations"][0].update(category_id=99),
        lambda d: d["annotations"][0].update(bbox=[0, 0, -1, 1]),
        lambda d: d["annotations"][0].update(bbox=[0, 0, float("inf"), 1]),
        lambda d: d["annotations"][0].update(iscrowd=1),
        lambda d: d["annotations"].append(d["annotations"][0]),
    ],
)
def test_gt_invalido_se_rechaza(cambio):
    verdad = gt([(1, "person", [0, 0, 10, 10])])
    cambio(verdad)
    with pytest.raises(EntradaError):
        evaluar(verdad, "")


@pytest.mark.parametrize("info", [None, [], "SINTETICO", {"synthetic": "false"}])
def test_info_coco_invalida_se_rechaza(info):
    verdad = gt()
    verdad["info"] = info
    with pytest.raises(EntradaError):
        evaluar(verdad, "")


def test_clases_sin_categorias_y_gt_no_evaluado_no_se_ocultan():
    verdad = gt()
    verdad["categories"] = [{"id": 99, "name": "tv"}]
    verdad["annotations"] = [{"id": 1, "image_id": 1, "category_id": 99, "bbox": [0, 0, 10, 10]}]
    r = evaluar(verdad, jsonl(evento()))
    assert set(r["per_class"]) == set(CLASES)
    assert all(c["support"] == 0 for c in r["per_class"].values())


@pytest.mark.parametrize("valor", [0, -1, 1.1, float("nan"), float("inf"), True])
def test_umbral_invalido(valor):
    with pytest.raises(EntradaError):
        evaluar(gt(), "", valor)


def test_ceros_con_avisos_y_clases_sin_soporte_visibles():
    r = evaluar(gt(), jsonl(evento()))
    for clase in (*CLASES, "micro"):
        c = r["micro"] if clase == "micro" else r["per_class"][clase]
        assert c["precision"] == c["recall"] == c["f1"] == c["support"] == 0
        assert any(f"{clase}.precision" in aviso for aviso in r["warnings"])
        assert any(f"{clase}.recall" in aviso for aviso in r["warnings"])
        assert any(f"{clase}.f1" in aviso for aviso in r["warnings"])


def test_otras_clases_no_se_confunden_con_los_obstaculos():
    ev = evento([{**det(), "class_name": "tv", "class_id": 72}])
    r = evaluar(gt(), jsonl(ev))
    assert r["input_integrity_ok"] and r["micro"]["fp"] == 0
    assert r["frame_details"][0]["ignored_detections"] == 1


def manifiesto():
    return (
        "sequence_id,frame_id,t_capture_ms,ruta,ancho,alto,sha256,estado_esperado_via\n"
        + f"S1,S1_f1,0,S1/1.jpg,100,100,{'a' * 64},libre\n"
    )


def test_manifiesto_coteja_ruta_dimensiones_hash_e_identidad():
    verdad = gt()
    del verdad["images"][0]["frame_id"]
    r = evaluar(verdad, jsonl(evento()), manifiesto=manifiesto())
    assert r["input_integrity_ok"] and r["frame_details"][0]["association"] == "frame_id"
    r = evaluar(gt(), jsonl(evento(image_sha256="d" * 64)), manifiesto=manifiesto())
    assert not r["input_integrity_ok"] and r["frames"]["invalid"] == 1


@pytest.mark.parametrize(
    "texto",
    [
        "ruta\nS1/1.jpg\n",
        manifiesto().replace("100,100", "99,100"),
        manifiesto().replace("S1/1.jpg", "S1/otra.jpg"),
        manifiesto().splitlines()[0],
    ],
)
def test_manifiesto_incompatible_se_rechaza(texto):
    with pytest.raises(EntradaError):
        evaluar(gt(), "", manifiesto=texto)


def test_fixture_sintetico_resultado_manual_completo():
    verdad = json.loads((FIXTURES / "gt.coco.json").read_text(encoding="utf-8"))
    r = evaluar(verdad, (FIXTURES / "predicciones.jsonl").read_text(encoding="utf-8"))
    assert r["evidence"] == "SINTETICA" and r["input_integrity_ok"]
    assert r["frames"] == {
        "expected": 6,
        "evaluated": 6,
        "ok": 4,
        "negative": 1,
        "missing": 1,
        "error": 1,
        "stale": 0,
        "invalid": 0,
        "duplicate": 0,
    }
    assert (r["micro"]["tp"], r["micro"]["fp"], r["micro"]["fn"]) == (1, 3, 4)
    assert r["micro"]["precision"] == pytest.approx(1 / 4)
    assert r["micro"]["recall"] == pytest.approx(1 / 5)
    assert r["micro"]["f1"] == pytest.approx(2 / 9)
    assert r["per_class"]["person"]["f1"] == 0.5
    assert r["per_class"]["dog"]["support"] == 2
    assert r["per_class"]["cat"]["fp"] == 2


def test_cli_modulo_reproducible_hashes_y_sin_sobrescritura(tmp_path):
    entorno = {
        **os.environ,
        "PYTHONPATH": str(Path(__file__).parents[1] / "src"),
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    comunes = [
        sys.executable,
        "-B",
        "-m",
        "p5.metricas",
        "--gt",
        str(FIXTURES / "gt.coco.json"),
        "--pred",
        str(FIXTURES / "predicciones.jsonl"),
        "--iou",
        "0.5",
        "--cuadros-esperados",
        "6",
    ]
    resultados = []
    for salida in (tmp_path / "a", tmp_path / "b"):
        p = subprocess.run(
            [*comunes, "--salida", str(salida)],
            capture_output=True,
            text=True,
            env=entorno,
            check=False,
            timeout=15,
        )
        assert p.returncode == 0, p.stderr
        resultados.append((salida / "metricas.json").read_bytes())
    assert resultados[0] == resultados[1]
    reporte = json.loads(resultados[0])
    assert (
        reporte["inputs"]["gt"]["sha256"]
        == hashlib.sha256((FIXTURES / "gt.coco.json").read_bytes()).hexdigest()
    )
    assert reporte["prediction_runs"][0]["run_id"] == "SINTETICO"
    assert main([*comunes[4:], "--salida", str(tmp_path / "a")]) == 2
    assert (tmp_path / "a" / "metricas.json").read_bytes() == resultados[0]


def test_cli_errores_entrada_y_reporte_degradado(tmp_path, capsys):
    coco = tmp_path / "gt.json"
    pred = tmp_path / "pred.jsonl"
    coco.write_text(json.dumps(gt()), encoding="utf-8")
    pred.write_text("{", encoding="utf-8")
    args = ["--gt", str(coco), "--pred", str(pred), "--salida", str(tmp_path / "out")]
    assert main(args) == 1
    r = json.loads((tmp_path / "out" / "metricas.json").read_text(encoding="utf-8"))
    assert not r["input_integrity_ok"] and r["invalid_records"]
    coco.write_text('{"images":[],"images":[]}', encoding="utf-8")
    assert main(args) == 2
    assert "clave JSON repetida" in capsys.readouterr().err


def test_cli_identidad_no_finita_se_reporta_sin_romper_serializacion(tmp_path):
    coco, pred = tmp_path / "gt.json", tmp_path / "pred.jsonl"
    coco.write_text(json.dumps(gt()), encoding="utf-8")
    pred.write_text(jsonl(evento(frame_id=float("nan"))), encoding="utf-8")
    assert main(["--gt", str(coco), "--pred", str(pred), "--salida", str(tmp_path)]) == 1
    r = json.loads((tmp_path / "metricas.json").read_text(encoding="utf-8"))
    assert r["invalid_records"][0]["frame_id"] is None


def test_cli_manifiesto_y_gt_sin_extensiones(tmp_path):
    verdad = gt([(1, "person", [0, 0, 10, 10])])
    del verdad["images"][0]["frame_id"]
    del verdad["images"][0]["sequence_id"]
    coco, pred, manifest = tmp_path / "gt.json", tmp_path / "pred.jsonl", tmp_path / "manifest.csv"
    coco.write_text(json.dumps(verdad), encoding="utf-8")
    pred.write_text(
        jsonl(evento([det()], frame_id="cli_00000", sequence_id="cli")), encoding="utf-8"
    )
    manifest.write_text(manifiesto(), encoding="utf-8")
    assert (
        main(
            [
                "--gt",
                str(coco),
                "--pred",
                str(pred),
                "--manifiesto",
                str(manifest),
                "--salida",
                str(tmp_path / "out"),
            ]
        )
        == 0
    )
    r = json.loads((tmp_path / "out" / "metricas.json").read_text(encoding="utf-8"))
    assert r["micro"]["tp"] == 1
    assert r["inputs"]["manifest"]["sha256"] == hashlib.sha256(manifest.read_bytes()).hexdigest()
    assert r["frame_details"][0]["gt_frame_id"] == "S1_f1"


def test_clases_coinciden_con_politica_integrada():
    import yaml

    politica = Path(__file__).parents[1] / "config" / "politica.yaml"
    assert set(yaml.safe_load(politica.read_text(encoding="utf-8"))["clases_obstaculo"]) == set(
        CLASES
    )


@pytest.mark.parametrize("numero", [0, -1, 78, 84])
def test_cli_no_acepta_otra_seleccion_si_se_exige_conteo(numero, tmp_path):
    args = [
        "--gt",
        str(FIXTURES / "gt.coco.json"),
        "--pred",
        str(FIXTURES / "predicciones.jsonl"),
        "--salida",
        str(tmp_path),
        "--cuadros-esperados",
        str(numero),
    ]
    assert main(args) == 2
    assert not (tmp_path / "metricas.json").exists()
