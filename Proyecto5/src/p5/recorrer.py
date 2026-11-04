"""Recorrido integral cuadros -> detector -> politica -> adaptador (P5-14).

Uso:

    PYTHONPATH=src python -m p5.recorrer \
        --datos datos/simulacion \
        --config config/politica.yaml \
        --salida resultados/recorrido

El detector se inyecta detras de `p5.detector.Detector`: `DetectorONNX` para las capturas
reales y `DetectorSimulado` para pruebas deterministas. El reproductor toma el orden y los
tiempos del manifiesto, pero arma el reloj de la ejecucion: cada secuencia avanza
`--replay-dt-ms` por cuadro (100 ms por defecto) y entre secuencias deja un hueco mayor que
el watchdog. El `t_capture_ms` original se conserva en el manifiesto y como
`t_capture_origen_ms` en cada evento. No hay sleeps: el reloj se avanza a mano.

Salidas: `run.json`, `detecciones.jsonl` (un `PerceptionEvent` por cuadro),
`decisiones.jsonl` y `comandos.jsonl`, todos vinculados por `frame_id`.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import subprocess
import sys
from collections.abc import Callable
from dataclasses import asdict, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from p5.contrato import (
    PerceptionEvent,
    validar_evento,
    validar_run_header,
    validar_secuencia,
)
from p5.control import AdaptadorVirtual
from p5.detector import Detector, DetectorSimulado, Frame
from p5.detector_onnx import DetectorONNX
from p5.detector_onnx import cargar_config as cargar_config_detector
from p5.politica import Politica, cargar_config
from p5.watchdog import ConfigWatchdog, RelojControlado, Watchdog
from p5.watchdog import cargar_config as cargar_config_watchdog

HASH_CERO = "0" * 64


class InsumoFaltanteError(RuntimeError):
    """Falta el manifiesto, una imagen o un guion de simulacion."""


class RecorridoInvalidoError(ValueError):
    """El manifiesto o la corrida no cumplen el contrato."""


class PoliticaGrabada:
    """Delegado de `Politica` que conserva cada `Decision` para `decisiones.jsonl`."""

    def __init__(self, politica: Politica) -> None:
        self._politica = politica
        self.decisiones: list[dict[str, Any]] = []

    @property
    def estado(self) -> str:
        return self._politica.estado

    def decidir(self, evento: PerceptionEvent) -> Any:
        decision = self._politica.decidir(evento)
        self.decisiones.append(asdict(decision))
        return decision

    def detener(self, event: str, razon: str) -> Any:
        decision = self._politica.detener(event, razon)
        self.decisiones.append(asdict(decision))
        return decision


def sha256_archivo(ruta: Path) -> str:
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


def _commit_actual() -> str:
    try:
        salida = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=Path.cwd(),
            capture_output=True,
            check=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return "desconocido"
    return salida.stdout.strip() or "desconocido"


def leer_manifiesto(ruta: Path, datos: Path) -> list[Frame]:
    if not ruta.is_file():
        raise InsumoFaltanteError(f"{ruta}: no existe el manifiesto")
    columnas = {
        "sequence_id",
        "frame_id",
        "t_capture_ms",
        "image_width",
        "image_height",
    }
    frames: list[Frame] = []
    contadores: dict[str, int] = {}
    with ruta.open(encoding="utf-8", newline="") as archivo:
        lector = csv.DictReader(archivo)
        campos = set(lector.fieldnames or [])
        faltan = columnas - campos
        if faltan:
            raise RecorridoInvalidoError(f"{ruta}: faltan columnas {sorted(faltan)}")
        if "image_path" not in campos and "path" not in campos:
            raise RecorridoInvalidoError(f"{ruta}: falta image_path o path")
        for numero, fila in enumerate(lector, 2):
            status = (fila.get("status") or "ok").strip()
            if status not in {"ok", "stale", "error"}:
                raise RecorridoInvalidoError(f"{ruta}:{numero}: status {status!r} invalido")
            error_msg = (fila.get("error_msg") or "").strip() or None
            if status in {"stale", "error"} and error_msg is None:
                raise RecorridoInvalidoError(f"{ruta}:{numero}: status {status} necesita error_msg")
            try:
                t_capture = float(fila["t_capture_ms"])
                ancho = int(fila["image_width"])
                alto = int(fila["image_height"])
            except (KeyError, TypeError, ValueError) as exc:
                raise RecorridoInvalidoError(f"{ruta}:{numero}: numero invalido ({exc})") from exc
            ruta_imagen = fila.get("image_path") or fila.get("path")
            if not ruta_imagen:
                raise RecorridoInvalidoError(f"{ruta}:{numero}: falta image_path/path")
            imagen = datos / ruta_imagen
            if status == "error":
                sha = HASH_CERO
            else:
                if not imagen.is_file():
                    raise InsumoFaltanteError(f"{ruta}:{numero}: falta la imagen {imagen}")
                sha = sha256_archivo(imagen)
                declarado = (fila.get("sha256") or "").strip()
                if declarado and declarado != sha:
                    raise RecorridoInvalidoError(
                        f"{ruta}:{numero}: sha256 {sha} distinto del declarado {declarado}"
                    )
            sequence_id = fila["sequence_id"]
            crudo = fila["frame_id"].strip()
            prefijo = f"{sequence_id}_f"
            if crudo.startswith(prefijo) and crudo[len(prefijo) :].isdigit():
                frame_id = crudo
            else:
                contadores[sequence_id] = contadores.get(sequence_id, 0) + 1
                frame_id = f"{prefijo}{contadores[sequence_id]:04d}"
            frames.append(
                Frame(
                    sequence_id=sequence_id,
                    frame_id=frame_id,
                    t_capture_ms=t_capture,
                    image_path=str(imagen.as_posix()),
                    image_width=ancho,
                    image_height=alto,
                    image_sha256=sha,
                    status=status,
                    error_msg=error_msg,
                    t_capture_origen_ms=t_capture,
                )
            )
    if not frames:
        raise RecorridoInvalidoError(f"{ruta}: no tiene cuadros")
    return frames


def hueco_entre_secuencias(cfg: ConfigWatchdog, replay_dt_ms: float) -> float:
    """Hueco entre secuencias que supera los plazos del watchdog."""
    return max(cfg.max_edad_ms, cfg.vencimiento_ms) + replay_dt_ms


def normalizar_tiempos(frames: list[Frame], replay_dt_ms: float, hueco_ms: float) -> list[Frame]:
    """Arma el reloj de la ejecucion a partir del orden del manifiesto.

    El primer cuadro arranca en 0; dentro de una secuencia cada cuadro avanza
    `replay_dt_ms`; al cambiar de secuencia se suma `hueco_ms`, que debe superar los plazos
    del watchdog para que el corte se note. El `t_capture_ms` original se conserva en
    `t_capture_origen_ms`. Nunca duerme.
    """
    if replay_dt_ms <= 0:
        raise RecorridoInvalidoError("--replay-dt-ms debe ser positivo")
    if hueco_ms <= 0:
        raise RecorridoInvalidoError("el hueco entre secuencias debe ser positivo")

    normalizados: list[Frame] = []
    previo: float | None = None
    previa_secuencia: str | None = None
    for frame in frames:
        origen = (
            frame.t_capture_ms if frame.t_capture_origen_ms is None else frame.t_capture_origen_ms
        )
        if previo is None:
            t = 0.0
        elif frame.sequence_id == previa_secuencia:
            t = previo + replay_dt_ms
        else:
            t = previo + hueco_ms
        normalizados.append(replace(frame, t_capture_ms=t, t_capture_origen_ms=origen))
        previo = t
        previa_secuencia = frame.sequence_id
    return normalizados


def _evento(
    frame: Frame,
    run_id: str,
    config_sha256: str,
    model_sha256: str,
    *,
    detecciones: list[Any] | None = None,
    status: str | None = None,
    error_msg: str | None = None,
    synthetic: bool,
) -> PerceptionEvent:
    estado = status or frame.status
    detecciones = [] if estado != "ok" else (detecciones or [])
    datos = {
        "schema_version": "1.0",
        "run_id": run_id,
        "sequence_id": frame.sequence_id,
        "frame_id": frame.frame_id,
        "t_capture_ms": frame.t_capture_ms,
        "t_capture_origen_ms": frame.t_capture_origen_ms,
        "image_path": None if estado == "error" else frame.image_path,
        "image_sha256": None if estado == "error" else frame.image_sha256,
        "image_width": None if estado == "error" else frame.image_width,
        "image_height": None if estado == "error" else frame.image_height,
        "model_sha256": model_sha256,
        "config_sha256": config_sha256,
        "status": estado,
        "error_msg": error_msg if estado != "ok" else None,
        "synthetic": synthetic,
        "detections": [
            {
                "class_name": d.class_name,
                "class_id": d.class_id,
                "confidence": d.confidence,
                "bbox": list(d.bbox),
            }
            for d in detecciones
        ],
    }
    return validar_evento(datos)


def correr_recorrido(
    frames: list[Frame],
    detector: Detector,
    config_path: Path,
    cfg_watchdog: ConfigWatchdog,
    salida: Path,
    *,
    run_id: str,
    commit: str,
    data_manifest_sha256: str,
    replay_dt_ms: float,
) -> dict[str, Any]:
    if salida.exists():
        raise RecorridoInvalidoError(f"{salida}: la salida debe ser una carpeta nueva")
    salida.mkdir(parents=True)
    inicio = datetime.now(UTC)
    config_sha = sha256_archivo(config_path)

    reloj = RelojControlado()
    control = AdaptadorVirtual(salida / "comandos.jsonl", run_id, reloj=reloj)
    politica = PoliticaGrabada(Politica(cargar_config(config_path)))
    watchdog = Watchdog(politica, control, reloj, cfg_watchdog, run_id)

    eventos: list[PerceptionEvent] = []
    with (salida / "detecciones.jsonl").open("w", encoding="utf-8") as detecciones_jsonl:
        for frame in frames:
            delta = frame.t_capture_ms - reloj()
            if delta < 0:
                raise RecorridoInvalidoError(
                    f"{frame.frame_id}: t_capture_ms retrocede ({frame.t_capture_ms} < {reloj()})"
                )
            reloj.avanzar(delta)
            # Revisa vencimientos aunque no haya llegado un cuadro nuevo.
            watchdog.tick()
            if frame.status != "ok":
                evento = _evento(
                    frame,
                    run_id,
                    config_sha,
                    detector.model_sha256,
                    status=frame.status,
                    error_msg=frame.error_msg,
                    synthetic=detector.synthetic,
                )
            else:
                try:
                    detecciones = detector.detectar(frame)
                except Exception as exc:  # inyeccion de fallo del detector (C9)
                    evento = _evento(
                        frame,
                        run_id,
                        config_sha,
                        detector.model_sha256,
                        status="error",
                        error_msg=f"detector: {type(exc).__name__}: {exc}",
                        synthetic=detector.synthetic,
                    )
                else:
                    evento = _evento(
                        frame,
                        run_id,
                        config_sha,
                        detector.model_sha256,
                        detecciones=detecciones,
                        synthetic=detector.synthetic,
                    )
            eventos.append(evento)
            detecciones_jsonl.write(json.dumps(asdict(evento), ensure_ascii=False) + "\n")
            watchdog.procesar_evento(evento)
    watchdog.cerrar()

    errores = validar_secuencia(eventos)
    if errores:
        raise RecorridoInvalidoError("secuencia invalida: " + "; ".join(errores))

    with (salida / "decisiones.jsonl").open("w", encoding="utf-8") as archivo:
        for decision in politica.decisiones:
            archivo.write(json.dumps(decision, ensure_ascii=False) + "\n")

    header = {
        "schema_version": "1.0",
        "run_id": run_id,
        "commit": commit,
        "model_sha256": detector.model_sha256,
        "config_sha256": config_sha,
        "data_manifest_sha256": data_manifest_sha256,
        "runtime": (
            f"{detector.nombre}: {type(detector).__name__}"
            + (" (simulado, sin onnxruntime)" if detector.synthetic else " (CPU)")
        ),
        "hardware": platform.platform(),
        "virtual_mode": True,
        "t_start_utc": inicio.isoformat(timespec="seconds"),
        "replay_dt_ms": int(replay_dt_ms) if float(replay_dt_ms).is_integer() else replay_dt_ms,
    }
    validar_run_header(header)
    (salida / "run.json").write_text(
        json.dumps(header, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return {
        "run_id": run_id,
        "eventos": len(eventos),
        "decisiones": len(politica.decisiones),
        "comandos": len((salida / "comandos.jsonl").read_text(encoding="utf-8").splitlines()),
    }


def main(
    argv: list[str] | None = None,
    *,
    fabrica_detector: Callable[[Path], Detector] | None = None,
) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--datos", type=Path, required=True, help="carpeta del manifiesto")
    parser.add_argument(
        "--manifiesto",
        type=Path,
        help="CSV de cuadros (por defecto <datos>/manifiesto.csv)",
    )
    parser.add_argument("--config", type=Path, required=True, help="politica.yaml de P5-10")
    parser.add_argument("--salida", type=Path, required=True, help="carpeta nueva de salida")
    parser.add_argument(
        "--watchdog-config",
        type=Path,
        default=Path("config/watchdog.yaml"),
        help="watchdog.yaml de P5-12",
    )
    parser.add_argument("--run-id", help="run_id fijo (por defecto, uno por fecha)")
    parser.add_argument("--commit", help="commit para run.json (por defecto, git HEAD)")
    parser.add_argument(
        "--replay-dt-ms",
        type=float,
        default=100.0,
        help="ms entre cuadros dentro de una secuencia (default 100)",
    )
    parser.add_argument(
        "--detector",
        choices=("simulado", "real"),
        default="simulado",
        help="detector simulado (default) o real de P5-04",
    )
    parser.add_argument(
        "--detector-config",
        type=Path,
        default=Path("config/detector.yaml"),
        help="config/detector.yaml del detector real",
    )
    parser.add_argument("--modelo", type=Path, help="ruta alternativa del .onnx")
    args = parser.parse_args(argv)

    try:
        cfg_watchdog = cargar_config_watchdog(args.watchdog_config)
        hueco = hueco_entre_secuencias(cfg_watchdog, args.replay_dt_ms)
        manifiesto = args.manifiesto or args.datos / "manifiesto.csv"
        frames = normalizar_tiempos(
            leer_manifiesto(manifiesto, args.datos), args.replay_dt_ms, hueco
        )
        if fabrica_detector is not None:
            detector = fabrica_detector(args.datos)
        elif args.detector == "real":
            detector = DetectorONNX.desde_config(
                cargar_config_detector(args.detector_config, args.modelo)
            )
        else:
            detector = DetectorSimulado.desde_yaml(args.datos / "detecciones.yaml")
        run_id = args.run_id or f"run-{datetime.now(UTC).strftime('%Y%m%dT%H%M%S')}"
        commit = args.commit or _commit_actual()
        resumen = correr_recorrido(
            frames,
            detector,
            args.config,
            cfg_watchdog,
            args.salida,
            run_id=run_id,
            commit=commit,
            data_manifest_sha256=sha256_archivo(manifiesto),
            replay_dt_ms=args.replay_dt_ms,
        )
    except (
        InsumoFaltanteError,
        RecorridoInvalidoError,
        OSError,
        ValueError,
    ) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(
        f"Recorrido {resumen['run_id']}: {resumen['eventos']} cuadros, "
        f"{resumen['decisiones']} decisiones, {resumen['comandos']} comandos"
    )
    print(f"Salida: {args.salida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
