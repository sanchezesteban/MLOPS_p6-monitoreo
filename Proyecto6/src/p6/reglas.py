"""Reglas de alerta evaluadas por ventana.

Ventana = `tamano_frames` frames consecutivos del stream (todos los estados cuentan para el
tamano). Una ventana es SUFICIENTE si tiene al menos `minimo_puntuados` frames puntuados
(estado ok); si no, es INSUFICIENTE: no se interpreta como normal ni como anormal.

Cada regla devuelve por ventana una `Decision` con `condicion`:
  True  -> la condicion se cumple (abrir o mantener la alerta)
  False -> se evaluo y no se cumple (resolver la alerta si estaba abierta)
  None  -> no evaluable (ventana insuficiente o sin referencia compatible): no abre ni cierra

Reglas:
  baja_confianza          proporcion de frames en zona baja >= proporcion_minima
  cambio_sostenido        (proporcion - referencia) >= tolerancia durante
                          `ventanas_consecutivas` ventanas suficientes seguidas; las
                          insuficientes no cuentan ni reinician la racha
  evidencia_insuficiente  `ventanas_consecutivas` ventanas insuficientes seguidas
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from p6.config import ConfigMonitoreo


@dataclass
class Ventana:
    seq: int
    window_id: str
    frames: int
    puntuados: int
    bajos: int
    suficiente: bool
    proporcion_baja: float | None
    event_ids_bajos: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Decision:
    regla: str  # clave en config (baja_confianza, ...)
    condicion: bool | None
    motivo: str
    ventanas: tuple[int, ...]  # ventanas que sustentan la condicion


def referencia_compatible(
    ref: dict[str, Any] | None, cfg: ConfigMonitoreo, model_sha: str, det_sha: str
) -> tuple[bool, str]:
    """La comparacion exige el mismo modelo, preprocesamiento/detector y umbral inferior."""
    if ref is None:
        return False, "sin referencia configurada"
    faltan = []
    if ref.get("model_sha256") != model_sha:
        faltan.append("modelo distinto")
    if ref.get("detector_config_sha256") != det_sha:
        faltan.append("configuracion del detector distinta")
    if ref.get("umbral_inferior") != cfg.umbral_inferior:
        faltan.append("umbral inferior distinto")
    if ref.get("proporcion_baja") is None:
        faltan.append("referencia sin proporcion")
    return (not faltan), ("; ".join(faltan) or "compatible")


class MotorReglas:
    def __init__(
        self, cfg: ConfigMonitoreo, referencia: dict[str, Any] | None, referencia_ok: bool
    ) -> None:
        self.cfg = cfg
        self.ref = referencia if referencia_ok else None
        self._racha_excede: list[int] = []
        self._racha_insuf: list[int] = []

    def evaluar(self, v: Ventana) -> list[Decision]:
        return [self._baja(v), self._sostenido(v), self._insuficiente(v)]

    def _baja(self, v: Ventana) -> Decision:
        p = self.cfg.reglas["baja_confianza"].params
        minimo = float(p["proporcion_minima"])
        if not v.suficiente:
            return Decision(
                "baja_confianza",
                None,
                f"ventana insuficiente ({v.puntuados} puntuados < "
                f"{self.cfg.minimo_puntuados}); no evaluable",
                (),
            )
        cumple = v.proporcion_baja >= minimo
        return Decision(
            "baja_confianza",
            cumple,
            f"{v.bajos}/{v.puntuados} frames puntuados con s < {self.cfg.umbral_inferior} "
            f"(proporcion {v.proporcion_baja:.3f} {'>=' if cumple else '<'} {minimo})",
            (v.seq,),
        )

    def _sostenido(self, v: Ventana) -> Decision:
        p = self.cfg.reglas["cambio_sostenido"].params
        tol, k = float(p["tolerancia"]), int(p["ventanas_consecutivas"])
        if self.ref is None:
            return Decision("cambio_sostenido", None, "sin referencia compatible; no evaluable", ())
        if not v.suficiente:
            return Decision(
                "cambio_sostenido",
                None,
                f"ventana insuficiente; racha se conserva en {len(self._racha_excede)}",
                tuple(self._racha_excede),
            )
        pref = float(self.ref["proporcion_baja"])
        delta = v.proporcion_baja - pref
        if delta >= tol:
            self._racha_excede.append(v.seq)
        else:
            self._racha_excede = []
        cumple = len(self._racha_excede) >= k
        return Decision(
            "cambio_sostenido",
            cumple,
            f"proporcion baja {v.proporcion_baja:.3f} vs referencia {pref:.3f} "
            f"(delta {delta:+.3f}, tolerancia {tol}); racha {len(self._racha_excede)}/{k}",
            tuple(self._racha_excede),
        )

    def _insuficiente(self, v: Ventana) -> Decision:
        k = int(self.cfg.reglas["evidencia_insuficiente"].params["ventanas_consecutivas"])
        if v.suficiente:
            self._racha_insuf = []
        else:
            self._racha_insuf.append(v.seq)
        cumple = len(self._racha_insuf) >= k
        return Decision(
            "evidencia_insuficiente",
            cumple,
            f"{len(self._racha_insuf)} ventanas insuficientes seguidas (umbral {k}); "
            f"esta ventana: {v.puntuados}/{v.frames} frames puntuados",
            tuple(self._racha_insuf),
        )
