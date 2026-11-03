# Watchdog, vencimiento y emergencia (P5-12)

Quien arma el `Command` del contrato v1 (`config/contrato_v1.md`) a partir de la `Decision`
de la política (`docs/politica.md`, grupo B, P5-10): agrega `run_id`, los tiempos y
`valid_until_ms` con un único reloj (el mismo que usa el `ControladorMotores` de P5-11 —
nunca dos relojes independientes para una misma corrida).

| Archivo | Qué es |
|---|---|
| `config/watchdog.yaml` | Plazos (`plazo_reaccion_ms`, `max_edad_ms`, `vencimiento_ms`) |
| `src/p5/watchdog.py` | `RelojControlado`, `cargar_config` y la clase `Watchdog` |
| `tests/test_watchdog.py` | Corte de cuadros, cuadro viejo, vencimiento de comando, emergencia/rearme y cierre, con reloj controlado |

## Plazos (provisionales, ver justificación)

| Parámetro | Valor | Justificación |
|---|---:|---|
| `plazo_reaccion_ms` | 100 ms | Ritmo de captura asumido por ahora (~10 cuadros/s ⇒ ~100 ms entre cuadros, mismo orden que los ejemplos del contrato). El watchdog debe revisar al menos una vez por cada periodo de cuadro para no tardar un cuadro entero en reaccionar |
| `max_edad_ms` | 300 ms | Tolera perder hasta 2 cuadros seguidos (3 × el periodo de captura) antes de considerar la percepción vencida; evita frenar por un solo cuadro tardío |
| `vencimiento_ms` | 250 ms | Ventana de validez de un comando de movimiento (~2.5 cuadros) sin que llegue uno nuevo que lo reemplace. Menor que `max_edad_ms` a propósito: si deja de llegar percepción, el comando en curso vence primero (regla normal del contrato) y recién si eso tampoco alcanza, el watchdog detecta la pérdida de cuadros por su cuenta |

Estos tres números no vienen de una medición real de la cámara (P5-02/P5-07) ni de la ficha
del vehículo (#57): son una primera aproximación razonable para no bloquear #64. Se ajustan
aquí, en `watchdog.yaml`, sin tocar `src/p5/watchdog.py`, en cuanto se conozca el ritmo real.

## Qué hace el `Watchdog`

- **`procesar_evento(evento)`**: por cada `PerceptionEvent` que llega de A. Si el cuadro ya
  nació vencido por nuestro reloj (`esta_vencido`), aunque A lo reporte `status=ok`, nunca se
  le pasa a la política tal cual: se decide como un cuadro `status="stale"` (conserva su
  `frame_id`, para saber cuál se rechazó, y sale con `event="stale_frame"`, `reason="cuadro_vencido"`)
  y no se reanuda movimiento con un cuadro viejo.
- **`tick(ahora=None)`**: revisión periódica sin esperar un cuadro nuevo. Si el comando en
  curso ya pasó su `valid_until_ms`, o no ha llegado un cuadro fresco en `max_edad_ms`, emite
  `STOP` por su cuenta (`event="watchdog"`, `razon="comando_vencido"` o `"sin_cuadros_recientes"`).
- **`emergencia(razon)`**: `STOP` inmediato con prioridad sobre todo (`event="emergency"`).
  Queda **enclavada**: mientras no se libere, `procesar_evento` no le pasa el cuadro a la
  política (no reanuda solo porque se acumularon cuadros libres), pero tampoco lo omite en
  silencio — cada cuadro que llega mientras está enclavada queda igual en la bitácora
  (`event="emergency"`, `reason="emergencia_enclavada"`, con su `frame_id`).
- **`rearme()`**: pide liberar la emergencia y ese pedido en sí queda registrado
  (`event="rearm"`), pero no libera nada todavía — solo cuando después llega un cuadro
  realmente fresco (`status=ok` y no vencido) se libera el enclave y ese cuadro (y los
  siguientes) vuelven a pasar por la política con normalidad. Como el estado de la política
  queda en `FALLA`, reanudar sigue pidiendo `cuadros_liberar` cuadros libres seguidos
  (histéresis de `docs/politica.md`), no solo el primero tras el rearme.
- **`cerrar()` / `instalar_señales()`**: cierre normal, `SIGINT` y `SIGTERM` delegan en
  `ControladorMotores.cerrar()`, que siempre registra el `STOP` de cierre (`event="shutdown"`,
  criterio C10 de P5-11) aunque ya estuviera detenido. El manejador de señal, después de
  cerrar, termina el programa (`SystemExit(128 + signum)`, convención Unix) — no se queda
  corriendo ignorando en silencio lo que llegue después.
