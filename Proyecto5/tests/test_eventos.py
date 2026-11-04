"""Pruebas de la exportacion de eventos por secuencia para el runner (P5-14)."""

from __future__ import annotations

import csv
import json
from itertools import pairwise
from pathlib import Path

import pytest

from exportar_eventos import EventosError, exportar

RAIZ = Path(__file__).resolve().parents[1]
RUN = RAIZ / "config" / "ejemplos" / "run_header.json"
EVENTO = RAIZ / "config" / "ejemplos" / "ok.json"
EVENTOS = RAIZ / "datos" / "eventos"
TABLA = RAIZ / "docs" / "compatibilidad_ids_consumidores_p5_05b.csv"


def _evento(sequence_id: str, frame_id: str, t_ms: float) -> dict:
    datos = json.loads(EVENTO.read_text(encoding="utf-8"))
    datos["sequence_id"] = sequence_id
    datos["frame_id"] = frame_id
    datos["t_capture_ms"] = t_ms
    datos["t_capture_origen_ms"] = t_ms
    return datos


def _escribir_jsonl(ruta: Path, eventos: list[dict]) -> None:
    ruta.write_text(
        "".join(json.dumps(evento, ensure_ascii=False) + "\n" for evento in eventos),
        encoding="utf-8",
    )


def test_exporta_por_secuencia_y_procedencia(tmp_path):
    detecciones = tmp_path / "detecciones.jsonl"
    _escribir_jsonl(
        detecciones,
        [
            _evento("seq01", "seq01_f0007", 700),
            _evento("seq01", "seq01_f0008", 800),
            _evento("seq02", "seq02_f0001", 900),
        ],
    )
    salida = tmp_path / "eventos"

    origen = exportar(detecciones, RUN, salida)

    assert len((salida / "seq01.jsonl").read_text().splitlines()) == 2
    assert len((salida / "seq02.jsonl").read_text().splitlines()) == 1
    assert origen["total"] == 3
    assert origen["secuencias"] == {"seq01": 2, "seq02": 1}
    assert origen["modo"] == "desconocido"
    assert origen["cortes_total"] is None
    assert origen["detecciones_sha256"]


def test_no_sobrescribe_sin_force(tmp_path):
    detecciones = tmp_path / "detecciones.jsonl"
    _escribir_jsonl(detecciones, [_evento("seq01", "seq01_f0007", 700)])
    salida = tmp_path / "eventos"
    exportar(detecciones, RUN, salida)

    _escribir_jsonl(detecciones, [_evento("seq01", "seq01_f0007", 800)])  # mismo frame, otro tiempo
    with pytest.raises(EventosError, match="--force"):
        exportar(detecciones, RUN, salida)

    exportar(detecciones, RUN, salida, force=True)
    assert '"t_capture_ms": 800' in (salida / "seq01.jsonl").read_text()


def test_evento_invalido_falla(tmp_path):
    detecciones = tmp_path / "detecciones.jsonl"
    datos = _evento("seq01", "seq01_f0007", 700)
    del datos["image_width"]
    _escribir_jsonl(detecciones, [datos])

    with pytest.raises(EventosError, match="evento invalido"):
        exportar(detecciones, RUN, tmp_path / "eventos")


def test_run_id_distinto_falla(tmp_path):
    detecciones = tmp_path / "detecciones.jsonl"
    datos = _evento("seq01", "seq01_f0007", 700)
    datos["run_id"] = "run-otro"
    _escribir_jsonl(detecciones, [datos])

    with pytest.raises(EventosError, match="run_id"):
        exportar(detecciones, RUN, tmp_path / "eventos")


def test_cortes_se_copian_en_la_procedencia(tmp_path):
    detecciones = tmp_path / "detecciones.jsonl"
    _escribir_jsonl(detecciones, [_evento("seq01", "seq01_f0007", 700)])
    cortes = tmp_path / "cortes.json"
    cortes.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "modo": "cortes_sesion",
                "replay_dt_ms": 100,
                "total": 1,
                "cortes": [{"frame_previo": "seq01_f0006", "frame_siguiente": "seq01_f0007"}],
            }
        ),
        encoding="utf-8",
    )

    origen = exportar(detecciones, RUN, tmp_path / "eventos", cortes=cortes)

    assert origen["modo"] == "cortes_sesion"
    assert origen["cortes_total"] == 1
    assert origen["cortes_sha256"]


def test_eventos_reales_exportados():
    if not (EVENTOS / "eventos_origen.json").is_file():
        pytest.skip("faltan datos/eventos; se generan con scripts/exportar_eventos.py")

    origen = json.loads((EVENTOS / "eventos_origen.json").read_text(encoding="utf-8"))
    assert origen["total"] == 78
    assert origen["modo"] == "cortes_sesion"
    assert origen["cortes_total"] == 5
    assert origen["secuencias"] == {
        "S1": 12,
        "S2": 17,
        "S3": 13,
        "S4": 12,
        "S5": 12,
        "S6": 12,
    }

    with TABLA.open(encoding="utf-8", newline="") as archivo:
        tabla = list(csv.DictReader(archivo))
    esperados = {
        secuencia: [
            fila["frame_id_reproductor_P514_cache"]
            for fila in tabla
            if fila["sequence_id"] == secuencia
        ]
        for secuencia in origen["secuencias"]
    }

    vistos: set[str] = set()
    for secuencia, total in origen["secuencias"].items():
        lineas = [
            json.loads(linea)
            for linea in (EVENTOS / f"{secuencia}.jsonl").read_text(encoding="utf-8").splitlines()
            if linea
        ]
        assert len(lineas) == total
        assert [linea["frame_id"] for linea in lineas] == esperados[secuencia]
        assert {linea["run_id"] for linea in lineas} == {origen["run_id"]}
        assert all(a["t_capture_ms"] < b["t_capture_ms"] for a, b in pairwise(lineas))
        vistos.update(linea["frame_id"] for linea in lineas)

    assert len(vistos) == 78
