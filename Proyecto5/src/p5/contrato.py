"""Contrato v1 entre percepcion (grupo A), politica (grupo B) y adaptador (`config/contrato_v1.md`).

Dos capas: el JSON Schema de `config/schemas/` revisa forma, tipos y rangos; este
modulo agrega las reglas entre campos (caja dentro del cuadro, `status` coherente
con `error_msg`, `STOP` con velocidad cero y sin vencimiento, `frame_id` igual a
`detections_ref` cuando ambos existen, numeros finitos). Un mensaje es valido
solo si pasa las dos. Los validadores devuelven dataclasses inmutables.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any, Literal

from jsonschema import Draft202012Validator

SCHEMA_VERSION = "1.0"
SCHEMAS_DIR = Path(__file__).resolve().parents[2] / "config" / "schemas"

Status = Literal["ok", "stale", "error"]
Action = Literal["FORWARD", "STEER_LEFT", "STEER_RIGHT", "STOP"]
MOVEMENT_ACTIONS = frozenset({"FORWARD", "STEER_LEFT", "STEER_RIGHT"})
Zone = Literal["izquierda", "centro", "derecha"]
RISK_Y_FRACTION = 0.5


class ContratoError(ValueError):
    """Mensaje fuera de contrato; `errores` lista cada problema encontrado."""

    def __init__(self, tipo: str, errores: list[str]) -> None:
        super().__init__(f"{tipo} invalido: " + "; ".join(errores))
        self.errores = errores


@dataclass(frozen=True)
class Detection:
    class_name: str
    class_id: int
    confidence: float
    bbox: tuple[float, float, float, float]


@dataclass(frozen=True)
class PerceptionEvent:
    schema_version: str
    run_id: str
    sequence_id: str
    frame_id: str
    t_capture_ms: float
    image_path: str | None
    image_sha256: str | None
    image_width: int | None
    image_height: int | None
    model_sha256: str
    config_sha256: str
    status: Status
    error_msg: str | None
    synthetic: bool
    detections: tuple[Detection, ...]
    t_capture_origen_ms: float | None = None


@dataclass(frozen=True)
class Command:
    schema_version: str
    run_id: str
    frame_id: str | None
    event: str | None
    detections_ref: str | None
    state_before: str
    state_after: str
    action: Action
    reason: str
    speed: float
    steering: float
    t_decision_ms: float
    t_command_ms: float
    valid_until_ms: float | None
    received: bool
    error: str | None
    synthetic: bool


@dataclass(frozen=True)
class RunHeader:
    schema_version: str
    run_id: str
    commit: str
    model_sha256: str
    config_sha256: str
    data_manifest_sha256: str
    runtime: str
    hardware: str
    virtual_mode: bool
    t_start_utc: str
    replay_dt_ms: float | None = None


@cache
def _validator(nombre: str) -> Draft202012Validator:
    schema = json.loads((SCHEMAS_DIR / f"{nombre}.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def _schema_errors(nombre: str, data: Any) -> list[str]:
    errores = sorted(_validator(nombre).iter_errors(data), key=lambda e: list(e.absolute_path))
    return [f"{'.'.join(map(str, e.absolute_path)) or '(raiz)'}: {e.message}" for e in errores]


def _non_finite(data: Any, path: str = "") -> list[str]:
    # json.loads acepta NaN e Infinity; el schema no los rechaza por si solo
    if isinstance(data, float) and not math.isfinite(data):
        return [f"{path or '(raiz)'}: numero no finito ({data})"]
    if isinstance(data, dict):
        return [e for k, v in data.items() for e in _non_finite(v, f"{path}.{k}" if path else k)]
    if isinstance(data, list):
        return [e for i, v in enumerate(data) for e in _non_finite(v, f"{path}.{i}")]
    return []


def _check(tipo: str, nombre: str, data: Any, reglas) -> None:
    errores = _non_finite(data) + _schema_errors(nombre, data)
    if not errores:
        errores = reglas(data)
    if errores:
        raise ContratoError(tipo, errores)


def _event_rules(d: dict[str, Any]) -> list[str]:
    errores: list[str] = []
    status, w, h = d["status"], d["image_width"], d["image_height"]
    if status == "ok" and d["error_msg"] is not None:
        errores.append("error_msg debe ser null con status=ok")
    if status in ("error", "stale") and not d["error_msg"]:
        errores.append(f"error_msg es obligatorio con status={status}")
    if status in ("error", "stale") and d["detections"]:
        errores.append(f"detections debe ir vacia con status={status}")
    if status != "error":
        for campo in ("image_path", "image_sha256", "image_width", "image_height"):
            if d[campo] is None:
                errores.append(f"{campo} solo puede ser null con status=error")
    if d["detections"] and (w is None or h is None):
        errores.append("hay detecciones sin dimensiones del cuadro")
    for i, det in enumerate(d["detections"]):
        x1, y1, x2, y2 = det["bbox"]
        if not (x1 < x2 and y1 < y2):
            errores.append(f"detections.{i}.bbox: se espera x1<x2 y y1<y2 (xyxy)")
        if w is not None and h is not None and (x2 > w or y2 > h):
            errores.append(f"detections.{i}.bbox: sale del cuadro {w}x{h}")
    return errores


def _command_rules(d: dict[str, Any]) -> list[str]:
    errores: list[str] = []
    action, speed, steering = d["action"], d["speed"], d["steering"]
    if d["frame_id"] is None and d["event"] is None:
        errores.append("frame_id o event debe ser no nulo")
    if (
        d["frame_id"] is not None
        and d["detections_ref"] is not None
        and d["frame_id"] != d["detections_ref"]
    ):
        errores.append("frame_id y detections_ref deben coincidir")
    if d["t_command_ms"] < d["t_decision_ms"]:
        errores.append("t_command_ms no puede ser anterior a t_decision_ms")
    if action == "STOP":
        if speed != 0 or steering != 0:
            errores.append("STOP exige speed=0 y steering=0")
        if d["valid_until_ms"] is not None:
            errores.append("STOP exige valid_until_ms=null")
    else:
        if speed <= 0:
            errores.append(f"{action} exige speed>0")
        if d["valid_until_ms"] is None:
            errores.append(f"{action} exige valid_until_ms")
        elif d["valid_until_ms"] <= d["t_command_ms"]:
            errores.append("valid_until_ms debe ser posterior a t_command_ms")
        if action == "FORWARD" and steering != 0:
            errores.append("FORWARD exige steering=0")
        if action == "STEER_LEFT" and steering >= 0:
            errores.append("STEER_LEFT exige steering<0")
        if action == "STEER_RIGHT" and steering <= 0:
            errores.append("STEER_RIGHT exige steering>0")
    return errores


def validar_evento(data: Any) -> PerceptionEvent:
    _check("evento de percepcion", "evento_percepcion", data, _event_rules)
    dets = tuple(
        Detection(d["class_name"], d["class_id"], float(d["confidence"]), tuple(d["bbox"]))
        for d in data["detections"]
    )
    return PerceptionEvent(**{**data, "detections": dets})


def validar_comando(data: Any) -> Command:
    _check("comando", "comando", data, _command_rules)
    return Command(**data)


def validar_run_header(data: Any) -> RunHeader:
    _check("cabecera de ejecucion", "run_header", data, lambda _: [])
    return RunHeader(**data)


def validar_secuencia(eventos: list[PerceptionEvent]) -> list[str]:
    """Problemas de una corrida: otro `run_id`, `frame_id` repetido o sin prefijo de su
    secuencia, o `t_capture_ms` no creciente (el reloj es uno solo por `run_id`)."""
    errores: list[str] = []
    vistos: set[str] = set()
    previo: float | None = None
    for ev in eventos:
        if ev.run_id != eventos[0].run_id:
            errores.append(f"{ev.frame_id}: run_id {ev.run_id} distinto de {eventos[0].run_id}")
        if not ev.frame_id.startswith(f"{ev.sequence_id}_"):
            errores.append(f"{ev.frame_id}: frame_id no empieza con {ev.sequence_id}_")
        if ev.frame_id in vistos:
            errores.append(f"frame_id repetido: {ev.frame_id}")
        vistos.add(ev.frame_id)
        if previo is not None and ev.t_capture_ms <= previo:
            errores.append(f"{ev.frame_id}: t_capture_ms {ev.t_capture_ms} no supera {previo}")
        previo = ev.t_capture_ms
    return errores


def esta_vencido(t_capture_ms: float, t_now_ms: float, max_frame_age_ms: float) -> bool:
    """Regla 3 del contrato: vencido si la edad del cuadro supera `max_frame_age_ms`.

    Un cuadro "del futuro" (`t_now_ms < t_capture_ms`) indica reloj inconsistente y
    tambien cuenta como vencido, para que la politica emita STOP.
    """
    return t_now_ms < t_capture_ms or t_now_ms - t_capture_ms > max_frame_age_ms


def zonas_ocupadas(bbox: tuple[float, float, float, float], width: int) -> frozenset[Zone]:
    """Zonas que toca el intervalo horizontal de la caja (criterio conservador)."""
    x1, _, x2, _ = bbox
    tercio, dos_tercios = width / 3, 2 * width / 3
    zonas: set[Zone] = set()
    if x1 < tercio:
        zonas.add("izquierda")
    if x1 <= dos_tercios and x2 >= tercio:
        zonas.add("centro")
    if x2 > dos_tercios:
        zonas.add("derecha")
    return frozenset(zonas)


def en_riesgo(bbox: tuple[float, float, float, float], height: int) -> bool:
    """Proxy de cercania: el borde inferior llega a la mitad baja del cuadro (no son metros)."""
    return bbox[3] >= RISK_Y_FRACTION * height
