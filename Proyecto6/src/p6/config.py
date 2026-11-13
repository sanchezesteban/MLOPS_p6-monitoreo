"""Carga y valida `config/monitoreo.yaml`.

La configuracion es la unica fuente de umbrales, ventanas, reglas y politica de captura.
Su SHA-256 (`config_sha256`) se guarda en cada evento, ventana y alerta para que la
configuracion usada pueda reconstruirse desde los registros.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


class ConfigError(ValueError):
    """Configuracion rechazada (claves faltantes o valores fuera de rango)."""


@dataclass(frozen=True)
class Regla:
    id: str
    severidad: str
    accion_sugerida: str
    params: dict[str, Any]


@dataclass(frozen=True)
class ConfigMonitoreo:
    ruta: Path
    texto: str
    config_id: str
    config_sha256: str
    fps: float
    politica_muestreo: str
    detector_config: Path
    umbral_inferior: float
    umbral_superior: float
    tamano_ventana: int
    minimo_puntuados: int
    referencia: Path | None
    reglas: dict[str, Regla]
    captura_zonas: tuple[str, ...]
    captura_estados: tuple[str, ...]
    captura_muestra_cada: int
    extra: dict[str, Any] = field(default_factory=dict)

    def como_dict(self) -> dict[str, Any]:
        return yaml.safe_load(self.texto)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _num(d: dict[str, Any], clave: str, errores: list[str]) -> float | None:
    v = d.get(clave)
    if isinstance(v, bool) or not isinstance(v, int | float):
        errores.append(f"{clave} debe ser numero")
        return None
    return float(v)


def cargar(ruta: str | Path) -> ConfigMonitoreo:
    ruta = Path(ruta).resolve()
    texto = ruta.read_text(encoding="utf-8")
    data = yaml.safe_load(texto)
    if not isinstance(data, dict):
        raise ConfigError(f"{ruta}: se esperaba un mapa")
    errores: list[str] = []
    fuente = data.get("fuente") or {}
    politica = data.get("politica") or {}
    ventanas = data.get("ventanas") or {}
    captura = data.get("captura") or {}
    inf = _num(politica, "umbral_inferior", errores)
    sup = _num(politica, "umbral_superior", errores)
    if inf is not None and sup is not None and not 0 <= inf < sup <= 1:
        errores.append("se exige 0 <= umbral_inferior < umbral_superior <= 1")
    fps = _num(fuente, "fps", errores)
    if fps is not None and fps <= 0:
        errores.append("fuente.fps debe ser positivo")
    tam = ventanas.get("tamano_frames")
    minimo = ventanas.get("minimo_puntuados")
    if not isinstance(tam, int) or tam <= 0:
        errores.append("ventanas.tamano_frames debe ser entero positivo")
    if not isinstance(minimo, int) or minimo <= 0 or (isinstance(tam, int) and minimo > tam):
        errores.append("ventanas.minimo_puntuados debe ser entero en [1, tamano_frames]")
    reglas: dict[str, Regla] = {}
    for rid, r in (data.get("reglas") or {}).items():
        if not isinstance(r, dict) or not {"id", "severidad", "accion_sugerida"} <= set(r):
            errores.append(f"regla {rid}: faltan id, severidad o accion_sugerida")
            continue
        params = {k: v for k, v in r.items() if k not in {"id", "severidad", "accion_sugerida"}}
        reglas[rid] = Regla(r["id"], r["severidad"], r["accion_sugerida"], params)
    for necesaria in ("baja_confianza", "cambio_sostenido", "evidencia_insuficiente"):
        if necesaria not in reglas:
            errores.append(f"falta la regla {necesaria}")
    muestra = captura.get("muestra_cada")
    if not isinstance(muestra, int) or muestra <= 0:
        errores.append("captura.muestra_cada debe ser entero positivo")
    if errores:
        raise ConfigError(f"{ruta}: " + "; ".join(errores))
    base = ruta.parent
    ref = data.get("referencia", {}).get("archivo")
    return ConfigMonitoreo(
        ruta=ruta,
        texto=texto,
        config_id=str(data.get("config_id", "sin-id")),
        config_sha256=sha256_bytes(texto.encode("utf-8")),
        fps=float(fps),
        politica_muestreo=str(fuente.get("politica_muestreo", "")),
        detector_config=(base / data["detector"]["config"]).resolve(),
        umbral_inferior=float(inf),
        umbral_superior=float(sup),
        tamano_ventana=tam,
        minimo_puntuados=minimo,
        referencia=(base / ref).resolve() if ref else None,
        reglas=reglas,
        captura_zonas=tuple(captura.get("zonas", [])),
        captura_estados=tuple(captura.get("estados", [])),
        captura_muestra_cada=muestra,
    )


def cargar_referencia(ruta: Path | None) -> dict[str, Any] | None:
    if ruta is None or not ruta.is_file():
        return None
    return json.loads(ruta.read_text(encoding="utf-8"))
