"""Mide llegada de JPEG distintos y decodificables; no guarda fotografías."""

from __future__ import annotations

import argparse
import hashlib
import http.client
import time
from collections import deque
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlsplit

from capturar_esp32 import JpegParser, stream_url
from capturas_core import jpeg_dimensions
from mediciones_core import OUTPUT, export_report, repetitions, seconds, statistics_of


class HttpFrames:
    """Lectura síncrona de TODOS los JPEG; una sola conexión y ningún hilo residual."""

    def __init__(self, response, transport, clock=time.monotonic):
        self.response = response
        self.transport = transport
        self.clock = clock
        self.parser = JpegParser()
        self.pending = deque()

    def read_until(self, deadline):
        while not self.pending:
            remaining = deadline - self.clock()
            if remaining <= 0:
                raise TimeoutError("Plazo de lectura agotado")
            self.transport.settimeout(remaining)
            data = self.response.read1(4096)
            if not data:
                raise OSError("Stream cerrado antes de completar la ventana")
            arrived = self.clock()
            self.pending.extend((jpeg, arrived) for jpeg in self.parser.feed(data))
        return self.pending.popleft()


@contextmanager
def open_frames(url, initial_timeout):
    parsed = urlsplit(stream_url(url))
    connection = http.client.HTTPConnection(parsed.hostname, parsed.port, timeout=initial_timeout)
    response = None
    try:
        connection.connect()
        transport = connection.sock
        connection.request("GET", parsed.path, headers={"Accept": "multipart/x-mixed-replace"})
        response = connection.getresponse()
        if response.status != 200:
            raise OSError(f"HTTP {response.status} {response.reason}")
        if "multipart/x-mixed-replace" not in response.getheader("Content-Type", "").lower():
            raise ValueError("La respuesta no es MJPEG multipart")
        yield HttpFrames(response, transport)
    finally:
        try:
            if response is not None:
                response.close()
        finally:
            connection.close()


def measure(frames, duration=10.0, initial_timeout=10.0, frame_timeout=3.0, clock=time.monotonic):
    """Ancla en primer JPEG válido; cuenta llegadas nuevas en (inicio, inicio+duración].

    El primer JPEG solo ancla el reloj; un hash ya visto en esta repetición no cuenta.
    Ventana completa o error, nunca combina partes separadas por una reconexión.
    """
    start = None
    end = None
    last = None
    initial_deadline = clock() + initial_timeout
    seen = set()
    arrivals = []
    intervals = []
    duplicate_count = 0
    invalid_count = 0
    while True:
        frame_deadline = initial_deadline if start is None else last + frame_timeout
        deadline = frame_deadline if end is None else min(frame_deadline, end)
        if clock() >= deadline:
            if end is not None and deadline == end:
                break
            phase = (
                "primer JPEG válido" if start is None else "lectura continua / posible congelación"
            )
            raise TimeoutError(f"Sin cuadros nuevos: {phase}")
        try:
            jpeg, arrived = frames.read_until(deadline)
        except TimeoutError:
            if end is not None and deadline == end and clock() >= end:
                break
            phase = (
                "primer JPEG válido" if start is None else "lectura continua / posible congelación"
            )
            raise TimeoutError(f"Timeout en {phase}") from None
        if arrived > deadline:
            if end is not None and deadline == end:
                break
            raise TimeoutError("JPEG recibido después del plazo de frescura")
        try:
            jpeg_dimensions(jpeg)
        except ValueError:
            invalid_count += 1
            continue
        digest = hashlib.sha256(jpeg).hexdigest()
        if digest in seen:
            duplicate_count += 1
            continue
        seen.add(digest)
        if start is None:
            start = last = arrived
            end = start + duration
            continue
        intervals.append(arrived - last)
        arrivals.append(arrived - start)
        last = arrived
    if not arrivals:
        raise ValueError("No hubo cuadros nuevos durante la ventana")
    return {
        "estado": "completa",
        "ventana_efectiva_s": end - start,
        "cuadros_nuevos": len(arrivals),
        "fps_recibidos_distintos": len(arrivals) / (end - start),
        "llegadas_relativas_s": arrivals,
        "intervalos_s": intervals,
        "intervalos_resumen_s": statistics_of(intervals),
        "jpeg_duplicados_descartados": duplicate_count,
        "jpeg_invalidos_descartados": invalid_count,
        "inicio_recepcion_monotonic_s": start,
    }


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--url", type=stream_url, required=True, help="http://<IP>:81/stream")
    result.add_argument("--duracion", type=seconds, default=10.0)
    result.add_argument("--repeticiones", type=repetitions, default=3)
    result.add_argument("--espera-inicial", type=seconds, default=10.0)
    result.add_argument("--espera-cuadros", type=seconds, default=3.0)
    result.add_argument("--condiciones", default="No registradas")
    result.add_argument("--salida", type=Path, default=OUTPUT)
    return result


def main(argv=None):
    args = parser().parse_args(argv)
    report = {
        "url": args.url,
        "tipo": "FPS de recepción de JPEG decodificables con hashes distintos",
        "condiciones": args.condiciones,
        "duracion_solicitada_s": args.duracion,
        "repeticiones_solicitadas": args.repeticiones,
        "primer_cuadro": "ancla; no cuenta en el numerador",
        "pruebas": [],
    }
    interrupted = False
    print(f"Stream: {args.url}. Cerrar controles y capturador: un único cliente de cámara.")
    try:
        for number in range(1, args.repeticiones + 1):
            print(f"Repetición {number}: conectando; espera inicial {args.espera_inicial:g} s")
            try:
                with open_frames(args.url, args.espera_inicial) as frames:
                    trial = measure(frames, args.duracion, args.espera_inicial, args.espera_cuadros)
            except (OSError, ValueError, http.client.HTTPException) as exc:
                trial = {"estado": "invalida", "error": f"{type(exc).__name__}: {exc}"}
            trial["repeticion"] = number
            report["pruebas"].append(trial)
            print(trial)
    except KeyboardInterrupt:
        interrupted = True
        print("Medición interrumpida; conexión cerrada. No se completa la ventana artificialmente.")
    finally:
        valid = [
            p["fps_recibidos_distintos"] for p in report["pruebas"] if p["estado"] == "completa"
        ]
        report["completa"] = len(valid) == args.repeticiones
        report["resumen_fps_repeticiones_completas"] = statistics_of(valid) if valid else None
        print("Resumen:", report["resumen_fps_repeticiones_completas"])
        print("Informe:", export_report(report, args.salida, "fps"))
    return 130 if interrupted else (0 if report["completa"] else 1)


if __name__ == "__main__":
    raise SystemExit(main())
