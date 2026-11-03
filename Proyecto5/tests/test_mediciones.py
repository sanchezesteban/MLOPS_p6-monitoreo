"""Mediciones con reloj y HTTP simulados: ninguna petición a hardware real."""

from __future__ import annotations

import contextlib
import io
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import capturar_esp32 as capture
import medir_fps as fps
import medir_movimiento as movement
from mediciones_core import export_report, positive, statistics_of

URL = "http://192.168.68.113:81/stream"


@pytest.fixture(autouse=True)
def no_hardware():
    with patch("socket.socket.connect", side_effect=AssertionError("Red real prohibida")):
        yield


def test_linear_conversion_and_angular_use_observed_time():
    result = movement.calculate_trial("avance", 2, distance=1.09)
    assert result["velocidad_m_s"] == pytest.approx(0.545)
    assert result["velocidad_km_h"] == pytest.approx(1.962)
    for kind in ("derecha", "izquierda"):
        assert movement.calculate_trial(kind, 0.35, angle=90)[
            "velocidad_angular_grados_s"
        ] == pytest.approx(257.142857)


@pytest.mark.parametrize("value", [0, -1, float("nan"), float("inf"), "no-numero"])
def test_positive_rejects_invalid(value):
    with pytest.raises(ValueError):
        positive(value)


@pytest.mark.parametrize(
    "kind, kwargs",
    [
        ("avance", {"observed_time": 0, "distance": 1}),
        ("izquierda", {"observed_time": -1, "angle": 90}),
        ("derecha", {"observed_time": 1, "angle": -90}),
        ("avance", {"observed_time": 1, "distance": -1}),
        ("invalido", {"observed_time": 1}),
    ],
)
def test_trial_invalid(kind, kwargs):
    with pytest.raises(ValueError):
        movement.calculate_trial(kind, **kwargs)


def test_summary_variation_and_reference():
    trials = [
        {"tipo": "avance", **movement.calculate_trial("avance", 1, distance=d)} for d in (1, 2, 3)
    ]
    result = movement.summarize(trials)["avance"]
    assert result["velocidad_m_s"] == {
        "n": 3,
        "media": 2,
        "minimo": 1,
        "maximo": 3,
        "rango": 2,
        "desviacion_estandar_muestral": 1,
    }
    assert result["diferencia_media_vs_referencia"] == pytest.approx(1.455)
    with pytest.raises(ValueError):
        statistics_of([])


def test_export_unique_json_and_no_overwrite(tmp_path):
    first = export_report({"dato": "medición"}, tmp_path, "registro")
    original = first.read_bytes()
    second = export_report({"dato": "otro"}, tmp_path, "registro")
    assert first != second
    assert first.read_bytes() == original
    assert json.loads(first.read_text(encoding="utf-8")) == {"dato": "medición"}
    with pytest.raises(ValueError):
        export_report({"dato": float("nan")}, tmp_path, "registro")


def test_manual_default_no_network_and_separate_command_times(tmp_path):
    answers = iter(["0.35", "0.36", "0.4", "85"] * 3)
    with (
        patch("builtins.input", side_effect=lambda _: next(answers)),
        patch.object(fps.http.client, "HTTPConnection", side_effect=AssertionError("No conectar")),
    ):
        assert (
            movement.main(
                ["--tipo", "derecha", "--nivel", "nominal observado", "--salida", str(tmp_path)]
            )
            == 0
        )
    report = json.loads(next(tmp_path.glob("*.json")).read_text(encoding="utf-8"))
    row = report["pruebas"][0]
    assert row["duracion_solicitada_comando_s"] == 0.35
    assert row["duracion_real_comando_s"] == 0.36
    assert row["tiempo_observado_s"] == 0.4
    assert row["velocidad_angular_grados_s"] == 85 / 0.4
    assert report["modo"] == "registro_manual_sin_actuacion"
    assert report["completa"]


