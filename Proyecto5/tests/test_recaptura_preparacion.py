"""Preparacion v2: pruebas sin camara; patrones sinteticos solo en temporales."""

import contextlib
import csv
import hashlib
import io
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import capturar_esp32 as capture
import capturas_core as core
from p5.contrato import validar_evento, validar_secuencia


def test_54_capturas_numeracion_por_secuencia_y_metadatos(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "jpeg_dimensions", lambda _: (400, 296))
    for seq, total in (("S2", 17), ("S3", 13), ("S4", 12), ("S6", 12)):
        with core.CaptureStore(tmp_path, f"TEST-ONLY-{seq}") as store:
            for i in range(total):
                label = "despejado" if seq == "S6" and (i < 4 or i >= 8) else "obstaculo"
                store.save(
                    f"TEST ONLY {seq}/{i}".encode(),
                    seq,
                    1_000_000_000 + i * 23_000_000,
                    label,
                    False,
                )
    rows = core.read_rows(tmp_path)
    assert len(rows) == len({r["frame_id"] for r in rows}) == 54
    for seq, total in (("S2", 17), ("S3", 13), ("S4", 12), ("S6", 12)):
        group = [r for r in rows if r["sequence_id"] == seq]
        assert [r["frame_id"] for r in group] == [f"{seq}_f{i:04d}" for i in range(1, total + 1)]
        assert [int(r["t_capture_ms"]) for r in group] == [i * 23 for i in range(total)]
        assert {r["session_id"] for r in group} == {f"TEST-ONLY-{seq}"}
        assert {r["sequence_start_unix_ns"] for r in group} == {"1000000000"}
    for r in rows:
        assert hashlib.sha256((tmp_path / r["path"]).read_bytes()).hexdigest() == r["sha256"]
    assert [r["scene_label"] for r in rows if r["sequence_id"] == "S6"] == (
        ["despejado"] * 4 + ["obstaculo"] * 4 + ["despejado"] * 4
    )


def test_reabrir_continua_numero_tiempos_y_no_reescribe_csv(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "jpeg_dimensions", lambda _: (400, 296))
    with core.CaptureStore(tmp_path, "TEST-OLD") as store:
        store.save(b"TEST ONLY first", "S2", 1_000_000_000, "obstaculo", False)
    before = (tmp_path / "capturas.csv").read_bytes()
    with core.CaptureStore(tmp_path, "TEST-NEW") as store:
        store.save(b"TEST ONLY second", "S2", 3_000_000_000, "obstaculo", False)
    rows = core.read_rows(tmp_path)
    assert [r["frame_id"] for r in rows] == ["S2_f0001", "S2_f0002"]
    assert [r["t_capture_ms"] for r in rows] == ["0", "2000"]
    assert [r["session_id"] for r in rows] == ["TEST-OLD", "TEST-NEW"]
    assert (tmp_path / "capturas.csv").read_bytes().startswith(before)


