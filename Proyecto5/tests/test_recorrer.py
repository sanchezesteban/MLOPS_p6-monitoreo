"""Recorrido integral P5-14 con detector simulado y detector que falla (C9)."""

from __future__ import annotations

import csv
import json
from itertools import pairwise
from pathlib import Path

import pytest
import yaml

from p5.contrato import validar_run_header
from p5.detector import DetectorSimulado, Frame
from p5.recorrer import (
    RecorridoInvalidoError,
    hueco_entre_secuencias,
    leer_manifiesto,
    main,
    normalizar_tiempos,
    sha256_archivo,
)
from p5.watchdog import cargar_config as cargar_config_watchdog

RAIZ = Path(__file__).resolve().parents[1]
DATOS = RAIZ / "datos" / "simulacion"
DATOS_EVAL = RAIZ / "datos" / "evaluacion"
CAPTURAS = DATOS_EVAL / "capturas.csv"
CONFIG = RAIZ / "config" / "politica.yaml"
WATCHDOG = RAIZ / "config" / "watchdog.yaml"
DETECTOR_CONFIG = RAIZ / "config" / "detector.yaml"
MODELO = RAIZ / "modelo" / "yolox_nano.onnx"
HASH = "0" * 64


def _datos(tmp_path: Path, filas: list[dict]) -> Path:
    datos = tmp_path / "datos"
    datos.mkdir()
    (datos / "cuadro.png").write_bytes(b"png de prueba")
    with (datos / "manifiesto.csv").open("w", encoding="utf-8", newline="") as f:
        escritor = csv.DictWriter(
            f,
            fieldnames=[
                "sequence_id",
                "frame_id",
                "t_capture_ms",
                "image_path",
                "image_width",
                "image_height",
                "status",
                "error_msg",
            ],
            lineterminator="\n",
        )
        escritor.writeheader()
        escritor.writerows(filas)
    (datos / "detecciones.yaml").write_text("frames: {}\n", encoding="utf-8")
    return datos


def _fila(frame_id: str, t_ms: float, status: str = "ok", error: str = "") -> dict:
    return {
        "sequence_id": frame_id.split("_")[0],
        "frame_id": frame_id,
        "t_capture_ms": t_ms,
        "image_path": "cuadro.png",
        "image_width": 640,
        "image_height": 480,
        "status": status,
        "error_msg": error,
    }


class DetectorRoto:
    nombre = "roto"
    model_sha256 = HASH
    synthetic = True

    def detectar(self, frame: Frame):
        raise RuntimeError("fallo inducido del detector")


def _lineas(ruta: Path) -> list[dict]:
    return [json.loads(linea) for linea in ruta.read_text(encoding="utf-8").splitlines()]


def test_detector_simulado_lee_el_guion_y_los_cuadros_vacios():
    detector = DetectorSimulado.desde_yaml(DATOS / "detecciones.yaml")
    frame = Frame("seq02", "seq02_f0003", 200, "cuadro.png", 640, 480, HASH)

    detecciones = detector.detectar(frame)

    assert len(detecciones) == 1
    assert detecciones[0].class_name == "person"
    assert detector.detectar(Frame("seq01", "seq01_f0001", 0, "x.png", 640, 480, HASH)) == []


def test_recorrido_simulado_del_repo(tmp_path):
    salida = tmp_path / "salida"
    codigo = main(
        [
            "--datos",
            str(DATOS),
            "--config",
            str(CONFIG),
            "--watchdog-config",
            str(WATCHDOG),
            "--salida",
            str(salida),
            "--run-id",
            "run-sim-test",
            "--commit",
            "commit-test",
        ],
    )

    assert codigo == 0
    eventos = _lineas(salida / "detecciones.jsonl")
    decisiones = _lineas(salida / "decisiones.jsonl")
    comandos = _lineas(salida / "comandos.jsonl")
    run = json.loads((salida / "run.json").read_text(encoding="utf-8"))

    assert len(eventos) == 54
    assert len(decisiones) == 54 + 6  # una por cuadro + seis cortes de secuencia
    assert len(comandos) == 55 + 6  # 54 cuadros + STOP de cierre + 6 cortes de secuencia
    assert [e["status"] for e in eventos[-2:]] == ["error", "stale"]
    assert all(e["run_id"] == "run-sim-test" for e in eventos)
    assert {e["frame_id"] for e in eventos} <= {c["frame_id"] for c in comandos}
    assert comandos[-1]["event"] == "shutdown"
    assert eventos[1]["t_capture_ms"] - eventos[0]["t_capture_ms"] == 100
    assert eventos[8]["t_capture_ms"] - eventos[7]["t_capture_ms"] == 400
    cortes = [c for c in comandos if c["event"] == "watchdog"]
    assert len(cortes) == 6
    assert all(c["frame_id"] is None and c["action"] == "STOP" for c in cortes)
    assert run["data_manifest_sha256"] == sha256_archivo(DATOS / "manifiesto.csv")
    assert run["config_sha256"] == sha256_archivo(CONFIG)
    assert run["replay_dt_ms"] == 100
    assert eventos[0]["t_capture_origen_ms"] == 0
    assert eventos[8]["t_capture_origen_ms"] == 800  # primer cuadro de seq02
    validar_run_header(run)


