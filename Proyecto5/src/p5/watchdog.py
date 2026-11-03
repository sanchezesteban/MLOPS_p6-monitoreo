"""P5-12: reloj inyectable, watchdog de vencimiento, emergencia enclavada con rearme
y STOP registrado al cerrar/SIGINT/SIGTERM (`contrato_v1.md`, `docs/politica.md`).

`Watchdog` es quien arma el `Command` del contrato a partir de la `Decision` de la
politica (grupo B, P5-10): agrega `run_id`, los tiempos y `valid_until_ms` con un
UNICO reloj (el mismo que usa el `ControladorMotores` -- nunca dos relojes
independientes para una misma corrida, como pide el contrato) y lo manda al adaptador.
"""

from __future__ import annotations

import math
import signal
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import yaml

from p5.contrato import PerceptionEvent, esta_vencido
from p5.control import ControladorMotores, Reloj
from p5.politica import Politica


class ConfigWatchdogError(ValueError):
    """Configuracion de plazos rechazada; `errores` lista cada problema encontrado."""

    def __init__(self, errores: list[str]) -> None:
        super().__init__("configuracion de watchdog invalida: " + "; ".join(errores))
        self.errores = errores


@dataclass(frozen=True)
class ConfigWatchdog:
    plazo_reaccion_ms: float
    max_edad_ms: float
    vencimiento_ms: float


_PLAZOS = ("plazo_reaccion_ms", "max_edad_ms", "vencimiento_ms")


def _numero_positivo(valor: Any) -> bool:
    es_numero = isinstance(valor, int | float) and not isinstance(valor, bool)
    return es_numero and math.isfinite(valor) and valor > 0


def validar_config(data: Any) -> ConfigWatchdog:
    """Revisa claves, tipos y rangos de `config/watchdog.yaml`; cualquier problema lanza
    `ConfigWatchdogError` antes de construir un `Watchdog`."""
    if not isinstance(data, dict):
        raise ConfigWatchdogError(["(raiz): se espera un mapa"])
    errores = [f"(raiz): clave desconocida {k}" for k in data if k not in ("version", "plazos")]
    errores += [f"(raiz): falta {k}" for k in ("version", "plazos") if k not in data]
    if errores:
        raise ConfigWatchdogError(errores)
    if data["version"] != 1:
        errores.append(f"version: se espera 1, llego {data['version']!r}")

    plazos = data["plazos"]
    if not isinstance(plazos, dict):
        raise ConfigWatchdogError([*errores, "plazos: se espera un mapa"])
    errores += [f"plazos: clave desconocida {k}" for k in plazos if k not in _PLAZOS]
    errores += [f"plazos: falta {k}" for k in _PLAZOS if k not in plazos]
    if errores:
        raise ConfigWatchdogError(errores)

    errores += [
        f"plazos.{k}: se espera un numero positivo finito"
        for k in _PLAZOS
        if not _numero_positivo(plazos[k])
    ]
    if errores:
        raise ConfigWatchdogError(errores)
    if plazos["plazo_reaccion_ms"] > plazos["max_edad_ms"]:
        errores.append(
            "plazos.plazo_reaccion_ms no puede ser mayor que plazos.max_edad_ms "
            "(si no, el watchdog reacciona mas lento que lo que tarda un cuadro en envejecer)"
        )
    if errores:
        raise ConfigWatchdogError(errores)
    return ConfigWatchdog(**{k: plazos[k] for k in _PLAZOS})


