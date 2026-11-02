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


def reloj_de_pared() -> float:
    """Milisegundos desde epoch. Default de produccion; las pruebas inyectan otro."""
    return time.time() * 1000


class ControladorMotores(ABC):
    """Interfaz unica entre la politica y quien ejecuta el comando (virtual o real)."""

    @abstractmethod
    def enviar(self, comando: dict[str, Any]) -> None:
        """Procesa un `Command` (dict con la forma de `p5.contrato.Command`)."""

    @abstractmethod
    def stop(self, razon: str) -> None:
        """Parada inmediata fuera del flujo normal de comandos (watchdog, emergencia, cierre)."""

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
    """

    def __init__(
        self,
        log_path: str | Path,
        run_id: str,
        reloj: Reloj = reloj_de_pared,
    ) -> None:
        self._log_path = Path(log_path)
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        self._archivo = self._log_path.open("a", encoding="utf-8")
        self._run_id = run_id
        self._reloj = reloj
        self._ultimo_estado = "inicio"
        self._cerrado = False

    def enviar(self, comando: dict[str, Any]) -> None:
        try:
            valido = validar_comando(comando)
            if valido.run_id != self._run_id:
                raise ContratoError(
                    "comando",
                    [f"run_id {valido.run_id!r} no coincide con la corrida {self._run_id!r}"],
                )
        except ContratoError as exc:
            self._escribir(self._comando_stop("comando_rechazado", error=str(exc)[:500]))
            return
        self._ultimo_estado = valido.state_after
        self._escribir({**asdict(valido), "received": True})

    def stop(self, razon: str) -> None:
        self._escribir(self._comando_stop(razon))

    def cerrar(self) -> None:
        if not self._cerrado:
            self._archivo.close()
            self._cerrado = True

    def _comando_stop(self, razon: str, error: str | None = None) -> dict[str, Any]:
        ahora = self._reloj()
        comando = {
            "schema_version": "1.0",
            "run_id": self._run_id,
            "frame_id": None,
            "event": "adaptador_stop",
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
    reloj: Reloj = reloj_de_pared,
) -> ControladorMotores:
    """Fabrica: "virtual" (default) construye el adaptador de arriba, sin tocar
    hardware. "real" queda reservado para cuando exista un controlador fisico
    -- no esta implementado, asi que ni un import tardio puede arrastrar
    GPIO/serial al arrancar en modo virtual."""
    if modo == "virtual":
        return AdaptadorVirtual(log_path, run_id, reloj)
    if modo == "real":
        raise NotImplementedError("modo real: no hay controlador fisico en este proyecto todavia")
    raise ValueError(f"modo desconocido: {modo!r} (usa 'virtual' o 'real')")
