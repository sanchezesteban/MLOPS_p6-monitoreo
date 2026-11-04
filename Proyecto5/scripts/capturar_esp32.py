"""Vista previa y captura de un único stream MJPEG. Sin comandos al vehículo."""

from __future__ import annotations

import argparse
import http.client
import math
import socket
import threading
import time
import uuid
from collections import deque
from contextlib import contextmanager, suppress
from pathlib import Path
from urllib.parse import urlsplit

from capturas_core import SEQUENCES, CaptureStore, anchored_clock

DEFAULT_URL = "http://192.168.1.93:81/stream"
DEFAULT_DATA = Path(__file__).resolve().parents[1] / "datos" / "evaluacion"


def stream_url(value: str) -> str:
    parsed = urlsplit(value)
    if (
        parsed.scheme != "http"
        or not parsed.hostname
        or parsed.port != 81
        or parsed.path != "/stream"
        or parsed.query
        or parsed.fragment
        or parsed.username
        or parsed.password
    ):
        raise argparse.ArgumentTypeError("Usar solo http://<IP>:81/stream, sin credenciales")
    return value


class JpegParser:
    """Extrae JPEG aunque los límites MJPEG lleguen partidos entre lecturas."""

    def __init__(self):
        self.buffer = bytearray()

    def feed(self, chunk: bytes) -> list[bytes]:
        self.buffer.extend(chunk)
        frames = []
        while True:
            start = self.buffer.find(b"\xff\xd8")
            if start < 0:
                self.buffer[:] = self.buffer[-1:]
                break
            if start:
                del self.buffer[:start]
            end = self.buffer.find(b"\xff\xd9", 2)
            if end < 0:
                if len(self.buffer) > 8 * 1024 * 1024:
                    raise ValueError("JPEG incompleto mayor a 8 MiB")
                break
            frames.append(bytes(self.buffer[: end + 2]))
            del self.buffer[: end + 2]
        return frames


class StreamReader:
    """Un lector en segundo plano; conserva solo el cuadro más reciente."""

    def __init__(self, response):
        self.response = response
        self.latest = None
        self.error = None
        self.guard = threading.Lock()
        self.stop = threading.Event()
        self.clock = anchored_clock()
        self.thread = threading.Thread(target=self.run, daemon=True)

    def run(self):
        parser = JpegParser()
        try:
            while not self.stop.is_set():
                chunk = self.response.read1(4096)
                if self.stop.is_set():
                    break
                if not chunk:
                    raise OSError("El stream se cerró")
                for data in parser.feed(chunk):
                    with self.guard:
                        self.latest = (data, self.clock(), time.monotonic())
        except (OSError, ValueError, http.client.HTTPException) as exc:
            if not self.stop.is_set():
                self.error = str(exc)
        finally:
            # Solo el lector cierra HTTP: nunca mientras otro hilo está en read1.
            try:
                self.response.close()
            except (OSError, ValueError, http.client.HTTPException) as exc:
                if not self.stop.is_set():
                    self.error = self.error or f"Error al cerrar HTTP: {exc}"

    def close(self):
        self.stop.set()
        self.thread.join(timeout=6)
        if self.thread.is_alive():
            # La respuesta sigue siendo propiedad del lector; no cerrarla desde aquí.
            raise OSError("El lector MJPEG no terminó en 6 s; conexión pendiente de cierre")

    def snapshot(self):
        with self.guard:
            return self.latest


@contextmanager
def open_stream(opener, request):
    response = opener.open(request, timeout=5)
    try:
        if "multipart/x-mixed-replace" not in response.headers.get("Content-Type", "").lower():
            raise ValueError("La respuesta no es un stream MJPEG multipart")
        reader = StreamReader(response)
        reader.thread.start()
    except BaseException:
        # Todavía no hay un lector que sea propietario de la conexión.
        response.close()
        raise
    try:
        yield reader
    finally:
        reader.close()


