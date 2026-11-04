"""Pruebas sin cámara: bytes simulados y decodificador sustituido en temporales."""

from __future__ import annotations

import argparse
import contextlib
import csv
import io
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("cv2")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import capturar_esp32 as capture
import capturas_core as core
import validar_capturas as validate


class DatasetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        # No se fabrican fotografías: las pruebas usan bytes que no son imágenes.
        self.decoder = patch.object(core, "jpeg_dimensions", return_value=(640, 480))
        self.decoder.start()
        self.addCleanup(self.decoder.stop)

    def save_one(self, root=None, data=b"TEST ONLY - not a camera image", session="eval"):
        root = root or self.root
        with core.CaptureStore(root, session) as store:
            return store.save(data, "S1", 1_000_000_000, "despejado", False)

    def rewrite(self, rows):
        with (self.root / "capturas.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=core.FIELDS)
            writer.writeheader()
            writer.writerows(rows)

    def test_save_original_bytes_hash_numbered_id_and_relative_time(self):
        data = b"TEST ONLY - bytes preserved"
        self.save_one(data=data)
        row = core.read_rows(self.root)[0]
        self.assertEqual((self.root / row["path"]).read_bytes(), data)
        self.assertEqual(row["sha256"], core.digest(data))
        self.assertEqual(row["t_capture_ms"], "0")
        self.assertEqual(row["frame_id"], "S1_f0001")
        self.assertTrue(core.inspect(self.root, minimums=False)["ok"])
        self.assertFalse((self.root / ".captura.lock").exists())

    def test_duplicate_rejected_even_after_restart(self):
        self.save_one()
        with core.CaptureStore(self.root, "eval") as store:
            message = store.save(
                b"TEST ONLY - not a camera image", "S2", 2_000_000_000, "obstaculo", True
            )
        self.assertIn("Duplicado", message)
        self.assertEqual(len(core.read_rows(self.root)), 1)

    def test_resume_preserves_origin_and_includes_pause(self):
        self.save_one()
        with core.CaptureStore(self.root, "eval") as store:
            store.save(b"TEST ONLY - second frame", "S1", 3_000_000_000, "obstaculo", False)
        rows = core.read_rows(self.root)
        self.assertEqual(rows[1]["t_capture_ms"], "2000")
        self.assertEqual(rows[0]["sequence_start_unix_ns"], rows[1]["sequence_start_unix_ns"])

    def test_legacy_uuid_id_is_read_without_rewriting_existing_records(self):
        self.save_one()
        rows = core.read_rows(self.root)
        rows[0]["frame_id"] = "a" * 32
        self.rewrite(rows)
        before = (self.root / "capturas.csv").read_bytes()
        with core.CaptureStore(self.root, "another-session"):
            self.assertEqual((self.root / "capturas.csv").read_bytes(), before)
        self.assertTrue(core.inspect(self.root, minimums=False)["ok"])

    def test_stale_timestamp_not_saved(self):
        self.save_one()
        with core.CaptureStore(self.root, "eval") as store:
            message = store.save(b"TEST ONLY - old frame", "S1", 999_000_000, "obstaculo", False)
        self.assertIn("omitida", message)
        self.assertEqual(len(core.read_rows(self.root)), 1)

    def test_concurrent_writer_rejected(self):
        with (
            core.CaptureStore(self.root, "a"),
            self.assertRaisesRegex(ValueError, "ocupado"),
            core.CaptureStore(self.root, "b"),
        ):
            self.fail("El segundo escritor entró")

    def test_corrupt_existing_dataset_not_modified_on_resume(self):
        self.save_one()
        row = core.read_rows(self.root)[0]
        image = self.root / row["path"]
        image.write_bytes(b"TEST ONLY - modified")
        before = (self.root / "capturas.csv").read_bytes()
        with (
            self.assertRaisesRegex(ValueError, "SHA-256"),
            core.CaptureStore(self.root, "eval"),
        ):
            self.fail("Se aceptó corrupción")
        self.assertEqual((self.root / "capturas.csv").read_bytes(), before)
        self.assertFalse((self.root / ".captura.lock").exists())

    def test_exact_minimums_pass_and_one_missing_fails(self):
        with core.CaptureStore(self.root, "eval") as store:
            for seq in core.SEQUENCES:
                for index in range(10):
                    data = f"TEST ONLY {seq} {index}".encode()
                    store.save(data, seq, 1_000_000_000 + index * 1_000_000, "despejado", False)
        report = core.inspect(self.root)
        self.assertTrue(report["ok"], report)
        self.assertEqual(report["total"], 60)
        self.assertEqual(report["counts"], dict.fromkeys(core.SEQUENCES, 10))
        rows = core.read_rows(self.root)
        (self.root / rows[-1]["path"]).unlink()
        self.rewrite(rows[:-1])
        report = core.inspect(self.root)
        self.assertFalse(report["ok"])
        self.assertIn("S6: 9/10", "; ".join(report["errors"]))
        self.assertIn("Total: 59/60", "; ".join(report["errors"]))

    def test_missing_sequence_not_replaced_by_extra_frames(self):
        with core.CaptureStore(self.root, "eval") as store:
            for index in range(60):
                store.save(
                    f"TEST ONLY {index}".encode(),
                    "S1",
                    1_000_000_000 + index * 1_000_000,
                    "despejado",
                    False,
                )
        report = core.inspect(self.root)
        self.assertEqual(report["total"], 60)
        self.assertFalse(report["ok"])
        self.assertIn("S2: 0/10", "; ".join(report["errors"]))

    def test_duplicate_in_manifest_not_counted(self):
        self.save_one()
        rows = core.read_rows(self.root)
        first = rows[0]
        second = dict(first, frame_id="another-id", t_capture_ms="1", path="S1/other.jpg")
        (self.root / second["path"]).write_bytes((self.root / first["path"]).read_bytes())
        self.rewrite([first, second])
        report = core.inspect(self.root, minimums=False)
        self.assertFalse(report["ok"])
        self.assertEqual(report["total"], 1)
        self.assertEqual(len(report["duplicates"]), 1)

    def test_invalid_csv_headers_extra_and_missing_cells(self):
        self.save_one()
        original = (self.root / "capturas.csv").read_text(encoding="utf-8")
        cases = [
            "sequence_id,frame_id\nS1,a\n",
            original + "S1,a\n",
            original + ",".join(["a"] * (len(core.FIELDS) + 1)) + "\n",
        ]
        for content in cases:
            with self.subTest(content=content[-50:]):
                (self.root / "capturas.csv").write_text(content, encoding="utf-8")
                self.assertFalse(core.inspect(self.root, minimums=False)["ok"])

    def test_corrupt_missing_invalid_time_and_path_traversal(self):
        self.save_one()
        original = core.read_rows(self.root)[0]
        mutations = {
            "sha256": "0" * 64,
            "t_capture_ms": "-1",
            "sequence_id": "S7",
            "path": "../outside.jpg",
            "scene_label": "fake",
            "outside_risk": "2",
            "image_width": "1",
            "session_id": "",
            "sequence_start_unix_ns": "0",
        }
        for key, value in mutations.items():
            with self.subTest(field=key):
                self.rewrite([dict(original, **{key: value})])
                self.assertFalse(core.inspect(self.root, minimums=False)["ok"])
        self.rewrite([original])
        (self.root / original["path"]).unlink()
        self.assertIn("Fila 2", "; ".join(core.inspect(self.root, minimums=False)["errors"]))

    def test_orphan_jpeg_is_reported(self):
        self.save_one()
        (self.root / "orphan.jpg").write_bytes(b"TEST ONLY")
        self.assertIn("sin registro", "; ".join(core.inspect(self.root, minimums=False)["errors"]))

    def test_missing_csv_returns_failure_without_generating_evidence(self):
        self.assertFalse(core.inspect(self.root)["ok"])
        self.assertEqual(list(self.root.iterdir()), [])

    def test_issue57_detects_shared_sessions_hashes_and_missing_labels(self):
        evaluation, adjustment = self.root / "eval", self.root / "ajuste"
        self.save_one(root=evaluation, session="shared")
        self.save_one(root=adjustment, session="shared")
        argv = ["validar", "--datos", str(evaluation), "--ajuste", str(adjustment), "--issue57"]
        with patch.object(sys, "argv", argv), contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(validate.main(), 1)
        errors = json.loads(output.getvalue())["errors"]
        self.assertTrue(any("comparten session_id" in error for error in errors))
        self.assertTrue(any("JPEG idénticos" in error for error in errors))
        self.assertTrue(any(">=20" in error for error in errors))

    def test_issue57_passes_complete_separate_datasets(self):
        evaluation, adjustment = self.root / "eval", self.root / "ajuste"
        with core.CaptureStore(evaluation, "evaluation-session") as store:
            for seq in core.SEQUENCES:
                for index in range(10):
                    label = "despejado" if seq in ("S1", "S6") else "obstaculo"
                    store.save(
                        f"TEST ONLY {seq}-{index}".encode(),
                        seq,
                        1_000_000_000 + index * 1_000_000,
                        label,
                        seq == "S1",
                    )
        self.save_one(root=adjustment, data=b"TEST ONLY adjustment", session="other-session")
        argv = ["validar", "--datos", str(evaluation), "--ajuste", str(adjustment), "--issue57"]
        with patch.object(sys, "argv", argv), contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(validate.main(), 0)
        self.assertTrue(json.loads(output.getvalue())["ok"])

    def test_preview_manual_capture_uses_single_stream_manager(self):
        # GUI, red y decoder simulados; no se abren cámara ni ventanas.
        gui, arrays, reader, opener, response = (MagicMock() for _ in range(5))
        gui.error = type("FakeCvError", (Exception,), {})
        gui.getWindowProperty.return_value = 1
        gui.imdecode.return_value.shape = (480, 640, 3)
        gui.imdecode.return_value.copy.return_value.shape = (480, 640, 3)
        gui.getTextSize.return_value = ((60, 12), 3)
        gui.waitKey.side_effect = [ord("b"), ord("z"), 32, ord("q")]
        reader.error = None
        reader.state = "EN VIVO"
        reader.drain_messages.return_value = []
        reader.is_current.return_value = True
        reader.snapshot.return_value = (b"TEST ONLY preview", 1_000_000_000, 100.0)
        response.headers = {"Content-Type": "multipart/x-mixed-replace; boundary=frame"}
        opener.open.return_value = response
        args = argparse.Namespace(
            secuencia="S2",
            intervalo=0,
            sesion="test",
            destino=self.root,
            url=capture.DEFAULT_URL,
            rotacion=0,
            espera_inicial=10,
            espera_cuadros=10,
            reintento=2,
            edad_maxima=2,
        )
        with (
            patch.dict(sys.modules, {"cv2": gui, "numpy": arrays}),
            patch.object(capture, "ReconnectingStream", return_value=reader) as factory,
            patch.object(capture.time, "monotonic", return_value=100.0),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            capture.run(args)
        factory.assert_called_once_with(capture.DEFAULT_URL, 10, 10, 2)
        row = core.read_rows(self.root)[0]
        self.assertEqual(
            (row["sequence_id"], row["scene_label"], row["outside_risk"]), ("S2", "obstaculo", "1")
        )
        self.assertEqual((self.root / row["path"]).read_bytes(), b"TEST ONLY preview")
        reader.stop.set.assert_called_once()
        reader.close.assert_called_once()
        gui.destroyAllWindows.assert_called_once()

    def run_capture_events(self, events, interval=2):
        """Ejecuta el bucle real con teclado, reloj, stream y GUI controlados."""
        gui, arrays, reader, opener, response = (MagicMock() for _ in range(5))
        gui.error = type("FakeCvError", (Exception,), {})
        gui.getWindowProperty.return_value = 1
        gui.imdecode.return_value.shape = (480, 640, 3)
        gui.imdecode.return_value.copy.return_value.shape = (480, 640, 3)
        gui.getTextSize.return_value = ((60, 12), 3)
        reader.error = None
        reader.state = "EN VIVO"
        reader.drain_messages.return_value = []
        reader.is_current.return_value = True
        response.headers = {"Content-Type": "multipart/x-mixed-replace; boundary=frame"}
        opener.open.return_value = response
        clock = [100.0]
        pending = iter(events)
        active = {}

        def snapshot():
            active.clear()
            active.update(next(pending))
            clock[0] = active["at"]
            reader.state = active.get("state", "EN VIVO")
            if active.get("missing"):
                return None
            received = active.get("received", clock[0])
            data = f"TEST ONLY event at {active['at']}".encode()
            return data, 1_000_000_000 + round(received * 1_000_000_000), received

        def keypress(delay):
            clock[0] = active.get("key_at", clock[0])
            return active.get("key", -1)

        reader.snapshot.side_effect = snapshot
        decoded_frame = gui.imdecode.return_value
        gui.imdecode.side_effect = lambda *args: None if active.get("invalid") else decoded_frame
        gui.waitKey.side_effect = keypress
        args = argparse.Namespace(
            secuencia="S1",
            intervalo=interval,
            sesion="test",
            destino=self.root,
            url=capture.DEFAULT_URL,
            rotacion=0,
            espera_inicial=10,
            espera_cuadros=10,
            reintento=2,
            edad_maxima=2,
        )
        with (
            patch.dict(sys.modules, {"cv2": gui, "numpy": arrays}),
            patch.object(capture, "ReconnectingStream", return_value=reader) as factory,
            patch.object(capture.time, "monotonic", side_effect=lambda: clock[0]),
            patch.object(capture, "draw_preview", wraps=capture.draw_preview) as renderer,
            contextlib.redirect_stdout(io.StringIO()) as output,
        ):
            capture.run(args)
        factory.assert_called_once_with(capture.DEFAULT_URL, 10, 10, 2)
        reader.stop.set.assert_called_once()
        reader.close.assert_called_once()
        gui.destroyAllWindows.assert_called_once()
        self.assertFalse((self.root / ".captura.lock").exists())
        self.preview_calls = renderer.call_args_list
        self.preview_lines = gui.line.call_args_list
        return core.read_rows(self.root), output.getvalue()

    def test_guides_toggle_preserves_original_bytes_in_manual_and_auto_captures(self):
        rows, _ = self.run_capture_events(
            [
                {"at": 100},
                {"at": 100.1, "key": ord("g")},
                {"at": 100.5, "key": 32},
                {"at": 102.5},
                {"at": 103, "key": ord("2")},
                {"at": 103.1, "key": ord("G")},
                {"at": 103.5, "key": 32},
                {"at": 105.5},
                {"at": 107.5, "key": ord("q")},
            ]
        )
        self.assertEqual([row["sequence_id"] for row in rows], ["S1", "S1", "S2", "S2"])
        self.assertEqual([int(row["t_capture_ms"]) for row in rows], [0, 2000, 0, 2000])
        self.assertEqual(len({row["frame_id"] for row in rows}), 4)
        for row, at in zip(rows, (100.5, 102.5, 103.5, 105.5), strict=True):
            original = f"TEST ONLY event at {at}".encode()
            self.assertEqual((self.root / row["path"]).read_bytes(), original)
            self.assertEqual(row["sha256"], core.digest(original))
            self.assertEqual(list(row), list(core.FIELDS))
        self.assertTrue(any(call.args[-1] is False for call in self.preview_calls))
        self.assertTrue(any(call.args[-1] is True for call in self.preview_calls))
        self.assertTrue(self.preview_lines)

    def test_slow_start_keeps_window_open_and_captures_after_first_frame(self):
        rows, output = self.run_capture_events(
            [
                {"at": 100, "missing": True, "state": "CONECTANDO"},
                {"at": 108, "missing": True, "state": "ESPERANDO VIDEO", "key": 32},
                {"at": 109, "key": ord("d")},
                {"at": 109.1, "key": 32},
                {"at": 111.1},
                {"at": 113.1, "key": ord("q")},
            ]
        )
        self.assertEqual(len(rows), 2)
        self.assertEqual([r["scene_label"] for r in rows], ["despejado", "despejado"])
        self.assertIn("ESPERANDO VIDEO", output)

    def test_stale_frames_and_reconnect_do_not_save_old_images(self):
        rows, output = self.run_capture_events(
            [
                {"at": 100},
                {"at": 100.5, "key": 32},
                {"at": 102.6, "received": 100.5, "key": 32},
                {"at": 103, "missing": True, "state": "RECONECTANDO", "key": 32},
                {"at": 104, "missing": True, "state": "RECONECTANDO", "key": ord("2")},
                {"at": 105},
                {"at": 106.9},
                {"at": 107},
                {"at": 109, "key": ord("q")},
            ]
        )
        self.assertEqual([r["sequence_id"] for r in rows], ["S1", "S2"])
        self.assertEqual([r["t_capture_ms"] for r in rows], ["0", "0"])
        self.assertEqual((self.root / rows[0]["path"]).read_bytes(), b"TEST ONLY event at 100.5")
        self.assertEqual((self.root / rows[1]["path"]).read_bytes(), b"TEST ONLY event at 107")
        self.assertIn("RECONECTANDO", output)

    def test_q_during_initial_wait_or_retry_keeps_csv_empty(self):
        rows, _ = self.run_capture_events(
            [
                {"at": 100, "missing": True, "state": "CONECTANDO"},
                {"at": 108, "missing": True, "state": "ESPERANDO VIDEO"},
                {"at": 110, "missing": True, "state": "RECONECTANDO", "key": ord("q")},
            ]
        )
        self.assertEqual(rows, [])

    def test_q_still_works_when_stream_delivers_invalid_jpeg(self):
        rows, output = self.run_capture_events(
            [
                {"at": 100, "invalid": True, "key": 32},
                {"at": 100.1, "received": 100, "invalid": True},
                {"at": 100.2, "received": 100, "invalid": True, "key": ord("q")},
            ]
        )
        self.assertEqual(rows, [])
        self.assertIn("JPEG no decodificable", output)

    def test_restart_appends_without_changing_preexisting_capture(self):
        self.save_one()
        original = core.read_rows(self.root)[0]
        image = (self.root / original["path"]).read_bytes()
        rows, _ = self.run_capture_events(
            [
                {"at": 100},
                {"at": 100.5, "key": 32},
                {"at": 102.5, "key": ord("q")},
            ]
        )
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0], original)
        self.assertEqual((self.root / original["path"]).read_bytes(), image)
        self.assertNotEqual(rows[0]["frame_id"], rows[1]["frame_id"])
        self.assertTrue(core.inspect(self.root, minimums=False)["ok"])

    def test_guides_and_status_refresh_without_new_camera_frame(self):
        rows, _ = self.run_capture_events(
            [
                {"at": 100},
                {"at": 100.1, "received": 100, "key": ord("g")},
                {"at": 100.2, "received": 100, "key": ord("a")},
                {"at": 100.3, "received": 100},
                {"at": 100.4, "received": 100, "key": ord("q")},
            ]
        )
        self.assertEqual(rows, [])
        self.assertEqual(
            [(call.args[-2], call.args[-1]) for call in self.preview_calls],
            [("ACTIVA", True), ("ACTIVA", False), ("PAUSADA", False)],
        )
        self.assertEqual(len(self.preview_lines), 3)

    def test_auto_continues_across_all_sequences_and_restarts_deadline(self):
        events = []
        for index in range(6):
            start = 100 + index * 6
            # Cambiar exactamente cuando vence el plazo anterior: no guardar en la anterior.
            events.extend(
                [
                    {"at": start, "key": ord(str(index + 1)) if index else -1},
                    {"at": start + 1.999},
                    {"at": start + 2},
                    {"at": start + 4},
                ]
            )
        events.append({"at": 136, "key": ord("Q")})
        rows, output = self.run_capture_events(events)
        self.assertEqual(
            [row["sequence_id"] for row in rows], [seq for seq in core.SEQUENCES for _ in range(2)]
        )
        self.assertEqual([int(row["t_capture_ms"]) for row in rows], [0, 2000] * 6)
        self.assertEqual(len({row["frame_id"] for row in rows}), 12)
        self.assertEqual(len({row["path"] for row in rows}), 12)
        for index, seq in enumerate(core.SEQUENCES):
            for offset, row in zip((2, 4), rows[index * 2 : index * 2 + 2], strict=True):
                self.assertTrue(row["path"].startswith(f"{seq}/{seq}_"))
                expected = f"TEST ONLY event at {100 + index * 6 + offset}".encode()
                self.assertEqual((self.root / row["path"]).read_bytes(), expected)
                self.assertEqual(row["sha256"], core.digest(expected))
            if index:
                self.assertIn(f"Secuencia activa: {seq}; captura automática continúa", output)
        self.assertTrue(core.inspect(self.root, minimums=False)["ok"])

    def test_space_captures_manually_while_auto_remains_active_after_switch(self):
        rows, _ = self.run_capture_events(
            [
                {"at": 100},
                {"at": 100.5, "key": 32},
                {"at": 102.49},
                {"at": 102.5},
                {"at": 103, "key": ord("2")},
                {"at": 103.5, "key": 32},
                {"at": 105.5},
                {"at": 107.5, "key": ord("q")},
            ]
        )
        self.assertEqual([row["sequence_id"] for row in rows], ["S1", "S1", "S2", "S2"])
        self.assertEqual([int(row["t_capture_ms"]) for row in rows], [0, 2000, 0, 2000])

    def test_switch_does_not_enable_auto_in_manual_mode(self):
        rows, output = self.run_capture_events(
            [
                {"at": 100},
                {"at": 102, "key": ord("2")},
                {"at": 104},
                {"at": 105, "key": 32},
                {"at": 106, "key": ord("3")},
                {"at": 108},
                {"at": 109, "key": 32},
                {"at": 110, "key": ord("q")},
            ],
            interval=0,
        )
        self.assertEqual([row["sequence_id"] for row in rows], ["S2", "S3"])
        self.assertIn("captura automática inactiva", output)

    def test_explicit_auto_pause_is_preserved_on_sequence_change(self):
        rows, output = self.run_capture_events(
            [
                {"at": 100, "key": ord("a")},
                {"at": 102, "key": ord("2")},
                {"at": 104},
                {"at": 105, "key": 32},
                {"at": 106, "key": ord("q")},
            ]
        )
        self.assertEqual([row["sequence_id"] for row in rows], ["S2"])
        self.assertIn("Secuencia activa: S2; captura automática inactiva", output)

    def test_new_sequence_rejects_frame_received_before_switch(self):
        rows, _ = self.run_capture_events(
            [
                {"at": 100},
                {"at": 101, "key": ord("2")},
                {"at": 101.5, "received": 100.9, "key": 32},
                {"at": 102, "received": 101.7, "key": 32},
                {"at": 103, "key": ord("q")},
            ]
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["sequence_id"], "S2")
        self.assertEqual((self.root / rows[0]["path"]).read_bytes(), b"TEST ONLY event at 102")

    def test_interval_starts_when_sequence_key_is_processed(self):
        rows, _ = self.run_capture_events(
            [
                {"at": 100},
                {"at": 101, "key_at": 101.5, "key": ord("2")},
                {"at": 103.1},
                {"at": 103.49},
                {"at": 103.5},
                {"at": 105.5, "key": ord("q")},
            ]
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["sequence_id"], "S2")
        self.assertEqual((self.root / rows[0]["path"]).read_bytes(), b"TEST ONLY event at 103.5")

    def test_invalid_jpeg_rejected_without_writing_image(self):
        with (
            core.CaptureStore(self.root, "test") as store,
            patch.object(core, "jpeg_dimensions", side_effect=ValueError("JPEG inválido")),
            self.assertRaisesRegex(ValueError, "JPEG inválido"),
        ):
            store.save(b"TEST ONLY invalid", "S1", 1_000_000_000, "pendiente", False)
        self.assertEqual(core.read_rows(self.root), [])
        self.assertEqual(list(self.root.rglob("*.jpg")), [])


