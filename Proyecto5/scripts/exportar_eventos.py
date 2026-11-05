"""Exporta los eventos de un recorrido a un JSONL por secuencia para el runner (P5-14).

El runner de casos (`p5.casos`) espera `datos/eventos/<secuencia>.jsonl`, con un solo
`run_id`, `frame_id` canonico y `t_capture_ms` creciente. `p5.recorrer` escribe un unico
`detecciones.jsonl`; este script lo valida y lo divide sin cambiar IDs, orden ni tiempos.

    python scripts/exportar_eventos.py \
        --detecciones resultados/recorrido-eventos/detecciones.jsonl \
        --run resultados/recorrido-eventos/run.json \
        --cortes resultados/recorrido-eventos/cortes.json \
        --salida datos/eventos

Escribe `S1.jsonl` ... `S6.jsonl` y `eventos_origen.json` con los hashes de la corrida y
el modo de reproduccion. Si un archivo ya existe con otro contenido, falla salvo `--force`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import OrderedDict
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from p5.contrato import (
    ContratoError,
    PerceptionEvent,
    validar_evento,
    validar_run_header,
    validar_secuencia,
)


class EventosError(ValueError):
    """La corrida o los eventos no cumplen el contrato."""


def sha256_archivo(ruta: Path) -> str:
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


def _leer_run(ruta: Path) -> dict[str, Any]:
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        header = validar_run_header(datos)
    except (OSError, json.JSONDecodeError, ContratoError) as exc:
        raise EventosError(f"{ruta}: cabecera de corrida invalida ({exc})") from exc
    return asdict(header)


def _leer_eventos(ruta: Path) -> list[PerceptionEvent]:
    eventos: list[PerceptionEvent] = []
    try:
        lineas = ruta.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise EventosError(f"{ruta}: no se pudo leer ({exc})") from exc
    for numero, linea in enumerate(lineas, 1):
        if not linea.strip():
            continue
        try:
            eventos.append(validar_evento(json.loads(linea)))
        except (json.JSONDecodeError, ContratoError) as exc:
            raise EventosError(f"{ruta}:{numero}: evento invalido ({exc})") from exc
    if not eventos:
        raise EventosError(f"{ruta}: no tiene eventos")
    return eventos


def _agrupar(eventos: list[PerceptionEvent]) -> OrderedDict[str, list[PerceptionEvent]]:
    grupos: OrderedDict[str, list[PerceptionEvent]] = OrderedDict()
    for evento in eventos:
        grupos.setdefault(evento.sequence_id, []).append(evento)
    for secuencia, propios in grupos.items():
        errores = validar_secuencia(propios)
        if errores:
            raise EventosError(f"{secuencia}: secuencia invalida: " + "; ".join(errores))
    return grupos


def _lineas(eventos: list[PerceptionEvent]) -> str:
    return "".join(json.dumps(asdict(evento), ensure_ascii=False) + "\n" for evento in eventos)


def _escribir(ruta: Path, contenido: str, force: bool) -> None:
    if ruta.exists() and ruta.read_text(encoding="utf-8") != contenido and not force:
        raise EventosError(f"{ruta}: ya existe con otro contenido; usa --force para reemplazarlo")
    ruta.write_text(contenido, encoding="utf-8")


def exportar(
    detecciones: Path,
    run: Path,
    salida: Path,
    *,
    cortes: Path | None = None,
    force: bool = False,
) -> dict[str, Any]:
    header = _leer_run(run)
    eventos = _leer_eventos(detecciones)
    run_ids = {evento.run_id for evento in eventos}
    if run_ids != {header["run_id"]}:
        raise EventosError(
            f"los eventos traen run_id {sorted(run_ids)!r} y la cabecera {header['run_id']!r}"
        )
    modelos = {evento.model_sha256 for evento in eventos}
    configs = {evento.config_sha256 for evento in eventos}
    if modelos != {header["model_sha256"]}:
        raise EventosError("el model_sha256 de los eventos no coincide con run.json")
    if configs != {header["config_sha256"]}:
        raise EventosError("el config_sha256 de los eventos no coincide con run.json")

    grupos = _agrupar(eventos)
    salida.mkdir(parents=True, exist_ok=True)
    for secuencia, propios in grupos.items():
        _escribir(salida / f"{secuencia}.jsonl", _lineas(propios), force)

    cortes_datos: dict[str, Any] | None = None
    if cortes is not None:
        try:
            cortes_datos = json.loads(cortes.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise EventosError(f"{cortes}: no se pudo leer ({exc})") from exc
        if not isinstance(cortes_datos, dict) or "modo" not in cortes_datos:
            raise EventosError(f"{cortes}: se espera un mapa con modo")
        if cortes_datos.get("total") not in (None, len(cortes_datos.get("cortes", []))):
            raise EventosError(f"{cortes}: total no coincide con la lista de cortes")

    origen = {
        "schema_version": "1.0",
        "run_id": header["run_id"],
        "commit": header["commit"],
        "model_sha256": header["model_sha256"],
        "config_sha256": header["config_sha256"],
        "data_manifest_sha256": header["data_manifest_sha256"],
        "replay_dt_ms": header.get("replay_dt_ms"),
        "detecciones_sha256": sha256_archivo(detecciones),
        "cortes_sha256": sha256_archivo(cortes) if cortes is not None else None,
        "modo": cortes_datos.get("modo") if cortes_datos else "desconocido",
        "cortes_total": cortes_datos.get("total") if cortes_datos else None,
        "secuencias": {secuencia: len(propios) for secuencia, propios in grupos.items()},
        "total": len(eventos),
        "generado_utc": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    (salida / "eventos_origen.json").write_text(
        json.dumps(origen, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return origen


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--detecciones", type=Path, required=True, help="detecciones.jsonl")
    parser.add_argument("--run", type=Path, required=True, help="run.json de la corrida")
    parser.add_argument("--cortes", type=Path, help="cortes.json de la corrida")
    parser.add_argument("--salida", type=Path, required=True, help="carpeta de los S*.jsonl")
    parser.add_argument(
        "--force", action="store_true", help="reemplaza archivos existentes con otro contenido"
    )
    args = parser.parse_args(argv)

    try:
        origen = exportar(
            args.detecciones,
            args.run,
            args.salida,
            cortes=args.cortes,
            force=args.force,
        )
    except (EventosError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    secuencias = ", ".join(
        f"{secuencia}={total}" for secuencia, total in origen["secuencias"].items()
    )
    print(f"Eventos exportados: {origen['total']} ({secuencias})")
    print(f"Modo: {origen['modo']}; cortes: {origen['cortes_total']}")
    print(f"Salida: {args.salida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
