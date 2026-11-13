"""Metricas adicionales con casos calculados a mano y funciones extra del portal."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from p6 import extras
from p6.portal.app import crear_app

DB = Path(__file__).resolve().parents[1] / "evidencias" / "monitoreo.db"


def ev(seq, estado, score=None, t0=0.0, dt=0.2, lat=0.03, w="w0"):
    return {
        "seq": seq,
        "event_id": f"e{seq}",
        "estado": estado,
        "score_principal": score,
        "t_captura_mono": t0 + seq * dt,
        "t_fin_mono": t0 + seq * dt + lat,
        "window_id": w,
        "t_captura": f"2026-01-01T00:00:{seq:02d}.000Z",
    }


def test_ks_a_mano():
    # F_a salta en 0.1, 0.2 ; F_b en 0.3, 0.4 -> en x=0.2 |1 - 0| = 1
    assert extras.ks([0.1, 0.2], [0.3, 0.4]) == 1.0
    assert extras.ks([0.1, 0.3], [0.1, 0.3]) == 0.0
    # a={0.1,0.2,0.3,0.4} b={0.25}: en x=0.2 F_a=0.5, F_b=0 -> 0.5
    assert extras.ks([0.1, 0.2, 0.3, 0.4], [0.25]) == 0.5
    assert extras.ks([], [0.1]) is None


def test_ks_por_ventana_exige_minimo():
    evs = [ev(i, "ok", 0.1) for i in range(5)]
    assert extras.ks_por_ventana(evs, [0.9])[0]["ks"] is None
    evs.append(ev(5, "ok", 0.1))
    assert extras.ks_por_ventana(evs, [0.9])[0]["ks"] == 1.0


def test_fps_captura_latencia_sindet_errores():
    evs = [ev(0, "ok", 0.5), ev(1, "sin_detecciones"), ev(2, "error"), ev(3, "ok", 0.2)]
    assert extras.fps_captura(evs) == pytest.approx(3 / 0.6)
    assert extras.fps_captura(evs[:1]) is None
    lat = extras.latencia_e2e(evs)
    assert lat["n"] == 3 and lat["p95_ms"] == pytest.approx(30.0)
    assert extras.proporcion_sin_detecciones(evs) == pytest.approx(1 / 3)
    assert extras.tasa_errores(evs) == 0.25
    assert extras.tasa_errores([]) is None
    assert extras.proporcion_sin_detecciones([ev(0, "error")]) is None


def test_tiempos_incidente_controlado():
    evs = [ev(i, "ok", 0.5) for i in range(30)]
    fases = ["normal"] * 10 + ["degradada"] * 10 + ["recuperacion"] * 10
    alertas = [
        {
            "alert_id": "a0",
            "rule_id": "r",
            "t_apertura": "2026-01-01T00:00:05.000Z",
            "t_resolucion": "2026-01-01T00:00:06.000Z",
        },  # antes del incidente: se ignora
        {
            "alert_id": "a1",
            "rule_id": "r",
            "t_apertura": "2026-01-01T00:00:14.500Z",
            "t_resolucion": "2026-01-01T00:00:22.000Z",
        },
    ]
    r = extras.tiempos_incidente(evs, alertas, fases)
    assert r["incidente"]["frame_inicio"] == 10 and r["incidente"]["frame_fin"] == 20
    assert r["por_regla"]["r"] == {
        "alert_id": "a1",
        "tiempo_deteccion_s": 4.5,
        "tiempo_recuperacion_s": 2.0,
    }
    assert extras.tiempos_incidente(evs, alertas, None)["incidente"] is None
    assert extras.tiempos_incidente(evs, alertas, ["normal"] * 30)["incidente"] is None


@pytest.mark.skipif(not DB.is_file(), reason="sin base de evidencia")
class TestPortalExtras:
    c = TestClient(crear_app(DB))

    def test_graficas_estados(self):
        assert "Elige una corrida" in self.c.get("/graficas").text
        r = self.c.get("/graficas?run=s-sostenido")
        assert r.status_code == 200 and "<svg" in r.text and "cambio-sostenido-v1" in r.text
        assert self.c.get("/graficas?run=no-existe").status_code == 404
        assert "no declara un incidente" in self.c.get("/graficas?run=c1-normal").text

    def test_capturas_filtros_y_estados(self):
        r = self.c.get("/capturas?run=c2-baja-confianza&zona=baja")
        assert r.status_code == 200 and r.text.count('class="z-baja"') == 21
        assert "No hay capturas" in self.c.get("/capturas?run=c1-normal&estado=error").text
        assert self.c.get("/capturas?zona=roja").status_code == 400

    def test_exportar_csv_coincide_con_api(self):
        r = self.c.get("/exportar/eventos.csv?run=c2-baja-confianza&zona=baja")
        filas = r.text.strip().splitlines()
        api = self.c.get("/api/eventos?run=c2-baja-confianza&zona=baja").json()
        assert r.headers["content-type"].startswith("text/csv")
        assert len(filas) - 1 == len(api) == int(r.headers["x-filas"]) == 21
        assert filas[0].startswith("event_id,run_id,seq")
        vacio = self.c.get("/exportar/eventos.csv?run=c1-normal&estado=error")
        assert vacio.text.strip().count("\n") == 0  # solo encabezado
        assert self.c.get("/exportar/eventos.csv?run=no-existe").status_code == 404
        assert self.c.get("/exportar/eventos.csv?estado=raro").status_code == 400