def test_acciones_representan_c1_c5_y_c7(tmp_path):
    salida = tmp_path / "salida"
    assert (
        main(
            [
                "--datos",
                str(DATOS),
                "--config",
                str(CONFIG),
                "--watchdog-config",
                str(WATCHDOG),
                "--salida",
                str(salida),
                "--run-id",
                "run-casos",
                "--commit",
                "test",
            ],
        )
        == 0
    )
    comandos = _lineas(salida / "comandos.jsonl")
    por_frame = {c["frame_id"]: c["action"] for c in comandos if c["frame_id"]}

    assert all(por_frame[f"seq01_f{i:04d}"] == "FORWARD" for i in range(3, 9))
    assert all(por_frame[f"seq02_f{i:04d}"] == "STOP" for i in range(3, 9))
    assert all(por_frame[f"seq03_f{i:04d}"] == "STEER_RIGHT" for i in range(3, 9))
    assert all(por_frame[f"seq04_f{i:04d}"] == "STEER_LEFT" for i in range(3, 9))
    assert all(por_frame[f"seq05_f{i:04d}"] == "STOP" for i in range(3, 9))
    # C7: obstaculo, luego reanuda tras la histeresis de tres cuadros despejados.
    assert por_frame["seq06_f0003"] == "STOP"
    assert por_frame["seq06_f0008"] == "FORWARD"


def test_detector_que_falla_queda_como_error_y_stop(tmp_path):
    datos = _datos(tmp_path, [_fila("seqX_f0001", 0)])
    salida = tmp_path / "salida"
    codigo = main(
        [
            "--datos",
            str(datos),
            "--config",
            str(CONFIG),
            "--watchdog-config",
            str(WATCHDOG),
            "--salida",
            str(salida),
            "--run-id",
            "run-fallo",
            "--commit",
            "test",
        ],
        fabrica_detector=lambda _: DetectorRoto(),
    )
    eventos = _lineas(salida / "detecciones.jsonl")
    comandos = _lineas(salida / "comandos.jsonl")

    assert codigo == 0
    assert eventos[0]["status"] == "error"
    assert "detector:" in eventos[0]["error_msg"]
    assert "fallo inducido" in eventos[0]["error_msg"]
    assert comandos[0]["action"] == "STOP"


def test_manifiesto_con_imagen_faltante_falla(tmp_path):
    datos = _datos(tmp_path, [_fila("seqX_f0001", 0)])
    (datos / "cuadro.png").unlink()
    codigo = main(
        [
            "--datos",
            str(datos),
            "--config",
            str(CONFIG),
            "--watchdog-config",
            str(WATCHDOG),
            "--salida",
            str(tmp_path / "salida"),
            "--run-id",
            "run-fallo",
            "--commit",
            "test",
        ],
    )
    assert codigo == 1


def test_salida_existente_no_se_sobrescribe(tmp_path):
    datos = _datos(tmp_path, [_fila("seqX_f0001", 0)])
    salida = tmp_path / "salida"
    salida.mkdir()
    codigo = main(
        [
            "--datos",
            str(datos),
            "--config",
            str(CONFIG),
            "--watchdog-config",
            str(WATCHDOG),
            "--salida",
            str(salida),
            "--run-id",
            "run-fallo",
            "--commit",
            "test",
        ],
    )
    assert codigo == 1


def test_detector_real_sin_pesos_es_error_claro(tmp_path):
    datos = _datos(tmp_path, [_fila("seqX_f0001", 0)])
    codigo = main(
        [
            "--datos",
            str(datos),
            "--config",
            str(CONFIG),
            "--watchdog-config",
            str(WATCHDOG),
            "--salida",
            str(tmp_path / "salida"),
            "--detector",
            "real",
            "--modelo",
            str(tmp_path / "no-existe.onnx"),
            "--run-id",
            "run-real",
            "--commit",
            "test",
        ],
    )
    assert codigo == 1