def test_reanudacion_usa_maximo_y_no_cantidad_de_filas(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "jpeg_dimensions", lambda _: (400, 296))
    with core.CaptureStore(tmp_path, "TEST") as store:
        store.save(b"TEST ONLY first", "S3", 1_000_000_000, "obstaculo", False)
    rows = core.read_rows(tmp_path)
    rows[0]["frame_id"] = "S3_f0013"
    with (tmp_path / "capturas.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=core.FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    with core.CaptureStore(tmp_path, "TEST") as store:
        store.save(b"TEST ONLY second", "S3", 2_000_000_000, "obstaculo", False)
    assert core.read_rows(tmp_path)[1]["frame_id"] == "S3_f0014"


def test_duplicados_y_cuadros_viejos_no_consumen_ids(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "jpeg_dimensions", lambda _: (400, 296))
    with core.CaptureStore(tmp_path, "TEST") as store:
        store.save(b"TEST ONLY first", "S4", 1_000_000_000, "obstaculo", False)
        assert "Duplicado" in store.save(
            b"TEST ONLY first", "S4", 2_000_000_000, "obstaculo", False
        )
        assert "omitida" in store.save(b"TEST ONLY old", "S4", 900_000_000, "obstaculo", False)
        store.save(b"TEST ONLY second", "S4", 3_000_000_000, "obstaculo", False)
    assert [r["frame_id"] for r in core.read_rows(tmp_path)] == ["S4_f0001", "S4_f0002"]


def test_anexar_a_uuid_legacy_no_renumera_original(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "jpeg_dimensions", lambda _: (400, 296))
    with core.CaptureStore(tmp_path, "TEST") as store:
        store.save(b"TEST ONLY first", "S2", 1_000_000_000, "obstaculo", False)
    rows = core.read_rows(tmp_path)
    rows[0]["frame_id"] = "S2_" + "b" * 32
    with (tmp_path / "capturas.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=core.FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    before = (tmp_path / "capturas.csv").read_bytes()
    with core.CaptureStore(tmp_path, "TEST") as store:
        store.save(b"TEST ONLY second", "S2", 2_000_000_000, "obstaculo", False)
    assert core.read_rows(tmp_path)[0] == rows[0]
    assert core.read_rows(tmp_path)[1]["frame_id"] == "S2_f0001"
    assert (tmp_path / "capturas.csv").read_bytes().startswith(before)


@pytest.mark.parametrize("seq", ["S2", "S3", "S4", "S6"])
def test_ids_nuevos_pasan_contrato_v1(seq, tmp_path, monkeypatch):
    monkeypatch.setattr(core, "jpeg_dimensions", lambda _: (400, 296))
    with core.CaptureStore(tmp_path, "TEST") as store:
        store.save(b"TEST ONLY", seq, 1_000_000_000, "obstaculo", False)
    r = core.read_rows(tmp_path)[0]
    data = json.loads((Path(__file__).parents[1] / "config/ejemplos/vacio.json").read_text())
    data.update(
        sequence_id=seq,
        frame_id=r["frame_id"],
        image_path=r["path"],
        image_sha256=r["sha256"],
        image_width=400,
        image_height=296,
        t_capture_ms=0,
        synthetic=True,
    )
    assert r["frame_id"] == f"{seq}_f0001"
    assert validar_secuencia([validar_evento(data)]) == []


@pytest.mark.parametrize("value", ["0x296", "400x-1", "400", "400x296x3", "nanx296"])
def test_resolucion_cli_invalida(value):
    with contextlib.redirect_stderr(io.StringIO()), pytest.raises(SystemExit):
        capture.parser().parse_args(["--resolucion", value])


@pytest.mark.parametrize("size", [(400, 296), (320, 240)])
def test_resolucion_se_comprueba_antes_de_guardar_y_cierra_limpiamente(size, tmp_path):
    cv2 = pytest.importorskip("cv2")
    import numpy as np

    source = np.zeros((size[1], size[0], 3), dtype=np.uint8)
    source[: size[1] // 2] = (50, 120, 220)  # Patron sintetico, solo en memoria.
    ok, encoded = cv2.imencode(".jpg", source)
    assert ok
    reader = MagicMock()
    reader.error = None
    reader.state = "EN VIVO"
    reader.drain_messages.return_value = []
    reader.is_current.return_value = True
    reader.snapshot.return_value = (encoded.tobytes(), 1_000_000_000, 100)
    args = capture.parser().parse_args(
        [
            "--destino",
            str(tmp_path),
            "--secuencia",
            "S2",
            "--rotacion",
            "180",
            "--resolucion",
            "400x296",
        ]
    )
    with (
        patch.object(capture, "ReconnectingStream", return_value=reader),
        patch.object(capture.time, "monotonic", return_value=100),
        patch.object(cv2, "namedWindow"),
        patch.object(cv2, "setWindowTitle"),
        patch.object(cv2, "imshow"),
        patch.object(cv2, "getWindowProperty", return_value=1),
        patch.object(cv2, "waitKey", side_effect=[ord("b"), 32, ord("q")]),
        patch.object(cv2, "destroyAllWindows"),
        contextlib.redirect_stdout(io.StringIO()),
    ):
        if size == (400, 296):
            capture.run(args)
        else:
            with pytest.raises(ValueError, match="Resolución recibida"):
                capture.run(args)
    rows = core.read_rows(tmp_path)
    assert len(rows) == (1 if size == (400, 296) else 0)
    if rows:
        assert rows[0]["frame_id"] == "S2_f0001"
        assert (rows[0]["image_width"], rows[0]["image_height"]) == ("400", "296")
        saved = (tmp_path / rows[0]["path"]).read_bytes()
        decoded = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
        ok, clean = cv2.imencode(".jpg", np.rot90(decoded, 2), [cv2.IMWRITE_JPEG_QUALITY, 95])
        assert ok and saved == clean.tobytes()
    reader.close.assert_called_once()
    assert not (tmp_path / ".captura.lock").exists()


@pytest.mark.parametrize(
    ("name", "count"), [("protocolo_v1", 84), ("seleccion_78_pre_recaptura", 78)]
)
def test_archivos_historicos_completos_y_hashes(name, count):
    root = Path(__file__).parents[1] / "datos/archivo" / name
    rows = core.read_rows(root)
    assert len(rows) == count
    assert {p.relative_to(root).as_posix() for p in root.rglob("*.jpg")} == {
        r["path"] for r in rows
    }
    for row in rows:
        assert hashlib.sha256((root / row["path"]).read_bytes()).hexdigest() == row["sha256"]
    metadata = json.loads((root / "archivo.json").read_text(encoding="utf-8"))
    assert metadata["jpeg_count"] == count
    assert (
        metadata["csv_sha256"] == hashlib.sha256((root / "capturas.csv").read_bytes()).hexdigest()
    )
    listed = set()
    for line in (root / "HASHES.sha256").read_text(encoding="utf-8").splitlines():
        sha, relative = line.split("  ", 1)
        assert (root / relative).resolve().is_relative_to(root.resolve())
        assert hashlib.sha256((root / relative).read_bytes()).hexdigest() == sha
        listed.add(relative)
    assert listed == {
        p.relative_to(root).as_posix()
        for p in root.rglob("*")
        if p.is_file() and p.name != "HASHES.sha256"
    }
    assert len({r["frame_id"] for r in rows}) == len({r["sha256"] for r in rows}) == count
