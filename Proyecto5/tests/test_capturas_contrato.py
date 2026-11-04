"""Compatibilidad con P5-01; fixtures simuladas, sin datos reales ni detector."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import capturas_core as core

contract = pytest.importorskip("p5.contrato", reason="Requiere las dependencias fusionadas de main")


def captured_row(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "jpeg_dimensions", lambda _data: (400, 296))
    with core.CaptureStore(tmp_path, "TEST-ONLY-session") as store:
        store.save(b"TEST ONLY - not a camera JPEG", "S1", 1_000_000_000, "despejado", False)
    return core.read_rows(tmp_path)[0]


def event_from_row(row):
    example = contract.SCHEMAS_DIR.parent / "ejemplos" / "vacio.json"
    data = json.loads(example.read_text(encoding="utf-8"))
    data.update(
        sequence_id=row["sequence_id"],
        frame_id=row["frame_id"],
        t_capture_ms=int(row["t_capture_ms"]),
        image_path=row["path"],
        image_sha256=row["sha256"],
        image_width=int(row["image_width"]),
        image_height=int(row["image_height"]),
        synthetic=True,
    )
    return contract.validar_evento(data)


def test_new_capture_id_and_path_are_compatible_with_upstream_contract(tmp_path, monkeypatch):
    event = event_from_row(captured_row(tmp_path, monkeypatch))
    assert contract.validar_secuencia([event]) == []


def test_legacy_uuid_requires_an_explicit_event_mapping(tmp_path, monkeypatch):
    row = captured_row(tmp_path, monkeypatch)
    row["frame_id"] = "a" * 32
    errors = contract.validar_secuencia([event_from_row(row)])
    assert any("frame_id no empieza" in error for error in errors)


def test_rotated_dimensions_use_contract_thirds_and_lower_half():
    # Cajas de prueba; no son anotaciones de los JPEG del dataset.
    assert contract.zonas_ocupadas((10, 150, 120, 250), 400) == {"izquierda"}
    assert contract.zonas_ocupadas((110, 150, 140, 250), 400) == {"izquierda", "centro"}
    assert contract.en_riesgo((150, 100, 240, 148), 296)
    assert not contract.en_riesgo((150, 100, 240, 147), 296)