class ReconnectingStream(StreamReader):
    """Un solo hilo posee conexión y respuesta, incluso durante las reconexiones."""

    def __init__(self, url, initial_wait=10.0, frame_wait=10.0, retry_delay=2.0):
        super().__init__(None)
        self.url = urlsplit(stream_url(url))
        self.initial_wait = initial_wait
        self.frame_wait = frame_wait
        self.retry_delay = retry_delay
        self.state = "CONECTANDO"
        self.messages = deque()
        self.transport = None
        self.last_jpeg = None

    def notify(self, state, message=None):
        with self.guard:
            self.state = state
            if message:
                self.messages.append(message)

    def drain_messages(self):
        with self.guard:
            messages = list(self.messages)
            self.messages.clear()
            return messages

    def is_current(self, stamp, maximum_age, now):
        with self.guard:
            return (
                not self.stop.is_set()
                and self.state == "EN VIVO"
                and self.latest is not None
                and self.latest[1] == stamp
                and now - self.latest[2] <= maximum_age
            )

    def run(self):
        while not self.stop.is_set():
            connection = None
            response = None
            phase = "conexión HTTP"
            self.notify("CONECTANDO")
            try:
                connection = http.client.HTTPConnection(
                    self.url.hostname, self.url.port, timeout=self.initial_wait
                )
                connection.connect()
                transport = connection.sock
                with self.guard:
                    self.transport = transport
                if self.stop.is_set():
                    break
                connection.request(
                    "GET", self.url.path, headers={"Accept": "multipart/x-mixed-replace"}
                )
                response = connection.getresponse()
                if response.status != 200:
                    raise OSError(f"HTTP {response.status} {response.reason}")
                if (
                    "multipart/x-mixed-replace"
                    not in response.getheader("Content-Type", "").lower()
                ):
                    raise ValueError("La respuesta no es un stream MJPEG multipart")
                phase = "primer cuadro MJPEG"
                self.notify("ESPERANDO VIDEO")
                started = time.monotonic()
                last_new = None
                parser = JpegParser()
                while not self.stop.is_set():
                    now = time.monotonic()
                    deadline = (
                        started + self.initial_wait
                        if last_new is None
                        else last_new + self.frame_wait
                    )
                    remaining = deadline - now
                    if remaining <= 0:
                        raise TimeoutError(
                            f"Sin cuadros JPEG distintos durante "
                            f"{self.initial_wait if last_new is None else self.frame_wait:g} s"
                        )
                    # El timeout se aplica a la lectura pendiente; no exige un JPEG cada 2 s.
                    transport.settimeout(remaining)
                    chunk = response.read1(4096)
                    if self.stop.is_set():
                        break
                    if not chunk:
                        raise OSError("El stream se cerró")
                    for data in parser.feed(chunk):
                        # Un JPEG idéntico no renueva su fecha ni descongela la captura.
                        if data == self.last_jpeg:
                            continue
                        now = time.monotonic()
                        with self.guard:
                            if self.stop.is_set():
                                break
                            self.latest = (data, self.clock(), now)
                            self.last_jpeg = data
                        if last_new is None:
                            self.notify("EN VIVO", "INFO: video disponible; captura habilitada")
                        last_new = now
                        phase = "lectura continua MJPEG"
            except (OSError, ValueError, http.client.HTTPException) as exc:
                if not self.stop.is_set():
                    hint = (
                        "Comprobar IP, Wi-Fi y puerto 81."
                        if phase == "conexión HTTP"
                        else "Cerrar otros clientes y la página de controles; "
                        "un cliente ocupado es una posibilidad, no un diagnóstico confirmado."
                    )
                    self.notify(
                        "RECONECTANDO",
                        f"ADVERTENCIA [{phase}]: {exc}. "
                        f"{hint} Reintento en {self.retry_delay:g} s; capturas bloqueadas.",
                    )
            except Exception as exc:
                # Un fallo de programación es fatal y se informa al visor, no se reintenta.
                self.error = f"{type(exc).__name__}: {exc}"
                return
            finally:
                with self.guard:
                    self.latest = None
                    self.transport = None
                # Solo este hilo cierra los objetos HTTP, una vez que terminó read1.
                for resource in (response, connection):
                    if resource is not None:
                        try:
                            resource.close()
                        except (OSError, ValueError, http.client.HTTPException) as exc:
                            if not self.stop.is_set():
                                self.notify("RECONECTANDO", f"ADVERTENCIA [cierre HTTP]: {exc}")
            if self.stop.wait(self.retry_delay):
                break
        self.notify("DETENIDO")

    def close(self):
        self.stop.set()
        with self.guard:
            transport = self.transport
            self.latest = None
        if transport is not None:
            with suppress(OSError):
                # Desbloquea read1 sin invalidar concurrentemente el objeto HTTPResponse.
                transport.shutdown(socket.SHUT_RDWR)
        self.thread.join(timeout=self.initial_wait + 1)
        if self.thread.is_alive():
            raise OSError("El lector MJPEG sigue esperando la conexión HTTP; cierre pendiente")


