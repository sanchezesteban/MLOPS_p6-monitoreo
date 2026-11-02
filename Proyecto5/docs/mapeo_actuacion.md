# P5-11 — Mapeo comando → actuación prevista en el auto

> **Pendiente (ver #57):** la ficha del vehículo de Bryan (P5-05: velocidad máxima real,
> ángulo máximo de dirección, distancia entre ejes) todavía no existe en el repo. Las
> constantes de esta página son **provisionales** (placeholders documentados) para poder
> cerrar P5-11 sin bloquearnos en esa dependencia; en cuanto la ficha esté, se actualizan
> aquí los valores de `V_MAX_FICHA` y `STEER_MAX_FICHA` y las tablas de ejemplo de abajo,
> sin tocar el código de `p5.control` (el adaptador solo mueve los campos `speed`/`steering`
> del contrato, nunca convierte unidades él mismo).

## Qué recibe el adaptador

`AdaptadorVirtual.enviar(comando)` recibe un `Command` del contrato (`config/contrato_v1.md`)
con `action`, `speed` ∈ [0, 1] y `steering` ∈ [-1, 1]. El adaptador **no convierte estos
valores a unidades físicas** — solo valida, registra en JSONL y (en modo virtual) nunca mueve
nada. La conversión de abajo es la que haría un controlador real (`--modo real`, no
implementado todavía) y sirve como referencia para quien lo construya.

## Correspondencia (provisional, hasta la ficha de #57)

| Campo del comando | Rango del contrato | Actuación prevista | Unidad física (placeholder) |
|---|---|---|---|
| `action = FORWARD` | — | Avanza en línea recta | — |
| `action = STEER_LEFT` | — | Avanza girando a la izquierda | — |
| `action = STEER_RIGHT` | — | Avanza girando a la derecha | — |
| `action = STOP` | `speed=0`, `steering=0` | Frena, motores en reposo | — |
| `speed` | `[0, 1]` | Fracción de la velocidad máxima del vehículo | `speed * V_MAX_FICHA` (m/s) |
| `steering` | `[-1, 1]` (− = izquierda) | Fracción del ángulo máximo de dirección | `steering * STEER_MAX_FICHA` (grados) |
| `valid_until_ms` | número o `null` | Tiempo límite antes de que el adaptador detenga el comando sin esperar otro cuadro | ms, reloj de la ejecución |

`V_MAX_FICHA` y `STEER_MAX_FICHA` salen de la ficha del vehículo de Bryan (#57); hasta
entonces no hay un valor real que poner aquí.

## Ejemplo con los JSON de `config/ejemplos/`

- `comando_forward.json`: `speed=0.4` → 40 % de la velocidad máxima configurada, línea recta
  (`steering=0.0`), válido hasta `valid_until_ms=1013.0`.
- `comando_stop.json`: `action=STOP` → frena de inmediato, cancela cualquier comando anterior
  aunque no haya vencido (regla 4 del contrato).

## Saturación segura ante un comando fuera de contrato

Si `enviar()` recibe un comando con `speed`/`steering` fuera de rango o no finito, o con un
`run_id` que no es el de la corrida (regla E4/5.1: el adaptador no confía a ciegas en quien le
manda el comando), **no lo ejecuta tal cual**: lo rechaza y en su lugar registra un `STOP` (ver
`AdaptadorVirtual._comando_stop` en `src/p5/control.py`), con el detalle del rechazo en el campo
`error` del registro JSONL. Parar es siempre una actuación válida dentro del contrato, así que
STOP es la saturación segura — no hace falta clamping campo por campo.

## Evidencia

[`docs/evidencia/log-ejemplo.jsonl`](evidencia/log-ejemplo.jsonl): una corrida real contra
`src/p5/control.py` (no inventada) con un comando `FORWARD` válido (`t_command_ms` puesto por el
adaptador al recibirlo, no el del ejemplo), un comando inválido (`speed=1.7`, rechazado con el
`frame_id` original conservado y el detalle del schema en `error`), un `stop("vencimiento_watchdog")`
directo, y el `STOP` de `cerrar()` (razón `shutdown`) que siempre queda en la bitácora al cerrar,
con reloj inyectado para que los tiempos sean reproducibles.