@pytest.mark.parametrize("extra", [[], ["--dry-run"]])
def test_real_mode_always_blocked_before_input_or_network(extra):
    with (
        patch("builtins.input", side_effect=AssertionError("No iniciar prueba")),
        patch.object(fps.http.client, "HTTPConnection", side_effect=AssertionError("No conectar")),
        pytest.raises(SystemExit) as error,
    ):
        movement.main(["--modo-real", *extra])
    assert error.value.code == 2


def test_manual_interruption_preserves_completed_trials_without_stop_requests(tmp_path):
    values = ["", "", "1", "1", KeyboardInterrupt()]
    with (
        patch("builtins.input", side_effect=values),
        patch.object(
            fps.http.client, "HTTPConnection", side_effect=AssertionError("No actuadores")
        ),
    ):
        assert (
            movement.main(["--tipo", "avance", "--nivel", "desconocida", "--salida", str(tmp_path)])
            == 130
        )
    report = json.loads(next(tmp_path.glob("*.json")).read_text(encoding="utf-8"))
    assert len(report["pruebas"]) == 1
    assert not report["completa"]


@pytest.mark.parametrize("argv", [["--repeticiones", "2"], ["--duracion-solicitada", "3"]])
def test_manual_unsafe_or_insufficient_configuration_rejected(argv):
    with pytest.raises(SystemExit):
        movement.main(argv)


def test_new_camera_url_compatible_and_forwarded():
    args = capture.parser().parse_args(
        [
            "--destino",
            "Proyecto5/datos/recaptura_clases",
            "--rotacion",
            "180",
            "--url",
            URL,
        ]
    )
    assert args.url == URL
    assert args.rotacion == 180
    with patch.object(capture, "ReconnectingStream") as reader:
        with capture.reconnecting_stream(args):
            pass
        reader.assert_called_once_with(URL, 10, 10, 2)
        reader.return_value.close.assert_called_once()
    assert fps.parser().parse_args(["--url", URL]).url == URL
    with pytest.raises(SystemExit):
        fps.parser().parse_args([])


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


class ScheduledFrames:
    def __init__(self, events, clock):
        self.events = iter(events)
        self.clock = clock

    def read_until(self, deadline):
        event = next(self.events, None)
        if event is None or event[0] > deadline:
            self.clock.now = deadline
            raise TimeoutError("simulado")
        stamp, data = event
        self.clock.now = stamp
        if isinstance(data, BaseException):
            raise data
        return data, stamp


def simulate(events, **kwargs):
    clock = Clock()
    frames = ScheduledFrames(events, clock)
    with patch.object(
        fps,
        "jpeg_dimensions",
        side_effect=lambda b: (
            (400, 296) if b != b"bad" else (_ for _ in ()).throw(ValueError("JPEG corrupto"))
        ),
    ):
        return fps.measure(frames, clock=clock, **kwargs)


def test_fps_slow_start_full_ten_second_window():
    events = [(8, b"anchor"), *[(8 + i, f"frame{i}".encode()) for i in range(1, 11)]]
    result = simulate(events)
    assert result["inicio_recepcion_monotonic_s"] == 8
    assert result["ventana_efectiva_s"] == 10
    assert result["fps_recibidos_distintos"] == 1
    assert result["cuadros_nuevos"] == 10
    assert result["intervalos_s"] == [1] * 10


def test_fps_corrupt_and_duplicate_not_counted_or_refreshing():
    events = [
        (0, b"bad"),
        (1, b"anchor"),
        (1.2, b"anchor"),
        (1.4, b"a"),
        (1.6, b"anchor"),
        (2, b"b"),
        (2.5, b"a"),
        (3, b"c"),
    ]
    result = simulate(events, duration=2)
    assert result["jpeg_invalidos_descartados"] == 1
    assert result["jpeg_duplicados_descartados"] == 3
    assert result["cuadros_nuevos"] == 3
    assert result["fps_recibidos_distintos"] == 1.5