@contextmanager
def reconnecting_stream(args):
    reader = ReconnectingStream(args.url, args.espera_inicial, args.espera_cuadros, args.reintento)
    reader.thread.start()
    try:
        yield reader
    finally:
        reader.close()


def positive_seconds(value):
    result = float(value)
    if not math.isfinite(result) or result <= 0:
        raise argparse.ArgumentTypeError("Usar un número de segundos finito mayor que cero")
    return result


def resolution(value):
    try:
        width, height = map(int, value.lower().split("x"))
    except (ValueError, TypeError) as exc:
        raise argparse.ArgumentTypeError("Usar ANCHOxALTO, por ejemplo 400x296") from exc
    if width <= 0 or height <= 0:
        raise argparse.ArgumentTypeError("La resolución debe tener dimensiones positivas")
    return width, height


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--url", type=stream_url, default=DEFAULT_URL)
    result.add_argument("--destino", type=Path, default=DEFAULT_DATA)
    result.add_argument("--secuencia", choices=SEQUENCES, default="S1")
    result.add_argument(
        "--resolucion",
        type=resolution,
        default=None,
        help="Exigir dimensiones del JPEG orientado (p. ej. 400x296); "
        "no redimensiona ni cambia firmware",
    )
    result.add_argument(
        "--rotacion",
        type=int,
        choices=(0, 90, 180, 270),
        default=0,
        help="Giro de vista previa y nuevos JPEG: 90 horario, 270 antihorario; 0 sin giro",
    )
    result.add_argument(
        "--intervalo", type=float, default=0, help="Segundos entre capturas automáticas; 0 = manual"
    )
    result.add_argument(
        "--sesion", default=None, help="Identificador de sesión física; por defecto UUID nuevo"
    )
    result.add_argument(
        "--espera-inicial",
        type=positive_seconds,
        default=10.0,
        help="Timeout HTTP y espera del primer JPEG por conexión (s; defecto 10)",
    )
    result.add_argument(
        "--espera-cuadros",
        type=positive_seconds,
        default=10.0,
        help="Interrupción máxima sin JPEG distinto antes de reconectar (s)",
    )
    result.add_argument(
        "--reintento",
        type=positive_seconds,
        default=2.0,
        help="Espera entre conexiones, interrumpible con Q (s)",
    )
    result.add_argument(
        "--edad-maxima",
        type=positive_seconds,
        default=2.0,
        help="Edad máxima de un cuadro para guardarlo; no cierra el programa (s)",
    )
    return result


def rotate_frame(frame, rotation: int):
    """Orienta el cuadro antes de dibujar o codificar; 90 = horario."""
    import cv2

    if rotation == 0:
        return frame
    codes = {90: cv2.ROTATE_90_CLOCKWISE, 180: cv2.ROTATE_180, 270: cv2.ROTATE_90_COUNTERCLOCKWISE}
    if rotation not in codes:
        raise ValueError("Rotación inválida: usar 0, 90, 180 o 270")
    return cv2.rotate(frame, codes[rotation])


