"""Persistencia y verificación de capturas. No abre conexiones de red."""

from __future__ import annotations

import csv
import hashlib
import re
import time
from collections import Counter
from pathlib import Path

SEQUENCES = tuple(f"S{i}" for i in range(1, 7))
FIELDS = (
    "sequence_id",
    "frame_id",
    "t_capture_ms",
    "path",
    "sha256",
    "sequence_start_unix_ns",
    "session_id",
    "scene_label",
    "outside_risk",
    "image_width",
    "image_height",
)
LABELS = ("pendiente", "obstaculo", "despejado")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_rows(root: Path) -> list[dict[str, str]]:
    with (root / "capturas.csv").open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, strict=True)
        if reader.fieldnames != list(FIELDS):
            raise ValueError(f"Cabecera CSV incorrecta. Se espera: {','.join(FIELDS)}")
        rows = list(reader)
    if any(None in row or any(value is None for value in row.values()) for row in rows):
        raise ValueError("CSV con filas incompletas o columnas adicionales")
    return rows


def image_path(root: Path, relative: str) -> Path:
    # Las rutas del manifiesto son portables y no pueden salir del dataset.
    if not relative or "\\" in relative:
        raise ValueError("Ruta vacía o no portable (usar /)")
    candidate = (root / relative).resolve()
    if not candidate.is_relative_to(root.resolve()) or Path(relative).is_absolute():
        raise ValueError(f"Ruta fuera del dataset: {relative}")
    return candidate


def jpeg_dimensions(data: bytes) -> tuple[int, int]:
    import cv2
    import numpy as np

    if not data.startswith(b"\xff\xd8") or not data.endswith(b"\xff\xd9"):
        raise ValueError("El archivo no es un JPEG completo")
    frame = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
    if frame is None:
        raise ValueError("JPEG no decodificable")
    return frame.shape[1], frame.shape[0]


def inspect(root: Path, minimums: bool = True) -> dict:
    """Valida integridad, archivos huérfanos y mínimos; no modifica evidencia."""
    errors: list[str] = []
    counts: Counter = Counter()
    labels: Counter = Counter()
    seen_hashes: dict[str, str] = {}
    seen_ids: set[str] = set()
    paths: set[str] = set()
    starts: dict[str, int] = {}
    last: dict[str, int] = {}
    sessions: set[str] = set()
    outside = 0
    duplicates = []
    try:
        rows = read_rows(root)
    except (OSError, ValueError, csv.Error, UnicodeError) as exc:
        return {
            "ok": False,
            "errors": [str(exc)],
            "counts": dict.fromkeys(SEQUENCES, 0),
            "total": 0,
            "duplicates": [],
            "labels": {},
            "outside_risk": 0,
            "sessions": [],
        }
    for line, row in enumerate(rows, start=2):
        try:
            seq, frame_id = row["sequence_id"], row["frame_id"]
            if seq not in SEQUENCES or not frame_id or frame_id in seen_ids:
                raise ValueError("sequence_id inválido o frame_id vacío/repetido")
            seen_ids.add(frame_id)
            stamp, origin = int(row["t_capture_ms"]), int(row["sequence_start_unix_ns"])
            if stamp < 0 or stamp <= last.get(seq, -1) or origin <= 0:
                raise ValueError("Tiempo negativo, no estrictamente creciente u origen inválido")
            if starts.setdefault(seq, origin) != origin:
                raise ValueError("Cambió el origen temporal de la secuencia")
            last[seq] = stamp
            if row["scene_label"] not in LABELS or row["outside_risk"] not in ("0", "1"):
                raise ValueError("Etiqueta de escena o outside_risk inválido")
            if not row["session_id"]:
                raise ValueError("session_id vacío")
            path = image_path(root, row["path"])
            if Path(row["path"]).parts[0] != seq or path.suffix.lower() != ".jpg":
                raise ValueError("JPEG fuera de su carpeta de secuencia")
            if row["path"] in paths:
                raise ValueError("Ruta repetida")
            paths.add(row["path"])
            data = path.read_bytes()
            actual = digest(data)
            if actual != row["sha256"]:
                raise ValueError("SHA-256 no coincide")
            if jpeg_dimensions(data) != (int(row["image_width"]), int(row["image_height"])):
                raise ValueError("Dimensiones no coinciden con el JPEG")
            if actual in seen_hashes:
                duplicates.append([seen_hashes[actual], row["path"]])
                raise ValueError(f"Duplicado exacto de {seen_hashes[actual]}")
            seen_hashes[actual] = row["path"]
            counts[seq] += 1
            labels[row["scene_label"]] += 1
            sessions.add(row["session_id"])
            outside += int(row["outside_risk"])
        except (OSError, ValueError, KeyError) as exc:
            errors.append(f"Fila {line}: {exc}")
    for path in root.rglob("*"):
        if (
            path.is_file()
            and path.suffix.lower() in (".jpg", ".jpeg")
            and path.relative_to(root).as_posix() not in paths
        ):
            errors.append(f"JPEG sin registro CSV: {path.relative_to(root).as_posix()}")
    if minimums:
        for seq in SEQUENCES:
            if counts[seq] < 10:
                errors.append(f"{seq}: {counts[seq]}/10 cuadros válidos distintos")
        if sum(counts.values()) < 60:
            errors.append(f"Total: {sum(counts.values())}/60 cuadros válidos distintos")
    return {
        "ok": not errors,
        "errors": errors,
        "counts": {seq: counts[seq] for seq in SEQUENCES},
        "total": sum(counts.values()),
        "duplicates": duplicates,
        "labels": dict(labels),
        "outside_risk": outside,
        "sessions": sorted(sessions),
    }


