"""Integracion monitor -> SQLite -> exportacion -> recalculo -> portal con un detector de prueba.

El detector falso solo existe en pruebas (no hay rama en el codigo de produccion que lo use);
la inferencia real se prueba en test_modelo_real.py cuando el modelo esta descargado.
"""

import json
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

from p5.contrato import Detection
from p6 import almacen, recalcular
from p6.config import cargar
from p6.detector import ResultadoInferencia
from p6.fuente import SecuenciaFuente
from p6.monitor import Monitor
from p6.portal.app import crear_app

CFG = Path(__file__).resolve().parents[1] / "config" / "monitoreo.yaml"
SCORES = [[0.9], [0.1], [0.12, 0.05], [], [0.3], [0.2], [0.15], [0.6], [0.1], [0.11], [0.9], [0.8]]


class DetectorFalso:
    nombre = "falso"
    synthetic = True
    model_sha256 = "m" * 64
    detector_config_sha256 = "d" * 64
    modelo_archivo = "falso.onnx"

    def __init__(self):
        self.i = 0

    def inferir(self, ruta):
        s = SCORES[self.i]
        self.i += 1
        dets = [Detection("cat", 15, x, (1.0, 1.0, 5.0, 5.0)) for x in s]
        return ResultadoInferencia(8, 8, dets, 0.1, 0.1, 1.0 + self.i, 0.1)


def test_flujo_completo(tmp_path, monkeypatch):
    for i in range(len(SCORES)):
        Image.new("RGB", (8, 8)).save(tmp_path / f"{i}.jpg")
    (tmp_path / "roto.jpg").write_bytes(b"no es imagen")
    man = tmp_path / "m.csv"
    man.write_text("path,sha256\n" + "".join(f"{i}.jpg,\n" for i in range(len(SCORES))))
    cfg = cargar(CFG)
    con = almacen.conectar(tmp_path / "db.sqlite")
    mon = Monitor(cfg, DetectorFalso(), con, "t1", tmp_path / "cap")
    fuente = SecuenciaFuente(man, tmp_path, "src", fps=1000)
    evs = [mon.procesar(f) for f in fuente.frames()]
    mon.cerrar_ventana()
    zonas = [e["zona"] for e in evs]
    assert zonas[:4] == ["aceptada", "baja", "baja", None]
    assert evs[3]["estado"] == "sin_detecciones" and evs[3]["score_principal"] is None
    # ventana 0 (10 frames): 9 puntuados, 6 bajos -> alerta de baja confianza
    al = list(mon.alertas.values())
    assert al and al[0]["rule_id"] == "baja-confianza-v1"
    vinculados = [r[0] for r in con.execute("SELECT event_id FROM alerta_eventos")]
    assert all(next(e for e in evs if e["event_id"] == i)["zona"] == "baja" for i in vinculados)
    # capturas: bajas y dudas siempre; existen y su sha coincide
    for e in evs:
        if e["zona"] in ("baja", "duda"):
            assert e["image_ref"] and e["image_sha256"]
    m = mon.metricas_run()
    assert m["G4_proporcion_baja"]["proporcion"] == 6 / 11
    assert m["G6_version_esperada"]["proporcion"] == 1.0
    # el portal muestra eventos y alertas
    con.execute(
        "INSERT INTO runs (run_id, escenario, inicio, metricas_json, entorno_json, "
        "config_sha256, model_sha256) VALUES ('t1','T','x',?, '{}', ?, ?)",
        (json.dumps(m), cfg.config_sha256, "m" * 64),
    )
    con.commit()
    c = TestClient(crear_app(tmp_path / "db.sqlite", raiz=tmp_path))
    r = c.get("/alertas")
    assert r.status_code == 200 and "baja-confianza-v1" in r.text and "Revisar" in r.text
    r = c.get(f"/alertas/{al[0]['alert_id']}")
    assert vinculados[0] in r.text
    assert c.get("/eventos?zona=baja").text.count('href="/eventos/t1-e') == 6
    assert "No hay eventos" in c.get("/eventos?estado=error").text
    assert c.get("/eventos/inexistente").status_code == 404
    assert c.get("/archivo/../../etc/passwd").status_code == 404


def test_imagen_corrupta_es_error_sin_score(tmp_path):
    (tmp_path / "roto.jpg").write_bytes(b"no es imagen")
    man = tmp_path / "m.csv"
    man.write_text("path,sha256\nroto.jpg,\nfalta.jpg,\n")

    class DetectorQueLee(DetectorFalso):
        def inferir(self, ruta):
            from p6.detector import p5det

            p5det.leer_imagen(ruta)
            return super().inferir(ruta)

    mon = Monitor(
        cargar(CFG), DetectorQueLee(), almacen.conectar(tmp_path / "d.db"), "t2", tmp_path / "cap"
    )
    evs = [mon.procesar(f) for f in SecuenciaFuente(man, tmp_path, "s", 1000).frames()]
    assert [e["estado"] for e in evs] == ["error", "error"]
    assert evs[0]["score_principal"] is None and evs[0]["image_ref"]  # se captura el error
    assert "ausente" in evs[1]["error_msg"]


def test_recalcular_detecta_alteracion(tmp_path):
    test_flujo_completo(tmp_path, None)
    # exportar y alterar una zona: el recalculo debe fallar
    con = almacen.conectar(tmp_path / "db.sqlite")
    con.execute(
        "UPDATE runs SET git_commit='x', manifiesto='m', manifiesto_sha256='s', "
        "detector_config_sha256=?",
        ("d" * 64,),
    )
    con.commit()
    almacen.exportar_run(con, "t1", tmp_path / "exp")
    r = recalcular.recalcular(tmp_path / "exp", CFG)
    nombres = {c["comprobacion"] for c in r["fallidas"]}
    assert "frames con zona/score inconsistente" not in nombres
    ev = (
        (tmp_path / "exp" / "eventos.jsonl")
        .read_text()
        .replace('"zona": "baja"', '"zona": "aceptada"', 1)
    )
    (tmp_path / "exp" / "eventos.jsonl").write_text(ev)
    r = recalcular.recalcular(tmp_path / "exp", CFG)
    assert "frames con zona/score inconsistente" in {c["comprobacion"] for c in r["fallidas"]}