@pytest.mark.parametrize("events", [[], [(0, b"a"), (1, b"a"), (2, b"a"), (3, b"a")]])
def test_fps_missing_or_frozen_times_out(events):
    with pytest.raises(TimeoutError, match=r"primer JPEG válido|congelación"):
        simulate(events)


def test_fps_midstream_disconnect_invalidates_window():
    with pytest.raises(OSError, match="corte"):
        simulate([(0, b"a"), (1, b"b"), (2, OSError("corte"))])


@pytest.mark.parametrize("error", [KeyboardInterrupt(), OSError("read failed")])
def test_stream_cleanup_on_interrupt_and_error(error):
    connection = MagicMock()
    response = connection.getresponse.return_value
    response.status = 200
    response.getheader.return_value = "multipart/x-mixed-replace; boundary=frame"
    response.read1.side_effect = error
    with (
        patch.object(fps.http.client, "HTTPConnection", return_value=connection) as factory,
        pytest.raises(type(error)),
        fps.open_frames(URL, 10) as frames,
    ):
        frames.read_until(time_deadline())
    factory.assert_called_once_with("192.168.68.113", 81, timeout=10)
    connection.request.assert_called_once_with(
        "GET", "/stream", headers={"Accept": "multipart/x-mixed-replace"}
    )
    response.close.assert_called_once()
    connection.close.assert_called_once()


def time_deadline():
    return fps.time.monotonic() + 10


@pytest.mark.parametrize("failure", ["connect", "http", "content_type"])
def test_http_error_cleanup(failure):
    connection = MagicMock()
    response = connection.getresponse.return_value
    response.status = 503 if failure == "http" else 200
    response.getheader.return_value = (
        "text/html" if failure == "content_type" else "multipart/x-mixed-replace"
    )
    if failure == "connect":
        connection.connect.side_effect = OSError("conexión fallida")
    with (
        patch.object(fps.http.client, "HTTPConnection", return_value=connection),
        pytest.raises((OSError, ValueError)),
        fps.open_frames(URL, 10),
    ):
        pytest.fail("No debe iniciar medición")
    connection.close.assert_called_once()
    if failure != "connect":
        response.close.assert_called_once()


def test_http_frames_keep_every_complete_frame_and_splits():
    clock = Clock()
    response = MagicMock()
    response.read1.side_effect = [b"\xff\xd8one", b"\xff\xd9\xff\xd8two\xff\xd9"]
    transport = MagicMock()
    frames = fps.HttpFrames(response, transport, clock)
    assert frames.read_until(10)[0] == b"\xff\xd8one\xff\xd9"
    assert frames.read_until(10)[0] == b"\xff\xd8two\xff\xd9"
    assert response.read1.call_count == 2


def test_repetitions_sequential_failure_then_recovery_exported(tmp_path):
    active = 0
    number = 0

    @contextlib.contextmanager
    def open_fake(url, initial_timeout):
        nonlocal active, number
        assert url == URL and initial_timeout == 10
        assert active == 0
        active += 1
        number += 1
        try:
            if number == 1:
                raise OSError("conexión inicial fallida")
            yield object()
        finally:
            active -= 1

    with (
        patch.object(fps, "open_frames", side_effect=open_fake),
        patch.object(
            fps, "measure", return_value={"estado": "completa", "fps_recibidos_distintos": 5}
        ),
        contextlib.redirect_stdout(io.StringIO()),
    ):
        assert fps.main(["--url", URL, "--salida", str(tmp_path)]) == 1
    report = json.loads(next(tmp_path.glob("*.json")).read_text(encoding="utf-8"))
    assert [p["estado"] for p in report["pruebas"]] == ["invalida", "completa", "completa"]
    assert report["resumen_fps_repeticiones_completas"]["media"] == 5
    assert not report["completa"]
    assert active == 0