class CaptureStore:
    """Un solo escritor por dataset, sin sobrescribir imágenes previas."""

    def __init__(self, root: Path, session_id: str):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = self.root / ".captura.lock"
        self.session_id = session_id
        self.hashes: dict[str, str] = {}
        self.starts: dict[str, int] = {}
        self.last: dict[str, int] = {}
        self.counts: Counter = Counter()
        self.frame_ids: set[str] = set()
        self.frame_numbers: Counter = Counter()

    def __enter__(self):
        try:
            with self.lock.open("x", encoding="utf-8") as handle:
                handle.write(self.session_id + "\n")
        except FileExistsError as exc:
            raise ValueError(
                f"Dataset ocupado: {self.lock}. Ver guía para bloqueo residual."
            ) from exc
        try:
            csv_path = self.root / "capturas.csv"
            if csv_path.exists():
                report = inspect(self.root, minimums=False)
                if not report["ok"]:
                    raise ValueError("Dataset previo inválido: " + "; ".join(report["errors"]))
                for row in read_rows(self.root):
                    seq = row["sequence_id"]
                    self.hashes[row["sha256"]] = row["path"]
                    self.starts[seq] = int(row["sequence_start_unix_ns"])
                    self.last[seq] = int(row["t_capture_ms"])
                    self.counts[seq] += 1
                    self.frame_ids.add(row["frame_id"])
                    numbered = re.fullmatch(rf"{re.escape(seq)}_f([0-9]{{4,}})", row["frame_id"])
                    if numbered:
                        self.frame_numbers[seq] = max(self.frame_numbers[seq], int(numbered[1]))
            elif any(self.root.rglob("*.jpg")) or any(self.root.rglob("*.jpeg")):
                raise ValueError("Hay JPEG sin manifiesto; conservarlos y usar un dataset vacío")
            else:
                with csv_path.open("x", encoding="utf-8", newline="") as handle:
                    csv.DictWriter(handle, fieldnames=FIELDS).writeheader()
            return self
        except BaseException:
            self.lock.unlink()
            raise

    def __exit__(self, *args):
        self.lock.unlink(missing_ok=True)

    def save(self, data: bytes, seq: str, acquired_ns: int, label: str, outside: bool) -> str:
        if seq not in SEQUENCES or label not in LABELS:
            raise ValueError("Secuencia o etiqueta inválida")
        sha = digest(data)
        if sha in self.hashes:
            return f"Duplicado exacto omitido: {self.hashes[sha]}"
        width, height = jpeg_dimensions(data)
        origin = self.starts.get(seq, acquired_ns)
        stamp = (acquired_ns - origin) // 1_000_000
        if stamp < 0 or stamp <= self.last.get(seq, -1):
            return "Cuadro anterior/repetido o reloj atrasado: captura omitida"
        number = self.frame_numbers[seq] + 1
        frame_id = f"{seq}_f{number:04d}"
        while frame_id in self.frame_ids:
            number += 1
            frame_id = f"{seq}_f{number:04d}"
        relative = f"{seq}/{seq}_{stamp:010d}_{frame_id}.jpg"
        path = image_path(self.root, relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as handle:
            handle.write(data)
        row = dict(
            zip(
                FIELDS,
                (
                    seq,
                    frame_id,
                    stamp,
                    relative,
                    sha,
                    origin,
                    self.session_id,
                    label,
                    int(outside),
                    width,
                    height,
                ),
                strict=True,
            )
        )
        # Si falla la escritura, conservar el JPEG: el validador señalará el huérfano.
        with (self.root / "capturas.csv").open("a", encoding="utf-8", newline="") as handle:
            csv.DictWriter(handle, fieldnames=FIELDS).writerow(row)
            handle.flush()
        self.starts[seq], self.last[seq] = origin, stamp
        self.hashes[sha] = relative
        self.counts[seq] += 1
        self.frame_ids.add(frame_id)
        self.frame_numbers[seq] = number
        return f"Guardado {relative} | {seq}: {self.counts[seq]}"


def anchored_clock():
    """Reloj monotónico de recepción, anclado a UTC para reabrir secuencias."""
    wall, monotonic = time.time_ns(), time.monotonic_ns()
    return lambda: wall + time.monotonic_ns() - monotonic