def jpeg_for_capture(original: bytes, oriented_frame, rotation: int) -> bytes:
    """Codifica el cuadro orientado sin guías; con 0 conserva el JPEG original."""
    import cv2

    if rotation == 0:
        return original
    ok, encoded = cv2.imencode(".jpg", oriented_frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
    if not ok:
        raise ValueError("No se pudo codificar el JPEG rotado")
    return encoded.tobytes()


def auto_status(auto: bool, ever_started: bool) -> str:
    if auto:
        return "ACTIVA"
    return "PAUSADA" if ever_started else "DETENIDA"


def draw_preview(frame, sequence, count, label, outside, status, guides=True):
    """Dibuja únicamente sobre una copia; nunca recibe ni recodifica el JPEG."""
    import cv2

    preview = frame.copy()
    height, width = preview.shape[:2]
    font = cv2.FONT_HERSHEY_SIMPLEX
    small = max(0.25, min(0.45, width / 1600))
    if guides:
        color = (0, 210, 210)
        for x in (width // 3, 2 * width // 3):
            cv2.line(preview, (x, 0), (x, height - 1), color, 1, cv2.LINE_AA)
        cv2.line(preview, (0, height // 2), (width - 1, height // 2), color, 1, cv2.LINE_AA)
        for index, text in enumerate(("IZQUIERDA", "CENTRO", "DERECHA")):
            (text_width, _), _ = cv2.getTextSize(text, font, small, 1)
            x = max(0, round((index + 0.5) * width / 3 - text_width / 2))
            cv2.putText(preview, text, (x, 64), font, small, color, 1, cv2.LINE_AA)
    status_color = {"ACTIVA": (0, 255, 0), "PAUSADA": (0, 220, 255), "DETENIDA": (80, 80, 255)}
    cv2.rectangle(preview, (0, 0), (width - 1, 44), (20, 20, 20), -1)
    cv2.putText(
        preview,
        f"SECUENCIA: {sequence} | AUTO: {status}",
        (8, 19),
        font,
        max(0.3, min(0.55, width / 1000)),
        status_color[status],
        1,
        cv2.LINE_AA,
    )
    details = f"n={count} {label} fuera={int(outside)} | G: guias {'ON' if guides else 'OFF'}"
    cv2.putText(preview, details, (8, 38), font, small, (220, 220, 220), 1, cv2.LINE_AA)
    return preview


def run(args):
    import cv2
    import numpy as np

    sequence, label, outside = args.secuencia, "pendiente", False
    auto = args.intervalo > 0
    ever_started = auto
    guides = True
    interval = args.intervalo or 1.0
    next_capture = time.monotonic() + interval
    session = args.sesion or uuid.uuid4().hex
    print(f"URL del stream: {args.url}")
    print(f"Sesión: {session}\nDestino: {args.destino.resolve()}")
    print(f"Rotación: {args.rotacion} grados (90 horario, 270 antihorario)")
    print("Cerrar controles y otros visores. Solo una conexión al stream.")
    print("1-6: secuencia | espacio/C: capturar | A: auto | Q/ESC: salir")
    print("B: obstáculo | D: despejado | U: pendiente | Z: objeto fuera de riesgo")
    print("G: mostrar/ocultar guías (solo vista previa; JPEG guardado sin anotaciones)")

    with CaptureStore(args.destino, session) as store:
        # HTTP directo: sin proxies, redirecciones ni visitas a la página de controles.
        with reconnecting_stream(args) as reader:
            window = "P5 ESP32-CAM - captura"
            last_display = None
            last_preview = None
            frame = None
            displayed = None
            sequence_changed_at = None
            was_fresh = False
            last_stream_state = None
            try:
                cv2.namedWindow(window, cv2.WINDOW_NORMAL)
                cv2.imshow(window, np.zeros((480, 640, 3), dtype=np.uint8))
                while True:
                    if reader.error:
                        raise OSError(reader.error)
                    for message in reader.drain_messages():
                        print(message)
                    current = reader.snapshot()
                    now = time.monotonic()
                    fresh = current is not None and now - current[2] <= args.edad_maxima
                    if current is None:
                        displayed = None
                        last_display = None
                    elif current[1] != last_display:
                        frame = cv2.imdecode(
                            np.frombuffer(current[0], dtype=np.uint8), cv2.IMREAD_COLOR
                        )
                        if frame is None:
                            # Un JPEG corrupto no se guarda; el visor puede recibir el siguiente.
                            print("ADVERTENCIA: JPEG no decodificable; captura bloqueada")
                            displayed = None
                            fresh = False
                        else:
                            frame = rotate_frame(frame, args.rotacion)
                            expected = getattr(args, "resolucion", None)
                            if (
                                expected is not None
                                and (frame.shape[1], frame.shape[0]) != expected
                            ):
                                raise ValueError(
                                    f"Resolución recibida {frame.shape[1]}x{frame.shape[0]}; "
                                    f"se exige {expected[0]}x{expected[1]}. "
                                    "Captura detenida sin redimensionar; revisar la cámara."
                                )
                            displayed = current
                        last_display = current[1]
                    fresh = fresh and displayed is not None
                    stream_state = f"{reader.state} | {'LISTO' if fresh else 'CAPTURAS BLOQUEADAS'}"
                    if stream_state != last_stream_state:
                        print(
                            f"Stream: {reader.state}; "
                            f"{'listo' if fresh else 'esperando video fresco'}"
                        )
                        cv2.setWindowTitle(window, f"{window} | {stream_state}")
                        last_stream_state = stream_state
                    if was_fresh and not fresh:
                        print(
                            "ADVERTENCIA: sin cuadro fresco; "
                            "guardado bloqueado hasta recuperar video"
                        )
                    if fresh and not was_fresh:
                        next_capture = now + interval
                    was_fresh = fresh
                    status = auto_status(auto and fresh, ever_started)
                    preview_state = (
                        last_display,
                        sequence,
                        store.counts[sequence],
                        label,
                        outside,
                        status,
                        guides,
                        stream_state,
                    )
                    if frame is not None and preview_state != last_preview:
                        cv2.imshow(
                            window,
                            draw_preview(
                                frame,
                                sequence,
                                store.counts[sequence],
                                label,
                                outside,
                                status,
                                guides,
                            ),
                        )
                        last_preview = preview_state
                    key = cv2.waitKey(10) & 0xFF
                    if (
                        key in (ord("q"), ord("Q"), 27)
                        or cv2.getWindowProperty(window, cv2.WND_PROP_VISIBLE) < 1
                    ):
                        break
                    # El intervalo empieza cuando se procesa la tecla, no antes de waitKey.
                    now = time.monotonic()
                    if ord("1") <= key <= ord("6"):
                        sequence = f"S{chr(key)}"
                        label, outside = "pendiente", False
                        sequence_changed_at = now
                        displayed = None
                        last_display = None
                        next_capture = now + interval
                        mode = (
                            f"captura automática continúa; próxima captura en {interval:g} s"
                            if auto
                            else "captura automática inactiva; Espacio para capturar"
                        )
                        print(f"Secuencia activa: {sequence}; {mode}")
                    elif key in (ord("b"), ord("B")):
                        label = "obstaculo"
                    elif key in (ord("d"), ord("D")):
                        label = "despejado"
                    elif key in (ord("u"), ord("U")):
                        label = "pendiente"
                    elif key in (ord("z"), ord("Z")):
                        outside = not outside
                    elif key in (ord("a"), ord("A")):
                        auto = not auto
                        ever_started = True
                        next_capture = now + interval
                    elif key in (ord("g"), ord("G")):
                        guides = not guides
                    manual = key in (32, ord("c"), ord("C"))
                    if (
                        displayed
                        and (sequence_changed_at is None or displayed[2] >= sequence_changed_at)
                        and now - displayed[2] <= args.edad_maxima
                        and reader.state == "EN VIVO"
                        and reader.is_current(displayed[1], args.edad_maxima, now)
                        and (manual or (auto and now >= next_capture))
                    ):
                        data = jpeg_for_capture(displayed[0], frame, args.rotacion)
                        print(store.save(data, sequence, displayed[1], label, outside))
                        next_capture = now + interval
            except cv2.error as exc:
                raise ValueError(f"OpenCV: {exc}. Usar opencv-python con GUI local.") from exc
            finally:
                reader.stop.set()
                print("Captura detenida; AUTO: DETENIDA")
                with suppress(cv2.error):
                    cv2.destroyAllWindows()
        print("Conteo: " + ", ".join(f"{seq}={store.counts[seq]}" for seq in SEQUENCES))


def main():
    argument_parser = parser()
    args = argument_parser.parse_args()
    if not math.isfinite(args.intervalo) or args.intervalo < 0:
        argument_parser.error("--intervalo debe ser finito y >= 0")
    if args.sesion is not None and not args.sesion.strip():
        argument_parser.error("--sesion no puede estar vacía")
    try:
        run(args)
    except KeyboardInterrupt:
        print("Captura detenida.")
        return 130
    except (OSError, ValueError, ImportError) as exc:
        print(f"ERROR: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