def cargar_config(ruta: str | Path) -> ConfigWatchdog:
    """Lee y valida `config/watchdog.yaml`; un YAML ilegible tambien es configuracion invalida."""
    try:
        data = yaml.safe_load(Path(ruta).read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigWatchdogError([f"{ruta}: no se pudo leer ({exc})"]) from exc
    return validar_config(data)


class RelojControlado:
    """Reloj de pruebas: tiempo manual en milisegundos, nunca el de pared. Es su propio
    `Reloj` (`Callable[[], float]`): se pasa tal cual a `Watchdog` y a `construir_controlador`
    para que ambos compartan la misma instancia, como exige el contrato."""

    def __init__(self, inicio: float = 0.0) -> None:
        self._ahora = inicio

    def __call__(self) -> float:
        return self._ahora

    def avanzar(self, ms: float) -> None:
        if ms < 0:
            raise ValueError(f"no se puede retroceder el reloj ({ms} ms)")
        self._ahora += ms


class Watchdog:
    """Vigila una corrida: arma el `Command` desde cada `Decision` de la politica, detecta
    cuadros/comandos vencidos sin esperar un cuadro nuevo, y enclava la emergencia hasta un
    rearme explicito con percepcion fresca. Una instancia por corrida (mismo `run_id`)."""

    def __init__(
        self,
        politica: Politica,
        controlador: ControladorMotores,
        reloj: Reloj,
        cfg: ConfigWatchdog,
        run_id: str,
    ) -> None:
        self._politica = politica
        self._controlador = controlador
        self._reloj = reloj
        self._cfg = cfg
        self._run_id = run_id
        self._valid_until_ms: float | None = None
        self._ultimo_t_capture_ms: float | None = None
        self._emergencia = False
        self._armado = False

    def procesar_evento(self, evento: PerceptionEvent) -> None:
        """Entrada por cada `PerceptionEvent` de percepcion (grupo A)."""
        ahora = self._reloj()
        fresco = evento.status == "ok" and not esta_vencido(
            evento.t_capture_ms, ahora, self._cfg.max_edad_ms
        )
        if self._emergencia:
            if not (self._armado and fresco):
                # enclavada: no se le pasa el cuadro a la politica, pero tampoco se
                # pierde sin rastro -- queda en la bitacora (sin omisiones silenciosas).
                self._registrar_stop(
                    "emergencia_enclavada",
                    "emergency",
                    frame_id=evento.frame_id,
                    synthetic=evento.synthetic,
                )
                return
            self._emergencia = False
            self._armado = False
        if evento.status == "ok" and not fresco:
            # A dijo que iba bien, pero por el tiempo que tardo en llegar ya no sirve:
            # STOP sin esperar un cuadro nuevo, nunca reanuda con un cuadro viejo. Se
            # decide como un cuadro "stale" (conserva frame_id, event="stale_frame").
            vencido = replace(
                evento, status="stale", error_msg="cuadro_vencido_por_reloj", detections=()
            )
            self._enviar_decision(self._politica.decidir(vencido), ahora)
            return
        if fresco:
            self._ultimo_t_capture_ms = evento.t_capture_ms
        self._enviar_decision(self._politica.decidir(evento), ahora)

    def tick(self, ahora: float | None = None) -> None:
        """Revision periodica, sin cuadro nuevo: vencimiento del comando en curso o
        perdida de percepcion. Quien ejecuta la aplicacion la llama cada `plazo_reaccion_ms`.

        Ya en `FALLA` no vuelve a emitir: evita repetir el mismo STOP en cada tick mientras
        la perdida de percepcion sigue sin resolverse (un `PerceptionEvent` nuevo via
        `procesar_evento` es lo unico que puede sacarla de ahi)."""
        if self._emergencia or self._politica.estado == "FALLA":
            return
        ahora = self._reloj() if ahora is None else ahora
        vencio_comando = self._valid_until_ms is not None and ahora >= self._valid_until_ms
        vencio_cuadro = self._ultimo_t_capture_ms is not None and esta_vencido(
            self._ultimo_t_capture_ms, ahora, self._cfg.max_edad_ms
        )
        if vencio_comando or vencio_cuadro:
            razon = "comando_vencido" if vencio_comando else "sin_cuadros_recientes"
            self._enviar_decision(self._politica.detener("watchdog", razon), ahora)

    def emergencia(self, razon: str = "boton_emergencia") -> None:
        """STOP inmediato con prioridad sobre todo; enclava hasta `rearme()` con un
        cuadro fresco despues (no se libera sola, aunque lleguen cuadros despejados)."""
        self._emergencia = True
        self._armado = False
        self._enviar_decision(self._politica.detener("emergency", razon), self._reloj())

    def rearme(self) -> None:
        """Pide liberar la emergencia; solo surte efecto cuando `procesar_evento` reciba
        despues un cuadro fresco (status=ok y no vencido). El rearme en si queda
        registrado (`event="rearm"`), aunque todavia no libere nada."""
        if not self._emergencia:
            return
        self._armado = True
        self._registrar_stop("rearme_solicitado", "rearm")

    def cerrar(self) -> None:
        """Cierre normal: delega en el adaptador, que siempre registra el STOP de cierre."""
        self._controlador.cerrar()

    def instalar_señales(self) -> None:
        """SIGINT/SIGTERM tambien deben cerrar registrando STOP (criterio C10)."""
        signal.signal(signal.SIGINT, self._manejar_señal)
        signal.signal(signal.SIGTERM, self._manejar_señal)

    def _manejar_señal(self, signum: int, frame: Any) -> None:
        self.cerrar()
        raise SystemExit(128 + signum)

    def _enviar_decision(self, decision: Any, ahora: float) -> None:
        comando = self._construir_comando(decision, ahora)
        self._controlador.enviar(comando)
        self._valid_until_ms = comando["valid_until_ms"]

    def _registrar_stop(
        self,
        razon: str,
        event: str,
        frame_id: str | None = None,
        synthetic: bool = False,
    ) -> None:
        """STOP directo que no pasa por la politica (no decide nada nuevo, solo deja
        constancia): el enclave de emergencia y el rearme en si."""
        ahora = self._reloj()
        estado = self._politica.estado
        comando = {
            "schema_version": "1.0",
            "run_id": self._run_id,
            "frame_id": frame_id,
            "event": event,
            "detections_ref": None,
            "state_before": estado,
            "state_after": estado,
            "action": "STOP",
            "reason": razon,
            "speed": 0.0,
            "steering": 0.0,
            "t_decision_ms": ahora,
            "t_command_ms": ahora,
            "valid_until_ms": None,
            "received": False,
            "error": None,
            "synthetic": synthetic,
        }
        self._controlador.enviar(comando)
        self._valid_until_ms = None

    def _construir_comando(self, decision: Any, ahora: float) -> dict[str, Any]:
        movimiento = decision.action != "STOP"
        return {
            "schema_version": "1.0",
            "run_id": self._run_id,
            "frame_id": decision.frame_id,
            "event": decision.event,
            "detections_ref": decision.detections_ref,
            "state_before": decision.state_before,
            "state_after": decision.state_after,
            "action": decision.action,
            "reason": decision.reason,
            "speed": decision.speed,
            "steering": decision.steering,
            "t_decision_ms": ahora,
            "t_command_ms": ahora,  # el adaptador lo sobreescribe con su propio reloj al recibir
            "valid_until_ms": ahora + self._cfg.vencimiento_ms if movimiento else None,
            "received": False,
            "error": None,
            "synthetic": decision.synthetic,
        }