class PreviewTests(unittest.TestCase):
    def test_guides_draw_on_separate_array_without_changing_original_pixels(self):
        import numpy as np

        source = np.full((480, 640, 3), 100, dtype=np.uint8)
        original = source.tobytes()
        preview = capture.draw_preview(source, "S3", 10, "obstaculo", False, "ACTIVA")
        self.assertEqual(source.tobytes(), original)
        self.assertFalse(np.shares_memory(source, preview))
        self.assertNotEqual(preview.tobytes(), original)
        hidden = capture.draw_preview(source, "S3", 10, "obstaculo", False, "ACTIVA", False)
        # Ocultar elimina guías y etiquetas sin dejar trazos del render anterior.
        self.assertTrue(np.array_equal(hidden[45:], source[45:]))
        self.assertFalse(np.array_equal(preview[45:], source[45:]))
        self.assertEqual(source.tobytes(), original)

    def test_guides_match_frame_dimensions_and_zone_labels(self):
        import cv2
        import numpy as np

        for width, height in ((320, 240), (640, 480), (641, 479), (1280, 720)):
            with (
                self.subTest(width=width, height=height),
                patch.object(cv2, "line", wraps=cv2.line) as line,
                patch.object(cv2, "putText", wraps=cv2.putText) as text,
            ):
                frame = np.zeros((height, width, 3), dtype=np.uint8)
                capture.draw_preview(frame, "S4", 0, "pendiente", False, "PAUSADA")
                self.assertEqual(
                    [(call.args[1], call.args[2]) for call in line.call_args_list],
                    [
                        ((width // 3, 0), (width // 3, height - 1)),
                        ((2 * width // 3, 0), (2 * width // 3, height - 1)),
                        ((0, height // 2), (width - 1, height // 2)),
                    ],
                )
                texts = [call.args[1] for call in text.call_args_list]
                for label in ("IZQUIERDA", "CENTRO", "DERECHA"):
                    self.assertIn(label, texts)
                self.assertIn("SECUENCIA: S4 | AUTO: PAUSADA", texts)

    def test_hidden_guides_keep_sequence_and_auto_indicator(self):
        import cv2
        import numpy as np

        with patch.object(cv2, "line") as line, patch.object(cv2, "putText") as text:
            capture.draw_preview(
                np.zeros((480, 640, 3), dtype=np.uint8),
                "S6",
                0,
                "pendiente",
                False,
                "DETENIDA",
                guides=False,
            )
        line.assert_not_called()
        texts = [call.args[1] for call in text.call_args_list]
        self.assertIn("SECUENCIA: S6 | AUTO: DETENIDA", texts)
        self.assertNotIn("IZQUIERDA", texts)
        self.assertNotIn("CENTRO", texts)
        self.assertNotIn("DERECHA", texts)

    def test_auto_indicator_distinguishes_initial_manual_and_explicit_pause(self):
        self.assertEqual(capture.auto_status(False, False), "DETENIDA")
        self.assertEqual(capture.auto_status(True, False), "ACTIVA")
        self.assertEqual(capture.auto_status(True, True), "ACTIVA")
        self.assertEqual(capture.auto_status(False, True), "PAUSADA")


class RotationTests(unittest.TestCase):
    def test_rotation_angles_and_directions_preserve_source(self):
        import numpy as np

        source = np.array([[1, 2, 3], [4, 5, 6]], dtype=np.uint8)
        expected = {
            0: [[1, 2, 3], [4, 5, 6]],
            90: [[4, 1], [5, 2], [6, 3]],
            180: [[6, 5, 4], [3, 2, 1]],
            270: [[3, 6], [2, 5], [1, 4]],
        }
        for angle, pixels in expected.items():
            with self.subTest(angle=angle):
                result = capture.rotate_frame(source, angle)
                np.testing.assert_array_equal(result, pixels)
                np.testing.assert_array_equal(source, [[1, 2, 3], [4, 5, 6]])
        with self.assertRaisesRegex(ValueError, "Rotación inválida"):
            capture.rotate_frame(source, 45)

    def test_rotation_cli_choices_and_default(self):
        self.assertEqual(capture.parser().parse_args([]).rotacion, 0)
        for angle in (0, 90, 180, 270):
            self.assertEqual(
                capture.parser().parse_args(["--rotacion", str(angle)]).rotacion, angle
            )
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
            capture.parser().parse_args(["--rotacion", "45"])
        self.assertEqual(error.exception.code, 2)

    def test_jpeg_encoding_failure_is_reported(self):
        import cv2

        with (
            patch.object(cv2, "imencode", return_value=(False, None)),
            self.assertRaisesRegex(ValueError, "codificar"),
        ):
            capture.jpeg_for_capture(b"TEST ONLY", object(), 90)

    def test_saved_jpeg_orientation_dimensions_hash_and_no_guides_for_all_angles(self):
        import cv2
        import numpy as np

        # Patrón de color solo para pruebas, en memoria y directorios temporales.
        # Dibujo, rotación, codificación y persistencia reales; cámara y GUI simuladas.
        events = [
            (100, -1),
            (100.5, 32),
            (102.5, -1),
            (103, ord("2")),
            (103.5, 32),
            (105.5, -1),
            (107.5, ord("q")),
        ]
        with tempfile.TemporaryDirectory() as temp:
            for angle in (0, 90, 180, 270):
                with self.subTest(angle=angle):
                    root = Path(temp) / str(angle)
                    originals = {}
                    for index, (stamp, _) in enumerate(events):
                        source = np.empty((240, 360, 3), dtype=np.uint8)
                        source[:120, :180] = (20 + index, 40, 220)
                        source[:120, 180:] = (40, 220 - index, 20)
                        source[120:, :180] = (220, 20 + index, 40)
                        source[120:, 180:] = (120, 200, 230 - index)
                        ok, encoded = cv2.imencode(".jpg", source)
                        self.assertTrue(ok)
                        originals[stamp] = encoded.tobytes()
                    reader, opener, response = (MagicMock() for _ in range(3))
                    reader.error = None
                    reader.state = "EN VIVO"
                    reader.drain_messages.return_value = []
                    reader.is_current.return_value = True
                    response.headers = {"Content-Type": "multipart/x-mixed-replace"}
                    opener.open.return_value = response
                    clock = [100.0]
                    pending = iter(events)
                    active = [events[0]]

                    def snapshot(active=active, pending=pending, clock=clock, originals=originals):
                        active[0] = next(pending)
                        clock[0] = active[0][0]
                        stamp = clock[0]
                        return originals[stamp], 1_000_000_000 + int(stamp * 1e9), stamp

                    reader.snapshot.side_effect = snapshot
                    args = capture.parser().parse_args(
                        [
                            "--destino",
                            str(root),
                            "--intervalo",
                            "2",
                            "--rotacion",
                            str(angle),
                        ]
                    )
                    with (
                        patch.object(capture, "ReconnectingStream", return_value=reader),
                        patch.object(
                            capture.time, "monotonic", side_effect=lambda clock=clock: clock[0]
                        ),
                        patch.object(cv2, "namedWindow"),
                        patch.object(cv2, "setWindowTitle") as window_title,
                        patch.object(cv2, "imshow"),
                        patch.object(cv2, "getWindowProperty", return_value=1),
                        patch.object(
                            cv2, "waitKey", side_effect=lambda delay, active=active: active[0][1]
                        ),
                        patch.object(cv2, "destroyAllWindows"),
                        patch.object(cv2, "line", wraps=cv2.line) as line,
                        contextlib.redirect_stdout(io.StringIO()),
                    ):
                        capture.run(args)
                    window_title.assert_called()
                    rows = core.read_rows(root)
                    self.assertEqual([row["sequence_id"] for row in rows], ["S1", "S1", "S2", "S2"])
                    self.assertEqual([int(row["t_capture_ms"]) for row in rows], [0, 2000, 0, 2000])
                    self.assertEqual(len({row["frame_id"] for row in rows}), 4)
                    height, width = (360, 240) if angle in (90, 270) else (240, 360)
                    for row, stamp in zip(rows, (100.5, 102.5, 103.5, 105.5), strict=True):
                        data = (root / row["path"]).read_bytes()
                        saved = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
                        decoded = cv2.imdecode(
                            np.frombuffer(originals[stamp], np.uint8), cv2.IMREAD_COLOR
                        )
                        # NumPy proporciona una referencia independiente del giro de OpenCV.
                        expected = np.rot90(decoded, k={0: 0, 90: -1, 180: 2, 270: 1}[angle])
                        self.assertEqual(saved.shape[:2], (height, width))
                        self.assertEqual(
                            (int(row["image_width"]), int(row["image_height"])), (width, height)
                        )
                        self.assertEqual(row["sha256"], core.digest(data))
                        self.assertTrue(row["path"].startswith(row["sequence_id"] + "/"))
                        # Permite pérdidas JPEG, pero no líneas, textos ni giros incorrectos.
                        difference = np.abs(saved.astype(float) - expected.astype(float))
                        self.assertLess(difference.mean(), 3)
                        if angle == 0:
                            self.assertEqual(data, originals[stamp])
                        else:
                            ok, clean = cv2.imencode(
                                ".jpg", expected, [cv2.IMWRITE_JPEG_QUALITY, 95]
                            )
                            self.assertTrue(ok)
                            # Igualdad exacta con un giro de referencia sin dibujar ninguna guía.
                            self.assertEqual(data, clean.tobytes())
                    coordinates = {(call.args[1], call.args[2]) for call in line.call_args_list}
                    self.assertEqual(
                        coordinates,
                        {
                            ((width // 3, 0), (width // 3, height - 1)),
                            ((2 * width // 3, 0), (2 * width // 3, height - 1)),
                            ((0, height // 2), (width - 1, height // 2)),
                        },
                    )
                    self.assertTrue(core.inspect(root, minimums=False)["ok"])
                    reader.stop.set.assert_called_once()
                    reader.close.assert_called_once()


class ReconnectionTests(unittest.TestCase):
    def connection(self, read):
        connection, response = MagicMock(), MagicMock()
        response.status = 200
        response.getheader.return_value = "multipart/x-mixed-replace; boundary=frame"
        response.read1.side_effect = read
        connection.getresponse.return_value = response
        return connection, response

    def test_timeout_cli_parameters_are_positive_and_configurable(self):
        args = capture.parser().parse_args([])
        self.assertEqual(
            (args.espera_inicial, args.espera_cuadros, args.reintento, args.edad_maxima),
            (10, 10, 2, 2),
        )
        args = capture.parser().parse_args(["--espera-inicial", "12", "--espera-cuadros", "15"])
        self.assertEqual((args.espera_inicial, args.espera_cuadros), (12, 15))
        for flag in ("--espera-inicial", "--espera-cuadros", "--reintento", "--edad-maxima"):
            for value in ("0", "-1", "nan", "inf"):
                with (
                    self.subTest(flag=flag, value=value),
                    contextlib.redirect_stderr(io.StringIO()),
                    self.assertRaises(SystemExit),
                ):
                    capture.parser().parse_args([flag, value])

    def test_initial_and_continuous_timeouts_have_distinct_diagnostics(self):
        for publish_first in (False, True):
            with self.subTest(publish_first=publish_first):
                clock = [100.0]
                reader = capture.ReconnectingStream(capture.DEFAULT_URL, 10, 3, 0.001)
                reader.clock = lambda clock=clock: int(clock[0] * 1e9)
                jpeg = b"\xff\xd8TEST ONLY first\xff\xd9"

                def timeout_chunk(publish_first=publish_first, clock=clock):
                    clock[0] = 104 if publish_first else 111
                    return b"headers without JPEG"

                steps = iter([jpeg, timeout_chunk] if publish_first else [timeout_chunk])

                def read(size, steps=steps):
                    item = next(steps)
                    return item() if callable(item) else item

                first, response = self.connection(read)
                second, _ = self.connection(lambda size: b"")

                def stop_on_connect(reader=reader):
                    reader.stop.set()

                second.connect.side_effect = stop_on_connect
                with (
                    patch.object(
                        capture.http.client, "HTTPConnection", side_effect=[first, second]
                    ),
                    patch.object(
                        capture.time, "monotonic", side_effect=lambda clock=clock: clock[0]
                    ),
                ):
                    reader.run()
                messages = " ".join(reader.drain_messages())
                self.assertIn(
                    "lectura continua MJPEG" if publish_first else "primer cuadro MJPEG", messages
                )
                self.assertIsNone(reader.error)
                response.close.assert_called_once()

    def test_connect_failure_retries_and_allows_slow_first_jpeg(self):
        clock = [100.0]
        reader = capture.ReconnectingStream(capture.DEFAULT_URL, 10, 10, 0.001)
        reader.clock = lambda: int(clock[0] * 1e9)
        first, _ = self.connection(lambda size: b"")
        first.connect.side_effect = OSError("ESP32 ocupado")
        jpeg = b"\xff\xd8TEST ONLY slow first\xff\xd9"

        def slow_read(size):
            clock[0] = 109.0
            return jpeg

        second, response = self.connection(slow_read)
        publications = []
        notify = reader.notify

        def observe(state, message=None):
            notify(state, message)
            if state == "EN VIVO":
                publications.append(reader.snapshot())
                reader.stop.set()

        with (
            patch.object(capture.http.client, "HTTPConnection", side_effect=[first, second]),
            patch.object(capture.time, "monotonic", side_effect=lambda: clock[0]),
            patch.object(reader, "notify", side_effect=observe),
        ):
            reader.run()
        self.assertEqual(publications, [(jpeg, 109_000_000_000, 109.0)])
        self.assertIn("conexión HTTP", " ".join(reader.drain_messages()))
        self.assertIsNone(reader.error)
        first.close.assert_called_once()
        response.close.assert_called_once()

    def test_frozen_jpeg_is_not_refreshed_even_after_reconnect(self):
        clock = [100.0]
        reader = capture.ReconnectingStream(capture.DEFAULT_URL, 10, 3, 0.001)
        reader.clock = lambda: int(clock[0] * 1e9)
        a, b = b"\xff\xd8TEST A\xff\xd9", b"\xff\xd8TEST B\xff\xd9"
        first_steps = iter([(100, a), (104, a)])
        second_steps = iter([(104, a), (105, b)])

        def first_read(size):
            clock[0], data = next(first_steps)
            return data

        def second_read(size):
            clock[0], data = next(second_steps)
            return data

        first, response1 = self.connection(first_read)
        second, response2 = self.connection(second_read)
        publications = []
        notify = reader.notify

        def observe(state, message=None):
            notify(state, message)
            if state == "EN VIVO":
                publications.append(reader.snapshot())
                if len(publications) == 2:
                    reader.stop.set()

        def check_previous_closed():
            response1.close.assert_called_once()
            first.close.assert_called_once()
            self.assertIsNone(reader.snapshot())

        second.connect.side_effect = check_previous_closed
        with (
            patch.object(capture.http.client, "HTTPConnection", side_effect=[first, second]),
            patch.object(capture.time, "monotonic", side_effect=lambda: clock[0]),
            patch.object(reader, "notify", side_effect=observe),
        ):
            reader.run()
        self.assertEqual(publications, [(a, 100_000_000_000, 100), (b, 105_000_000_000, 105)])
        self.assertIn("lectura continua MJPEG", " ".join(reader.drain_messages()))
        self.assertFalse(reader.is_current(publications[0][1], 2, 105))
        response2.close.assert_called_once()

    def test_temporary_read_error_recovers_on_a_new_connection(self):
        reader = capture.ReconnectingStream(capture.DEFAULT_URL, 10, 10, 0.001)
        a, b = b"\xff\xd8TEST before loss\xff\xd9", b"\xff\xd8TEST recovered\xff\xd9"
        first, response1 = self.connection([a, OSError("WiFi interrumpido")])
        second, response2 = self.connection([b])
        publications = []
        notify = reader.notify

        def observe(state, message=None):
            notify(state, message)
            if state == "EN VIVO":
                publications.append(reader.snapshot()[0])
                if len(publications) == 2:
                    reader.stop.set()

        with (
            patch.object(
                capture.http.client, "HTTPConnection", side_effect=[first, second]
            ) as factory,
            patch.object(reader, "notify", side_effect=observe),
        ):
            reader.run()
        self.assertEqual(publications, [a, b])
        self.assertEqual(factory.call_count, 2)
        first.request.assert_called_once_with(
            "GET", "/stream", headers={"Accept": "multipart/x-mixed-replace"}
        )
        second.request.assert_called_once_with(
            "GET", "/stream", headers={"Accept": "multipart/x-mixed-replace"}
        )
        self.assertIn("WiFi interrumpido", " ".join(reader.drain_messages()))
        self.assertIsNone(reader.error)
        response1.close.assert_called_once()
        response2.close.assert_called_once()

    def test_q_cancels_long_retry_delay_without_opening_another_connection(self):
        reader = capture.ReconnectingStream(capture.DEFAULT_URL, 10, 10, 30)
        connection, _ = self.connection(lambda size: b"")
        connection.connect.side_effect = OSError("sin conexión")
        closed = threading.Event()
        connection.close.side_effect = closed.set
        with patch.object(
            capture.http.client, "HTTPConnection", return_value=connection
        ) as factory:
            reader.thread.start()
            try:
                self.assertTrue(closed.wait(1))
                reader.close()
                self.assertFalse(reader.thread.is_alive())
                factory.assert_called_once()
                self.assertIsNone(reader.snapshot())
            finally:
                reader.stop.set()
                reader.thread.join(timeout=2)

    def test_q_interrupts_real_http_read_and_closes_cleanly(self):
        from http.server import BaseHTTPRequestHandler, HTTPServer

        release = threading.Event()
        received = threading.Event()
        failures = []

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
                self.end_headers()
                self.wfile.write(b"--frame\r\n\r\n\xff\xd8TEST ONLY loopback\xff\xd9\r\n")
                self.wfile.flush()
                release.wait(3)

            def log_message(self, *args):
                pass

        server = HTTPServer(("127.0.0.1", 0), Handler)
        service = threading.Thread(target=server.serve_forever, daemon=True)
        real_connection = capture.http.client.HTTPConnection
        reader = capture.ReconnectingStream(capture.DEFAULT_URL, 10, 10, 0.001)
        notify = reader.notify

        def observe(state, message=None):
            notify(state, message)
            if state == "EN VIVO":
                received.set()

        def connect(host, port, timeout):
            return real_connection("127.0.0.1", server.server_port, timeout=timeout)

        service.start()
        try:
            with (
                patch.object(capture.http.client, "HTTPConnection", side_effect=connect),
                patch.object(reader, "notify", side_effect=observe),
                patch.object(
                    threading,
                    "excepthook",
                    side_effect=lambda args: failures.append(args.exc_value),
                ),
            ):
                reader.thread.start()
                self.assertTrue(received.wait(2), "No llegó el JPEG del servidor local")
                self.assertTrue(
                    reader.is_current(reader.snapshot()[1], 2, capture.time.monotonic())
                )
                reader.close()
                self.assertFalse(reader.thread.is_alive())
                self.assertIsNone(reader.snapshot())
                self.assertIsNone(reader.error)
                self.assertEqual(failures, [])
        finally:
            reader.stop.set()
            release.set()
            reader.thread.join(timeout=2)
            server.shutdown()
            server.server_close()
            service.join(timeout=2)

    def test_q_during_connection_does_not_send_a_late_request(self):
        reader = capture.ReconnectingStream(capture.DEFAULT_URL, 2, 10, 0.001)
        entered, release = threading.Event(), threading.Event()
        connection, _ = self.connection(lambda size: b"")

        def connect():
            entered.set()
            release.wait(2)

        connection.connect.side_effect = connect
        errors = []

        def close():
            try:
                reader.close()
            except BaseException as exc:
                errors.append(exc)

        closer = threading.Thread(target=close)
        with patch.object(capture.http.client, "HTTPConnection", return_value=connection):
            reader.thread.start()
            try:
                self.assertTrue(entered.wait(1))
                closer.start()
                self.assertTrue(reader.stop.wait(1))
            finally:
                release.set()
                reader.thread.join(timeout=2)
                if closer.ident is not None:
                    closer.join(timeout=2)
        self.assertEqual(errors, [])
        self.assertFalse(reader.thread.is_alive())
        connection.request.assert_not_called()
        connection.close.assert_called_once()


class StreamTests(unittest.TestCase):
    def test_close_waits_until_read_finishes_before_closing_http(self):
        response = MagicMock()
        entered, release = threading.Event(), threading.Event()
        reading = [False]
        failures = []

        def read(size):
            reading[0] = True
            entered.set()
            try:
                if not release.wait(2):
                    raise TimeoutError("La prueba no liberó la lectura")
                return b"\xff\xd8TEST ONLY - frame arriving during Q\xff\xd9"
            finally:
                reading[0] = False

        def close_http():
            self.assertFalse(reading[0], "HTTP se cerró durante read1")

        response.read1.side_effect = read
        response.close.side_effect = close_http
        reader = capture.StreamReader(response)

        def stop_reader():
            try:
                reader.close()
            except BaseException as exc:
                failures.append(exc)

        closer = threading.Thread(target=stop_reader)
        with patch.object(
            threading, "excepthook", side_effect=lambda args: failures.append(args.exc_value)
        ):
            reader.thread.start()
            try:
                self.assertTrue(entered.wait(1))
                closer.start()
                self.assertTrue(reader.stop.wait(1))
                response.close.assert_not_called()
            finally:
                reader.stop.set()
                release.set()
                reader.thread.join(timeout=2)
                if closer.ident is not None:
                    closer.join(timeout=2)
        self.assertFalse(reader.thread.is_alive())
        self.assertFalse(closer.is_alive())
        self.assertEqual(failures, [])
        self.assertIsNone(reader.error)
        self.assertIsNone(reader.snapshot())
        response.read1.assert_called_once()
        response.close.assert_called_once()

    def test_expected_read_and_close_errors_are_ignored_only_after_stop(self):
        for error in (
            OSError("socket cerrado"),
            ValueError("respuesta cerrada"),
            capture.http.client.IncompleteRead(b"partial"),
        ):
            with self.subTest(error=type(error).__name__):
                response = MagicMock()
                entered = threading.Event()
                reader = capture.StreamReader(response)

                def read(size, reader=reader, entered=entered, error=error):
                    entered.set()
                    reader.stop.wait(2)
                    raise error

                response.read1.side_effect = read
                response.close.side_effect = OSError("cierre de socket cancelado")
                reader.thread.start()
                self.assertTrue(entered.wait(1))
                reader.close()
                self.assertFalse(reader.thread.is_alive())
                self.assertIsNone(reader.error)
                response.close.assert_called_once()

    def test_connection_failures_are_reported_while_capture_is_active(self):
        for error in (
            OSError("conexión perdida"),
            ValueError("respuesta inválida"),
            capture.http.client.IncompleteRead(b"partial"),
        ):
            with self.subTest(error=type(error).__name__):
                response = MagicMock()
                response.read1.side_effect = error
                reader = capture.StreamReader(response)
                reader.run()
                self.assertEqual(reader.error, str(error))
                response.close.assert_called_once()

    def test_unexpected_reader_bug_is_not_silently_discarded(self):
        response = MagicMock()
        response.read1.side_effect = AttributeError("fallo real inesperado")
        reader = capture.StreamReader(response)
        with self.assertRaisesRegex(AttributeError, "fallo real"):
            reader.run()
        response.close.assert_called_once()

    def test_timeout_does_not_close_http_from_another_thread(self):
        response = MagicMock()
        reader = capture.StreamReader(response)
        reader.thread = MagicMock()
        reader.thread.is_alive.return_value = True
        with self.assertRaisesRegex(OSError, "no terminó"):
            reader.close()
        self.assertTrue(reader.stop.is_set())
        reader.thread.join.assert_called_once_with(timeout=6)
        response.close.assert_not_called()

    def test_open_stream_stops_reader_and_closes_http_when_body_raises(self):
        response, opener = MagicMock(), MagicMock()
        response.headers = {"Content-Type": "multipart/x-mixed-replace"}
        opener.open.return_value = response
        reader = capture.StreamReader(response)

        def read(size):
            reader.stop.wait(2)
            return b""

        response.read1.side_effect = read
        with (
            patch.object(capture, "StreamReader", return_value=reader),
            self.assertRaisesRegex(ValueError, "falló la interfaz"),
            capture.open_stream(opener, object()),
        ):
            raise ValueError("falló la interfaz")
        self.assertTrue(reader.stop.is_set())
        self.assertFalse(reader.thread.is_alive())
        response.close.assert_called_once()

    def test_invalid_content_type_closes_http_without_starting_reader(self):
        response, opener = MagicMock(), MagicMock()
        response.headers = {"Content-Type": "text/html"}
        opener.open.return_value = response
        with (
            self.assertRaisesRegex(ValueError, "no es un stream"),
            capture.open_stream(opener, object()),
        ):
            self.fail("Se aceptó HTML como MJPEG")
        response.read1.assert_not_called()
        response.close.assert_called_once()

    def test_jpeg_markers_split_and_multiple_frames(self):
        parser = capture.JpegParser()
        self.assertEqual(parser.feed(b"header\xff"), [])
        self.assertEqual(parser.feed(b"\xd8TEST ONLY\xff"), [])
        self.assertEqual(
            parser.feed(b"\xd9boundary\xff\xd8SECOND TEST\xff\xd9"),
            [b"\xff\xd8TEST ONLY\xff\xd9", b"\xff\xd8SECOND TEST\xff\xd9"],
        )

    def test_parser_memory_bounded_for_incomplete_frame(self):
        parser = capture.JpegParser()
        with self.assertRaises(ValueError):
            parser.feed(b"\xff\xd8" + b"x" * (8 * 1024 * 1024))

    def test_parser_discards_non_jpeg_data(self):
        parser = capture.JpegParser()
        parser.feed(b"header" * 10000)
        self.assertLessEqual(len(parser.buffer), 1)

    def test_only_explicit_stream_url_allowed(self):
        self.assertEqual(capture.stream_url(capture.DEFAULT_URL), capture.DEFAULT_URL)
        for url in [
            "http://192.168.1.93",
            "http://192.168.1.93/control",
            "http://192.168.1.93:81/stream?motor=1",
            "https://host:81/stream",
            "http://user:pass@host:81/stream",
        ]:
            with self.subTest(url=url), self.assertRaises(argparse.ArgumentTypeError):
                capture.stream_url(url)

    def test_reader_reports_disconnect_and_keeps_latest_only(self):
        response = io.BytesIO(b"\xff\xd8FIRST TEST\xff\xd9\xff\xd8SECOND TEST\xff\xd9")
        reader = capture.StreamReader(response)
        reader.run()
        self.assertEqual(reader.snapshot()[0], b"\xff\xd8SECOND TEST\xff\xd9")
        self.assertIn("cerró", reader.error)


if __name__ == "__main__":
    unittest.main()