def test_manifiesto_79_genera_frame_id_con_prefijo_y_tiempos_monotonos():
    frames = leer_manifiesto(CAPTURAS, DATOS_EVAL)
    cfg = cargar_config_watchdog(WATCHDOG)
    normalizados = normalizar_tiempos(frames, 100.0, hueco_entre_secuencias(cfg, 100.0))

    assert len(frames) == 78
    assert {f.sequence_id for f in frames} == {"S1", "S2", "S3", "S4", "S5", "S6"}
    first = {}
    for frame in frames:
        first.setdefault(frame.sequence_id, frame)
    assert first["S1"].frame_id == "S1_f0001"
    assert first["S2"].frame_id == "S2_f0001"
    assert all(f.frame_id.startswith(f"{f.sequence_id}_f") for f in frames)
    assert all(a.t_capture_ms < b.t_capture_ms for a, b in pairwise(normalizados))
    assert all(f.t_capture_origen_ms == f.t_capture_ms for f in frames)


def test_replay_usa_cien_ms_dentro_de_secuencia_y_hueco_mayor_al_watchdog():
    frames = leer_manifiesto(CAPTURAS, DATOS_EVAL)
    cfg = cargar_config_watchdog(WATCHDOG)
    normalizados = normalizar_tiempos(frames, 100.0, hueco_entre_secuencias(cfg, 100.0))

    assert normalizados[0].t_capture_ms == 0
    for previo, actual in pairwise(normalizados):
        delta = actual.t_capture_ms - previo.t_capture_ms
        if actual.sequence_id == previo.sequence_id:
            assert delta == 100.0
        else:
            assert delta > cfg.max_edad_ms
            assert delta > cfg.vencimiento_ms

    primeros = [normalizados[0]] + [
        actual
        for previo, actual in pairwise(normalizados)
        if actual.sequence_id != previo.sequence_id
    ]
    assert len(primeros) == 6  # una por secuencia S1-S6
    assert primeros[0].t_capture_ms == 0
    assert [f.t_capture_origen_ms for f in normalizados] == [f.t_capture_ms for f in frames]


def test_replay_dt_invalido_se_rechaza():
    frames = leer_manifiesto(CAPTURAS, DATOS_EVAL)
    with pytest.raises(RecorridoInvalidoError):
        normalizar_tiempos(frames, 0.0, 400.0)


@pytest.mark.skipif(not MODELO.is_file(), reason="faltan los pesos descargados del detector")
def test_recorrido_real_una_imagen_de_s1(tmp_path):
    with CAPTURAS.open(encoding="utf-8", newline="") as f:
        lector = csv.DictReader(f)
        campos = lector.fieldnames
        fila = next(lector)
    manifiesto = tmp_path / "una.csv"
    with manifiesto.open("w", encoding="utf-8", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=campos, lineterminator="\n")
        escritor.writeheader()
        escritor.writerow(fila)

    salida = tmp_path / "salida"
    codigo = main(
        [
            "--datos",
            str(DATOS_EVAL),
            "--manifiesto",
            str(manifiesto),
            "--config",
            str(CONFIG),
            "--watchdog-config",
            str(WATCHDOG),
            "--detector",
            "real",
            "--detector-config",
            str(DETECTOR_CONFIG),
            "--replay-dt-ms",
            "100",
            "--salida",
            str(salida),
            "--run-id",
            "run-real-una",
            "--commit",
            "test",
        ],
    )
    eventos = _lineas(salida / "detecciones.jsonl")
    run = json.loads((salida / "run.json").read_text(encoding="utf-8"))

    assert codigo == 0
    assert len(eventos) == 1
    assert eventos[0]["frame_id"] == "S1_f0001"
    assert eventos[0]["status"] == "ok"
    assert (eventos[0]["image_width"], eventos[0]["image_height"]) == (400, 296)
    assert eventos[0]["t_capture_origen_ms"] == 0
    assert run["replay_dt_ms"] == 100
    assert run["model_sha256"] == "c789161ed43c8269fcd4e67c67eeeb4e80c622da2eb296a20bc6007bd18a0b7d"


def test_manifiesto_y_guion_del_repo_son_consistentes():
    with (DATOS / "manifiesto.csv").open(encoding="utf-8", newline="") as f:
        filas = list(csv.DictReader(f))
    guion = yaml.safe_load((DATOS / "detecciones.yaml").read_text(encoding="utf-8"))["frames"]
    ids = {fila["frame_id"] for fila in filas}
    assert len(ids) == len(filas) == 54
    assert set(guion) <= ids
    assert all(fila["image_width"] == "640" for fila in filas)
