"""Aritmética temporal y candidatos derivados; sin cámara ni evidencia fabricada."""

from copy import deepcopy
from unittest.mock import patch

import pytest

import capturas_core as core
from normalizar_tiempos_capturas import build_candidate, normalize_rows

PRINCIPAL = 1_793_763_347_573_381_600
EXTRA = 1_793_767_996_073_360_200


def row(frame, stamp, origin, session):
    # Metadatos sintéticos para aritmética, no registros reales del dataset.
    return dict(
        zip(
            core.FIELDS,
            (
                "S2",
                frame,
                str(stamp),
                f"S2/{session}_{frame}.jpg",
                f"test-{session}-{frame}",
                str(origin),
                session,
                "obstaculo",
                "1" if session == "extra" else "0",
                "400",
                "296",
            ),
            strict=True,
        )
    )


def source_rows():
    return [
        row("S2_f0017", 2_831_460, PRINCIPAL, "principal"),
        row("S2_f0001", 0, EXTRA, "extra"),
        row("S2_f0006", 38_781, EXTRA, "extra"),
    ]


def test_exact_offsets_keep_pause_residue_and_sessions_without_mutating_input():
    rows = source_rows()
    before = deepcopy(rows)
    derived, audit = normalize_rows(rows, "S2", PRINCIPAL, "extra", 18)
    assert rows == before
    assert [r["t_capture_ms"] for r in derived] == ["2831460", "4648499", "4687280"]
    assert [r["frame_id"] for r in derived] == ["S2_f0017", "S2_f0018", "S2_f0019"]
    assert [r["session_id"] for r in derived] == ["principal", "extra", "extra"]
    assert audit[1]["temporal"]["remainder_ns"] == 978_600
    # La pausa no se compacta: 1817.0399786 s, no un intervalo de captura añadido.
    assert (
        audit[1]["temporal"]["absolute_estimate_ns"] - audit[0]["temporal"]["absolute_estimate_ns"]
    ) == 1_817_039_978_600
    for entry in audit:
        t = entry["temporal"]
        assert PRINCIPAL + t["relative_ms"] * 1_000_000 + t["remainder_ns"] == (
            int(entry["original"]["sequence_start_unix_ns"])
            + int(entry["original"]["t_capture_ms"]) * 1_000_000
        )
        for field in ("sha256", "session_id", "scene_label", "outside_risk"):
            assert entry["original"][field] == entry["derived"][field]


def test_preserves_other_sequence_and_is_deterministic():
    rows = source_rows()
    other = row("S3_f0001", 100, EXTRA, "other")
    other.update(sequence_id="S3", path="S3/original.jpg")
    rows.append(other)
    first = normalize_rows(rows, "S2", PRINCIPAL, "extra", 18)
    assert first == normalize_rows(rows, "S2", PRINCIPAL, "extra", 18)
    assert first[0][-1] == other


@pytest.mark.parametrize(
    ("origin", "session", "alias"),
    [
        (PRINCIPAL + 1, "extra", 18),
        (EXTRA, "extra", 18),
        (PRINCIPAL, "none", 18),
        (PRINCIPAL, "extra", 17),
    ],
)
def test_rejects_unrecorded_origin_negative_times_or_unsafe_alias(origin, session, alias):
    with pytest.raises(ValueError):
        normalize_rows(source_rows(), "S2", origin, session, alias)


def test_rejects_millisecond_tie_instead_of_inventing_time():
    rows = source_rows()
    rows.append(row("S2_f0002", 0, EXTRA, "extra"))
    with pytest.raises(ValueError, match="empatados"):
        normalize_rows(rows, "S2", PRINCIPAL, "extra", 18)


def test_rejects_hash_collision():
    rows = source_rows()
    rows[-1]["sha256"] = rows[0]["sha256"]
    with pytest.raises(ValueError, match="sha256"):
        normalize_rows(rows, "S2", PRINCIPAL, "extra", 18)


def test_clock_ignores_wall_adjustments_after_anchor_but_new_anchor_uses_new_wall():
    with (
        patch.object(core.time, "time_ns", side_effect=[1_000_000_000, 9_000_000_000]) as wall,
        patch.object(core.time, "monotonic_ns", side_effect=[100, 150, 200, 250, 300]),
    ):
        first = core.anchored_clock()
        assert first() == 1_000_000_050
        assert first() == 1_000_000_100
        assert wall.call_count == 1
        second = core.anchored_clock()
        assert second() == 9_000_000_050
    # No se puede demostrar sincronización entre procesos solo con el reloj anclado.


def write_synthetic_source(root):
    import csv

    root.mkdir()
    rows = source_rows()
    for item in rows:
        data = ("TEST ONLY not a JPEG: " + item["path"]).encode()
        path = root / item["path"]
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(data)
        item["sha256"] = core.digest(data)
    with (root / "capturas.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=core.FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def test_candidate_copies_bytes_and_backs_up_csv_without_overwriting(tmp_path):
    source, destination = tmp_path / "source", tmp_path / "candidate"
    before = write_synthetic_source(source)
    with patch.object(core, "jpeg_dimensions", return_value=(400, 296)):
        report = build_candidate(source, destination, "S2", PRINCIPAL, "extra", 18)
    assert report["integrity"]["ok"]
    assert (destination / "auditoria/capturas_original.csv").read_bytes() == before[
        source.joinpath("capturas.csv").relative_to(source)
    ]
    for entry in report["rows"]:
        assert (destination / entry["derived"]["path"]).read_bytes() == before[
            source.joinpath(entry["original"]["path"]).relative_to(source)
        ]
    assert {
        p.relative_to(source): p.read_bytes() for p in source.rglob("*") if p.is_file()
    } == before
    with pytest.raises(ValueError, match="destino nuevo"):
        build_candidate(source, destination, "S2", PRINCIPAL, "extra", 18)


def test_bad_source_hash_creates_no_candidate(tmp_path):
    source, destination = tmp_path / "source", tmp_path / "candidate"
    write_synthetic_source(source)
    (source / "S2/extra_S2_f0001.jpg").write_bytes(b"changed TEST bytes")
    with pytest.raises(ValueError, match="SHA fuente"):
        build_candidate(source, destination, "S2", PRINCIPAL, "extra", 18)
    assert not destination.exists()
