"""Inferencia del detector real sobre imagenes elegidas (P5-04, #56).

    PYTHONPATH=src python -m p5.detectar --imagenes <dir|archivos...>
        --config config/detector.yaml --salida <dir>

Escribe en `--salida` (carpeta nueva o vacia):
- `run.json`: cabecera de ejecucion del contrato v1 (commit, hashes, runtime, hardware).
- `detecciones.jsonl`: un evento de percepcion del contrato v1 por imagen, validado antes
  de escribirlo. Una imagen sin objetos sale con `status=ok` y `detections=[]`; una
  ilegible o un fallo del detector, con `status=error` y `error_msg`.

Las carpetas se recorren de forma recursiva (.jpg, .jpeg, .png, .bmp) en orden de ruta.
Aqui no hay secuencia: `sequence_id` es `cli`, `frame_id` es `cli_00000`, `cli_00001`, ...
y `t_capture_ms` es el orden de procesamiento. `image_path` es relativa a la carpeta dada
(o al directorio del archivo). El nombre del archivo nunca entra al detector.

Codigos de salida: 0 todas las imagenes procesadas (aunque alguna salga con error, que
queda registrada); 2 configuracion, pesos, entradas o carpeta de salida invalidos.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from p5.contrato import SCHEMA_VERSION, ContratoError, validar_evento, validar_run_header
from p5.detector_onnx import (
    DetectorError,
    DetectorONNX,
    ModeloInvalidoError,
    cargar_config,
    sha256_archivo,
)

EXTENSIONES = {".jpg", ".jpeg", ".png", ".bmp"}


def listar_imagenes(entradas: list[Path]) -> list[tuple[Path, str]]:
    """(ruta, image_path relativa con `/`) de cada imagen, sin repetir."""
    vistas: dict[Path, str] = {}
    for entrada in entradas:
        if entrada.is_dir():
            for ruta in sorted(entrada.rglob("*")):
                if ruta.is_file() and ruta.suffix.lower() in EXTENSIONES:
                    vistas.setdefault(ruta.resolve(), ruta.relative_to(entrada).as_posix())
        elif entrada.is_file():
            vistas.setdefault(entrada.resolve(), entrada.name)
        else:
            raise FileNotFoundError(f"no existe {entrada}")
    return [(ruta, rel) for ruta, rel in vistas.items()]


def _commit() -> str:
    try:
        salida = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True, timeout=10
        )
        return salida.stdout.strip() or "desconocido"
    except (OSError, subprocess.SubprocessError):
        return "desconocido"


def _evento(
    detector: DetectorONNX, run_id: str, indice: int, ruta: Path, rel: str
) -> dict[str, object]:
    evento: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "sequence_id": "cli",
        "frame_id": f"cli_{indice:05d}",
        "t_capture_ms": float(indice),
        "t_capture_origen_ms": None,
        "image_path": rel,
        "image_sha256": None,
        "image_width": None,
        "image_height": None,
        "model_sha256": detector.model_sha256,
        "config_sha256": detector.config.config_sha256,
        "status": "ok",
        "error_msg": None,
        "synthetic": False,
        "detections": [],
    }
    try:
        evento["image_sha256"] = sha256_archivo(ruta)
        ancho, alto, detecciones = detector.detectar_imagen(ruta)
    except (DetectorError, OSError) as exc:
        evento.update(status="error", error_msg=str(exc))
        return evento
    evento.update(
        image_width=ancho,
        image_height=alto,
        detections=[
            {
                "class_name": d.class_name,
                "class_id": d.class_id,
                "confidence": round(d.confidence, 4),
                "bbox": list(d.bbox),
            }
            for d in detecciones
        ],
    )
    return evento


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--imagenes", type=Path, nargs="+", required=True)
    parser.add_argument("--config", type=Path, required=True, help="config/detector.yaml")
    parser.add_argument("--salida", type=Path, required=True, help="carpeta nueva de salida")
    parser.add_argument("--modelo", type=Path, help="reemplaza la ruta del .onnx de la config")
    parser.add_argument("--run-id", help="run_id fijo (por defecto, uno por fecha)")
    args = parser.parse_args(argv)

    try:
        if args.salida.exists() and any(args.salida.iterdir()):
            raise FileExistsError(f"{args.salida} ya tiene archivos; usa una carpeta nueva")
        imagenes = listar_imagenes(args.imagenes)
        if not imagenes:
            raise FileNotFoundError("no se encontraron imagenes en --imagenes")
        config = cargar_config(args.config, args.modelo)
        detector = DetectorONNX.desde_config(config)
    except (ModeloInvalidoError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    import onnxruntime as ort

    inicio = datetime.now(UTC)
    run_id = args.run_id or f"det-{inicio.strftime('%Y%m%dT%H%M%S')}"
    manifiesto = "".join(f"{sha256_archivo(r)}  {rel}\n" for r, rel in imagenes)
    cabecera = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "commit": _commit(),
        "model_sha256": detector.model_sha256,
        "config_sha256": config.config_sha256,
        "data_manifest_sha256": hashlib.sha256(manifiesto.encode()).hexdigest(),
        "runtime": f"onnxruntime {ort.__version__} CPUExecutionProvider",
        "hardware": f"{platform.machine()} {platform.processor() or ''} {platform.platform()}",
        "virtual_mode": True,
        "t_start_utc": inicio.isoformat().replace("+00:00", "Z"),
    }
    validar_run_header(cabecera)

    args.salida.mkdir(parents=True, exist_ok=True)
    (args.salida / "run.json").write_text(json.dumps(cabecera, indent=2) + "\n", encoding="utf-8")
    conteo = {"ok": 0, "vacios": 0, "error": 0, "detecciones": 0}
    with (args.salida / "detecciones.jsonl").open("w", encoding="utf-8", newline="\n") as f:
        for indice, (ruta, rel) in enumerate(imagenes):
            evento = _evento(detector, run_id, indice, ruta, rel)
            try:
                validar_evento(evento)
            except ContratoError as exc:  # nunca se escribe un evento fuera de contrato
                evento.update(status="error", error_msg=f"salida fuera de contrato: {exc}")
                evento.update(detections=[], image_width=None, image_height=None)
                validar_evento(evento)
            f.write(json.dumps(evento, ensure_ascii=False) + "\n")
            n = len(evento["detections"])
            if evento["status"] == "error":
                conteo["error"] += 1
            else:
                conteo["ok"] += 1
                conteo["vacios"] += n == 0
                conteo["detecciones"] += n
            print(f"{evento['frame_id']}  {rel}  {evento['status']}  {n} detecciones")

    print(
        f"{len(imagenes)} imagenes: {conteo['ok']} ok ({conteo['vacios']} sin objetos), "
        f"{conteo['error']} con error, {conteo['detecciones']} detecciones -> {args.salida}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
