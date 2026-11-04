"""Crea una copia derivada auditable; no certifica relojes ni aprueba protocolos."""

from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
from pathlib import Path

from capturas_core import FIELDS, SEQUENCES, digest, image_path, inspect, read_rows

NS_PER_MS = 1_000_000


def normalize_rows(rows, sequence, origin, alias_session, first_alias):
    """Normaliza una secuencia con enteros; los alias son IDs derivados explícitos."""
    selected = [r for r in rows if r["sequence_id"] == sequence]
    if sequence not in SEQUENCES or not selected or origin <= 0:
        raise ValueError("Secuencia/origen inválido o sin registros")
    if origin not in {int(r["sequence_start_unix_ns"]) for r in selected}:
        raise ValueError("El origen común debe ser un origen registrado")
    if not alias_session or not any(r["session_id"] == alias_session for r in selected):
        raise ValueError("La sesión para alias debe existir en la secuencia")
    numbers = [
        int(match[1])
        for r in selected
        if (match := re.fullmatch(rf"{sequence}_f([0-9]+)", r["frame_id"]))
    ]
    if first_alias <= max(numbers, default=0):
        raise ValueError("Los alias deben comenzar después de los IDs originales")
    derived, audit = [], []
    for original in rows:
        row = original.copy()
        temporal = None
        if row["sequence_id"] == sequence:
            old_origin = int(row["sequence_start_unix_ns"])
            old_ms = int(row["t_capture_ms"])
            if old_origin <= 0 or old_ms < 0:
                raise ValueError("Tiempo original inválido")
            absolute = old_origin + old_ms * NS_PER_MS
            stamp, remainder = divmod(absolute - origin, NS_PER_MS)
            if stamp < 0:
                raise ValueError("El origen común es posterior a un cuadro")
            row.update(t_capture_ms=str(stamp), sequence_start_unix_ns=str(origin))
            temporal = {
                "absolute_estimate_ns": absolute,
                "relative_ms": stamp,
                "remainder_ns": remainder,
            }
        derived.append(row)
        audit.append({"original": original.copy(), "derived": row, "temporal": temporal})
    targets = sorted(
        (a for a in audit if a["temporal"] and a["original"]["session_id"] == alias_session),
        key=lambda a: a["temporal"]["absolute_estimate_ns"],
    )
    for number, entry in enumerate(targets, first_alias):
        row = entry["derived"]
        row["frame_id"] = f"{sequence}_f{number:04d}"
        row["path"] = f"{sequence}/{sequence}_{int(row['t_capture_ms']):010d}_{row['frame_id']}.jpg"
    for field in ("frame_id", "path", "sha256"):
        values = [r[field] for r in derived]
        if len(values) != len(set(values)):
            raise ValueError(f"Colisión de {field}")
    derived.sort(key=lambda r: (r["sequence_id"], int(r["t_capture_ms"])))
    last = {}
    for row in derived:
        seq, stamp = row["sequence_id"], int(row["t_capture_ms"])
        if stamp <= last.get(seq, -1):
            raise ValueError("Tiempos empatados/no crecientes; no se inventan incrementos")
        last[seq] = stamp
    return derived, audit


def build_candidate(source, destination, sequence, origin, alias_session, first_alias):
    source, destination = source.resolve(), destination.resolve()
    if (
        destination.exists()
        or destination.is_relative_to(source)
        or source.is_relative_to(destination)
    ):
        raise ValueError("Usar un destino nuevo separado del origen")
    rows = read_rows(source)
    derived, audit = normalize_rows(rows, sequence, origin, alias_session, first_alias)
    source_csv = (source / "capturas.csv").read_bytes()
    files = []
    for entry in audit:
        old, new = entry["original"], entry["derived"]
        path = image_path(source, old["path"])
        image_path(destination, new["path"])
        if digest(path.read_bytes()) != old["sha256"]:
            raise ValueError(f"SHA fuente incorrecto: {old['path']}")
        files.append((path, new))
    source_jpegs = {
        p.relative_to(source).as_posix()
        for p in source.rglob("*")
        if p.is_file() and p.suffix.lower() in (".jpg", ".jpeg")
    }
    if source_jpegs != {r["path"] for r in rows}:
        raise ValueError("Origen con JPEG huérfanos o registros sin JPEG")
    destination.mkdir(parents=True, exist_ok=False)
    for path, row in files:
        target = image_path(destination, row["path"])
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as handle:
            handle.write(path.read_bytes())
    with (destination / "capturas.csv").open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(derived)
    audit_dir = destination / "auditoria"
    audit_dir.mkdir()
    shutil.copyfile(source / "capturas.csv", audit_dir / "capturas_original.csv")
    report = inspect(destination, minimums=False)
    evidence = {
        "approved": False,
        "source_csv_sha256": digest(source_csv),
        "derived_csv_sha256": digest((destination / "capturas.csv").read_bytes()),
        "sequence": sequence,
        "common_origin_unix_ns": origin,
        "formula": "A=O_original+t_original*1000000; (t_nuevo,residuo)=divmod(A-O_comun,1000000)",
        "precision": "Recepción registrada truncada a ms; no hora exacta de exposición",
        "clock_reliability": "Requiere auditoría externa; este programa no verifica relojes",
        "rows": audit,
        "integrity": report,
    }
    (audit_dir / "normalizacion.json").write_text(
        json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    if not report["ok"]:
        raise ValueError("Candidato inválido; conservar informe y no integrar")
    return evidence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--datos", type=Path, required=True)
    parser.add_argument("--salida", type=Path, required=True)
    parser.add_argument("--secuencia", choices=SEQUENCES, required=True)
    parser.add_argument("--origen-unix-ns", type=int, required=True)
    parser.add_argument("--alias-sesion", required=True)
    parser.add_argument("--primer-alias", type=int, required=True)
    args = parser.parse_args()
    try:
        report = build_candidate(
            args.datos,
            args.salida,
            args.secuencia,
            args.origen_unix_ns,
            args.alias_sesion,
            args.primer_alias,
        )
    except (OSError, ValueError) as exc:
        parser.exit(1, f"ERROR: {exc}\n")
    print(json.dumps(report["integrity"], indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
