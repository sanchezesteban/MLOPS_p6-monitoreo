"""Auditor propio de M3 con reloj controlado (autoevaluacion P5-17).

Se corre desde Proyecto5/ con `PYTHONPATH=src`. Usa solo la API publica de p5 y eventos
sinteticos; no abre anotaciones ni hardware. Imprime True/False por comprobacion.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from p5.contrato import PerceptionEvent
from p5.control import AdaptadorVirtual
from p5.politica import Politica, cargar_config
from p5.watchdog import RelojControlado, Watchdog
from p5.watchdog import cargar_config as cargar_config_watchdog


def montar(etiqueta: str):
    log = Path(tempfile.mkdtemp()) / f"{etiqueta}.jsonl"
    reloj = RelojControlado()
    controlador = AdaptadorVirtual(log, "auditor", reloj=reloj)
    politica = Politica(cargar_config("config/politica.yaml"))
    cfg = cargar_config_watchdog("config/watchdog.yaml")
    return log, reloj, Watchdog(politica, controlador, reloj, cfg, "auditor")


def evento(i: int, t: float, status: str = "ok", error: str | None = None) -> PerceptionEvent:
    return PerceptionEvent(
        "1", "auditor", "AUD", f"AUD_f{i:04d}", float(t), None, None, 400, 296,
        "0" * 64, "0" * 64, status, error, True, (),
    )  # fmt: skip


def comandos(log: Path) -> list[dict]:
    if not log.exists():
        return []
    return [json.loads(linea) for linea in log.read_text(encoding="utf-8").splitlines()]


def resumen(log: Path, desde: int = 0) -> list[tuple]:
    return [
        (c.get("event"), c.get("state_after"), c.get("speed"), c.get("frame_id"), c.get("reason"))
        for c in comandos(log)[desde:]
    ]


def cuadros_libres(wd, reloj, desde: int, hasta: int) -> None:
    for i in range(desde, hasta):
        reloj.avanzar(100)
        wd.procesar_evento(evento(i, reloj()))


def main() -> None:
    res = {}
    # C8: corte de cuadros con reloj controlado y luego un cuadro vencido.
    log, reloj, wd = montar("c8")
    cuadros_libres(wd, reloj, 0, 5)
    n = len(comandos(log))
    reloj.avanzar(120)
    wd.tick()
    print("tras +120 ms sin cuadros:", resumen(log, n))
    reloj.avanzar(400)
    wd.tick()
    despues = resumen(log, n)
    print("tras +520 ms sin cuadros:", despues)
    res["c8_stop_sin_cuadro_nuevo"] = any(x[2] == 0 for x in despues)
    n = len(comandos(log))
    wd.procesar_evento(evento(99, 0.0))
    viejo = resumen(log, n)
    print(f"cuadro vencido (t_capture=0, reloj={reloj()}):", viejo)
    res["c8_cuadro_vencido_stop"] = bool(viejo) and viejo[-1][2] == 0

    # C9: error del detector convertido en STOP.
    log, reloj, wd = montar("c9")
    cuadros_libres(wd, reloj, 0, 3)
    n = len(comandos(log))
    reloj.avanzar(100)
    wd.procesar_evento(evento(10, reloj(), status="error", error="excepcion_detector"))
    error = resumen(log, n)
    print("status=error:", error)
    res["c9_error_stop"] = bool(error) and error[-1][2] == 0

    # C10: emergencia, rearme y cierre.
    log, reloj, wd = montar("c10")
    cuadros_libres(wd, reloj, 0, 6)
    print("avance previo:", resumen(log)[-1])
    n = len(comandos(log))
    wd.emergencia()
    emergencia = resumen(log, n)
    print("emergencia:", emergencia)
    res["c10_emergencia_stop"] = bool(emergencia) and emergencia[-1][2] == 0
    n = len(comandos(log))
    cuadros_libres(wd, reloj, 20, 26)
    sin_rearme = resumen(log, n)
    res["c10_sin_rearme_no_avanza"] = all(x[2] == 0 for x in sin_rearme)
    wd.rearme()
    n = len(comandos(log))
    cuadros_libres(wd, reloj, 30, 38)
    con_rearme = resumen(log, n)
    print("tras rearme + 8 cuadros frescos:", [(x[1], x[2]) for x in con_rearme])
    res["c10_rearme_reanuda"] = any((x[2] or 0) > 0 for x in con_rearme)
    n = len(comandos(log))
    wd.cerrar()
    cierre = resumen(log, n)
    print("cierre:", cierre)
    res["c10_cierre_stop"] = bool(cierre) and cierre[-1][2] == 0

    # Rearme con un cuadro viejo no debe reanudar.
    log, reloj, wd = montar("c10b")
    cuadros_libres(wd, reloj, 0, 3)
    wd.emergencia()
    wd.rearme()
    reloj.avanzar(1000)
    n = len(comandos(log))
    wd.procesar_evento(evento(50, 0.0))
    res["c10_rearme_cuadro_viejo_no_reanuda"] = all(x[2] == 0 for x in resumen(log, n))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
