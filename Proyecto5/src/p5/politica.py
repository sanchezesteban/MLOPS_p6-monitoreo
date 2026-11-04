"""Politica temporal (grupo B): convierte eventos de percepcion en decisiones (`docs/politica.md`).

Modulo puro: recibe un `PerceptionEvent` del contrato v1 y su propio estado, y devuelve una
`Decision` con estados, accion, razon, velocidad y direccion. No lee etiquetas, expectativas,
relojes ni hardware; los tiempos, el vencimiento y el watchdog los agrega quien arma el comando.

Reglas, en orden de prioridad:
1. `status` error o stale: STOP (nunca equivale a via libre).
2. Obstaculo cierto que toca el centro en zona de riesgo: STOP inmediato.
3. Tras una parada (inicio, bloqueo o falla): STOP hasta `cuadros_liberar` cuadros validos
   consecutivos con el centro libre de obstaculos ciertos e inciertos (histeresis).
4. Obstaculo incierto en el centro en riesgo, o cierto en el centro lejos: avance en precaucion.
5. Obstaculo cierto solo a un lado: corrige hacia el lado contrario si esa zona esta libre;
   si no, avance en precaucion por el centro libre.
6. Sin obstaculos relevantes: avance de crucero.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml

from p5.contrato import Action, Detection, PerceptionEvent, Zone

Estado = Literal["INICIO", "AVANCE", "CORRECCION", "PRECAUCION", "BLOQUEADO", "FALLA"]
Certeza = Literal["cierto", "incierto"]
ESTADOS_DETENIDOS = frozenset({"INICIO", "BLOQUEADO", "FALLA"})
_EVENTO_STATUS = {"stale": "stale_frame", "error": "detector_error"}


class ConfigPoliticaError(ValueError):
    """Configuracion rechazada; `errores` lista cada problema encontrado."""

    def __init__(self, errores: list[str]) -> None:
        super().__init__("configuracion de politica invalida: " + "; ".join(errores))
        self.errores = errores


@dataclass(frozen=True)
class ConfigPolitica:
    clases_obstaculo: frozenset[str]
    umbral: float
    minimo_incierto: float
    limite_izquierda: float
    limite_derecha: float
    riesgo_y: float
    cuadros_liberar: int
    velocidad_crucero: float
    velocidad_precaucion: float
    giro_correccion: float


@dataclass(frozen=True)
class Obstaculo:
    """Deteccion de una clase relevante con su certeza, zonas y proxy de cercania."""

    deteccion: Detection
    certeza: Certeza
    zonas: frozenset[Zone]
    en_riesgo: bool


@dataclass(frozen=True)
class Decision:
    frame_id: str | None
    event: str | None
    detections_ref: str | None
    state_before: Estado
    state_after: Estado
    action: Action
    reason: str
    speed: float
    steering: float
    synthetic: bool


_ESQUEMA = {
    "version": None,
    "clases_obstaculo": None,
    "confianza": ("umbral", "minimo_incierto"),
    "zonas": ("limite_izquierda", "limite_derecha", "riesgo_y"),
    "histeresis": ("cuadros_liberar",),
    "comandos": ("velocidad_crucero", "velocidad_precaucion", "giro_correccion"),
}


def _numero(valor: Any) -> bool:
    return isinstance(valor, int | float) and not isinstance(valor, bool) and math.isfinite(valor)


def validar_config(data: Any) -> ConfigPolitica:
    """Revisa claves, tipos y rangos; cualquier problema lanza `ConfigPoliticaError`."""
    if not isinstance(data, dict):
        raise ConfigPoliticaError(["(raiz): se espera un mapa"])
    errores = [f"(raiz): clave desconocida {k}" for k in data if k not in _ESQUEMA]
    errores += [f"(raiz): falta {k}" for k in _ESQUEMA if k not in data]
    if errores:
        raise ConfigPoliticaError(errores)
    if data["version"] != 1:
        errores.append(f"version: se espera 1, llego {data['version']!r}")

    clases = data["clases_obstaculo"]
    if not isinstance(clases, list) or not clases:
        errores.append("clases_obstaculo: se espera una lista no vacia")
    elif not all(isinstance(c, str) and c.strip() for c in clases):
        errores.append("clases_obstaculo: cada clase debe ser texto no vacio")
    elif len(set(clases)) != len(clases):
        errores.append("clases_obstaculo: hay clases repetidas")

    planos: dict[str, Any] = {}
    for seccion, claves in _ESQUEMA.items():
        if claves is None:
            continue
        valor = data[seccion]
        if not isinstance(valor, dict):
            errores.append(f"{seccion}: se espera un mapa")
            continue
        errores += [f"{seccion}: clave desconocida {k}" for k in valor if k not in claves]
        for k in claves:
            if k not in valor:
                errores.append(f"{seccion}: falta {k}")
            elif not _numero(valor[k]):
                errores.append(f"{seccion}.{k}: se espera un numero finito")
            else:
                planos[k] = valor[k]
    if errores:
        raise ConfigPoliticaError(errores)

    p = planos
    if not 0 < p["umbral"] <= 1:
        errores.append("confianza.umbral: debe estar en (0, 1]")
    if not 0 <= p["minimo_incierto"] <= p["umbral"]:
        errores.append("confianza.minimo_incierto: debe estar en [0, umbral]")
    if not 0 < p["limite_izquierda"] < p["limite_derecha"] < 1:
        errores.append("zonas: se espera 0 < limite_izquierda < limite_derecha < 1 (sin solape)")
    if not 0 < p["riesgo_y"] <= 1:
        errores.append("zonas.riesgo_y: debe estar en (0, 1]")
    if not isinstance(p["cuadros_liberar"], int) or p["cuadros_liberar"] < 1:
        errores.append("histeresis.cuadros_liberar: se espera un entero >= 1")
    if not 0 < p["velocidad_crucero"] <= 1:
        errores.append("comandos.velocidad_crucero: debe estar en (0, 1]")
    if not 0 < p["velocidad_precaucion"] <= p["velocidad_crucero"]:
        errores.append("comandos.velocidad_precaucion: debe estar en (0, velocidad_crucero]")
    if not 0 < p["giro_correccion"] <= 1:
        errores.append("comandos.giro_correccion: debe estar en (0, 1]")
    if errores:
        raise ConfigPoliticaError(errores)

    return ConfigPolitica(clases_obstaculo=frozenset(clases), **p)


def cargar_config(ruta: str | Path) -> ConfigPolitica:
    """Lee y valida `politica.yaml`; un YAML ilegible tambien es configuracion invalida."""
    try:
        data = yaml.safe_load(Path(ruta).read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigPoliticaError([f"{ruta}: no se pudo leer ({exc})"]) from exc
    return validar_config(data)


def zonas_ocupadas(
    bbox: tuple[float, float, float, float], width: int, cfg: ConfigPolitica
) -> frozenset[Zone]:
    """Como `p5.contrato.zonas_ocupadas`, con los limites de la configuracion."""
    x1, _, x2, _ = bbox
    izq, der = cfg.limite_izquierda * width, cfg.limite_derecha * width
    zonas: set[Zone] = set()
    if x1 < izq:
        zonas.add("izquierda")
    if x1 <= der and x2 >= izq:
        zonas.add("centro")
    if x2 > der:
        zonas.add("derecha")
    return frozenset(zonas)


def obstaculos(evento: PerceptionEvent, cfg: ConfigPolitica) -> list[Obstaculo]:
    """Todas las detecciones relevantes del cuadro, no solo la de mayor confianza."""
    resultado = []
    for det in evento.detections:
        if det.class_name not in cfg.clases_obstaculo or det.confidence < cfg.minimo_incierto:
            continue
        certeza: Certeza = "cierto" if det.confidence >= cfg.umbral else "incierto"
        resultado.append(
            Obstaculo(
                deteccion=det,
                certeza=certeza,
                zonas=zonas_ocupadas(det.bbox, evento.image_width, cfg),
                en_riesgo=det.bbox[3] >= cfg.riesgo_y * evento.image_height,
            )
        )
    return resultado


class Politica:
    """Maquina de estados de la politica; una instancia por corrida."""

    def __init__(self, cfg: ConfigPolitica) -> None:
        self.cfg = cfg
        self.estado: Estado = "INICIO"
        self._libres = 0

    def decidir(self, evento: PerceptionEvent) -> Decision:
        """Decision para un cuadro; actualiza el estado interno."""
        if evento.status != "ok":
            razon = "cuadro_vencido" if evento.status == "stale" else "error_percepcion"
            return self._parar(evento, "FALLA", razon)

        obs = obstaculos(evento, self.cfg)
        riesgo = [o for o in obs if o.en_riesgo]
        if any(o.certeza == "cierto" and "centro" in o.zonas for o in riesgo):
            return self._parar(evento, "BLOQUEADO", "obstaculo_centro_riesgo")

        centro_incierto = any("centro" in o.zonas for o in riesgo)
        if self.estado in ESTADOS_DETENIDOS:
            self._libres = 0 if centro_incierto else self._libres + 1
            if self._libres < self.cfg.cuadros_liberar:
                razon = "obstaculo_incierto_centro" if centro_incierto else "esperando_liberacion"
                return self._decision(evento, self.estado, "STOP", razon)

        cfg = self.cfg
        if centro_incierto:
            return self._mover(
                evento, "PRECAUCION", "obstaculo_incierto_centro", cfg.velocidad_precaucion, 0.0
            )
        ciertos = [o for o in riesgo if o.certeza == "cierto"]
        izq = any("izquierda" in o.zonas for o in ciertos)
        der = any("derecha" in o.zonas for o in ciertos)
        if izq or der:
            # destino libre: ningun obstaculo, cierto o incierto, en riesgo en esa zona
            if izq and not der and not any("derecha" in o.zonas for o in riesgo):
                return self._mover(
                    evento,
                    "CORRECCION",
                    "obstaculo_izquierda",
                    cfg.velocidad_precaucion,
                    cfg.giro_correccion,
                )
            if der and not izq and not any("izquierda" in o.zonas for o in riesgo):
                return self._mover(
                    evento,
                    "CORRECCION",
                    "obstaculo_derecha",
                    cfg.velocidad_precaucion,
                    -cfg.giro_correccion,
                )
            return self._mover(
                evento,
                "PRECAUCION",
                "obstaculos_laterales_centro_libre",
                cfg.velocidad_precaucion,
                0.0,
            )
        if riesgo:
            # solo quedan inciertos laterales en riesgo: bajan la velocidad, pero nunca giran
            return self._mover(
                evento, "PRECAUCION", "obstaculo_incierto_lateral", cfg.velocidad_precaucion, 0.0
            )
        if any(o.certeza == "cierto" and "centro" in o.zonas for o in obs):
            return self._mover(
                evento, "PRECAUCION", "obstaculo_centro_lejos", cfg.velocidad_precaucion, 0.0
            )
        return self._mover(evento, "AVANCE", "via_libre", cfg.velocidad_crucero, 0.0)

    def detener(self, event: str, razon: str) -> Decision:
        """STOP por un evento sin cuadro (watchdog, error del detector, cierre). Pasa a FALLA,
        asi que reanudar exige otra vez `cuadros_liberar` cuadros validos con centro libre."""
        antes = self.estado
        self.estado, self._libres = "FALLA", 0
        return Decision(None, event, None, antes, "FALLA", "STOP", razon, 0.0, 0.0, False)

    def _parar(self, evento: PerceptionEvent, estado: Estado, razon: str) -> Decision:
        self._libres = 0
        return self._decision(evento, estado, "STOP", razon)

    def _mover(
        self, evento: PerceptionEvent, estado: Estado, razon: str, speed: float, steering: float
    ) -> Decision:
        if steering > 0:
            action: Action = "STEER_RIGHT"
        elif steering < 0:
            action = "STEER_LEFT"
        else:
            action = "FORWARD"
        return self._decision(evento, estado, action, razon, speed, steering)

    def _decision(
        self,
        evento: PerceptionEvent,
        estado: Estado,
        action: Action,
        razon: str,
        speed: float = 0.0,
        steering: float = 0.0,
    ) -> Decision:
        antes, self.estado = self.estado, estado
        ok = evento.status == "ok"
        return Decision(
            frame_id=evento.frame_id,
            event=None if ok else _EVENTO_STATUS[evento.status],
            detections_ref=evento.frame_id if ok else None,
            state_before=antes,
            state_after=estado,
            action=action,
            reason=razon,
            speed=speed,
            steering=steering,
            synthetic=evento.synthetic,
        )
