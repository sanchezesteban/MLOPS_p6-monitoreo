"""P5-11: interfaz de control (`ControladorMotores`) y su adaptador virtual.

La politica (grupo B, P5-10) decide un `Command` del contrato (`p5.contrato`)
y lo manda a un `ControladorMotores` -- la misma interfaz para la aplicacion y
para la evaluacion. `AdaptadorVirtual` nunca mueve nada: registra cada comando
en un JSONL. El controlador real (GPIO/serial) queda detras de `--modo real`
en `construir_controlador`; no existe todavia, asi que en modo virtual (el
default) no hay ningun import de hardware al arrancar.
"""

from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path
from typing import Any

from p5.contrato import ContratoError, validar_comando

Reloj = Callable[[], float]


def reloj_monotonico() -> Reloj:
    """Milisegundos monotonicos desde que se llama -- un solo origen por corrida, como pide
    el contrato (nunca el reloj de pared). Para que la politica y el adaptador compartan
    exactamente el mismo reloj, quien construye la corrida llama esto una sola vez y pasa
    esa misma instancia a ambos (o usa `RelojControlado` en pruebas)."""
    inicio = time.monotonic()
    return lambda: (time.monotonic() - inicio) * 1000


class ControladorMotores(ABC):
    """Interfaz unica entre la politica y quien ejecuta el comando (virtual o real)."""

    @abstractmethod
    def enviar(self, comando: dict[str, Any]) -> None:
        """Procesa un `Command` (dict con la forma de `p5.contrato.Command`)."""

    @abstractmethod
    def stop(self, razon: str, *, event: str) -> None:
        """Parada inmediata fuera del flujo normal de comandos. `event` es el disparador
        del contrato (`"watchdog"`, `"emergency"` o `"shutdown"`), nunca un valor libre."""

    @abstractmethod
    def cerrar(self) -> None:
        """Libera recursos (p. ej. el archivo de bitacora). Idempotente."""


class AdaptadorVirtual(ControladorMotores):
    """No mueve motores: registra cada comando en `log_path` (JSONL, un objeto por linea).

    Un comando fuera de contrato (velocidad/direccion fuera de rango, numero no
    finito, regla entre campos rota, ...) nunca se ejecuta tal cual -- se
    rechaza y en su lugar se registra un `STOP` seguro con el detalle en
    `error` (la saturacion segura documentada que pide el ticket: ante duda,
    parar es siempre valido dentro del contrato).

    `reloj` es obligatorio (sin reloj de pared por defecto): quien construye la
    corrida (p. ej. `Watchdog`, P5-12) debe pasar la MISMA instancia que usa para
    el resto de la corrida, nunca una propia -- `p5.control.reloj_monotonico()`
    para la aplicacion real, `p5.watchdog.RelojControlado` en pruebas.
    """

    def __init__(
        self,
        log_path: str | Path,
        run_id: str,
        reloj: Reloj,
    ) -> None:
        self._log_path = Path(log_path)
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        self._archivo = self._log_path.open("a", encoding="utf-8")
        self._run_id = run_id
        self._reloj = reloj
        self._ultimo_estado = "inicio"
        self._cerrado = False

    def enviar(self, comando: dict[str, Any]) -> None:
        if self._cerrado:
            return
        # t_command_ms es "el instante en que el adaptador lo recibio" (contrato): lo pone
        # el adaptador con su propio reloj, nunca el valor que trae la politica.
        recibido_en = self._reloj()
        datos = {**comando, "t_command_ms": recibido_en} if isinstance(comando, dict) else comando
        try:
            valido = validar_comando(datos)
            if valido.run_id != self._run_id:
                raise ContratoError(
                    "comando",
                    [f"run_id {valido.run_id!r} no coincide con la corrida {self._run_id!r}"],
                )
        except ContratoError as exc:
            frame_id = datos.get("frame_id") if isinstance(datos, dict) else None
            frame_id = frame_id if isinstance(frame_id, str) else None
            self._escribir(
                self._comando_stop(
                    "comando_rechazado",
                    error=str(exc)[:500],
                    frame_id=frame_id,
                    event="comando_rechazado",
                    ahora=recibido_en,
                )
            )
            return
        self._ultimo_estado = valido.state_after
        self._escribir({**asdict(valido), "received": True})

    def stop(self, razon: str, *, event: str) -> None:
        if self._cerrado:
            return
        self._escribir(self._comando_stop(razon, event=event))

    def cerrar(self) -> None:
        if self._cerrado:
            return
        # Siempre deja un STOP de cierre en la bitacora (C10), incluso si el ultimo
        # comando ya era STOP -- es la unica forma de ver que el cierre en si ocurrio.
        self.stop("shutdown", event="shutdown")
        self._archivo.close()
        self._cerrado = True

    def _comando_stop(
        self,
        razon: str,
        *,
        event: str,
        error: str | None = None,
        frame_id: str | None = None,
        ahora: float | None = None,
    ) -> dict[str, Any]:
        ahora = self._reloj() if ahora is None else ahora
        comando = {
            "schema_version": "1.0",
            "run_id": self._run_id,
            "frame_id": frame_id,
            "event": event,
            "detections_ref": None,
            "state_before": self._ultimo_estado,
            "state_after": "STOPPED",
            "action": "STOP",
            "reason": razon or "stop",
            "speed": 0.0,
            "steering": 0.0,
            "t_decision_ms": ahora,
            "t_command_ms": ahora,
            "valid_until_ms": None,
            "received": True,
            "error": error,
            "synthetic": False,
        }
        self._ultimo_estado = "STOPPED"
        return comando

    def _escribir(self, comando: dict[str, Any]) -> None:
        self._archivo.write(json.dumps(comando, ensure_ascii=False) + "\n")
        self._archivo.flush()


def construir_controlador(
    modo: str,
    *,
    log_path: str | Path,
    run_id: str,
    reloj: Reloj,
) -> ControladorMotores:
    """Fabrica: "virtual" (default) construye el adaptador de arriba, sin tocar
    hardware. "real" queda reservado para cuando exista un controlador fisico
    -- no esta implementado, asi que ni un import tardio puede arrastrar
    GPIO/serial al arrancar en modo virtual. `reloj` es obligatorio: ver
    `AdaptadorVirtual`."""
    if modo == "virtual":
        return AdaptadorVirtual(log_path, run_id, reloj)
    if modo == "real":
        raise NotImplementedError("modo real: no hay controlador fisico en este proyecto todavia")
    raise ValueError(f"modo desconocido: {modo!r} (usa 'virtual' o 'real')")
