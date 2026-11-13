# Escenarios adicionales (extras S)

Estos escenarios usan **el mismo código de monitoreo y la misma configuración** que C1 y C2:
- `src/` y `config/` no cambian, y `config_sha256` sigue siendo `62a273b9…`;
- la referencia es la misma (`5d512afc…`) y el modelo también (`c789161e…`).

Lo único que cambia es la entrada, preparada con [`scripts/preparar_extras.py`](../scripts/preparar_extras.py) en el commit `4bb00ad`, que es el que registra cada `run.json` (`git_sucio = 0`). Todos los scores salen de inferencia real.

Cada manifiesto tiene una columna `fase` que hace de **registro del incidente**: indica el frame donde empieza la condición y el frame donde empieza la recuperación. Con ella se mide el tiempo de detección y de recuperación (M-07 y M-08 en [`extras.md`](extras.md)).

## S-01 · Cambio sostenido de confianza, con transición y recuperación (`s-sostenido`)

**Entrada:** [`escenarios/s_sostenido.csv`](../escenarios/s_sostenido.csv), 90 frames a 5 fps, en tres fases:

| Frames | Fase | Contenido |
|---|---|---|
| 0–19 | normal | S5 + S4 originales |
| 20–59 | degradada | S2 + S3 + S6 con compresión **JPEG de calidad 5** (`datos/s_sostenido_jpeg5/`). Simula una cámara con ancho de banda saturado. |
| 60–89 | recuperación | S2 + S3 originales |

**Comando:**

```bash
PYTHONPATH=src python -m p6.monitor --manifiesto escenarios/s_sostenido.csv --escenario S-sostenido \
    --run-id s-sostenido --db evidencias/monitoreo.db --capturas evidencias/capturas \
    --salida evidencias/escenarios/s-sostenido
```

**Esperado:**
- La proporción de frames bajos sube durante la fase degradada.
- `cambio-sostenido-v1` se abre solo cuando la proporción − 0.146 ≥ 0.25 se cumple en **3 ventanas suficientes seguidas**, y se resuelve en la primera ventana suficiente que ya no exceda.
- `baja-confianza-v1` se abre antes, porque basta una ventana.

**Observado** (`evidencias/escenarios/s-sostenido/ventanas.jsonl` y `alertas.jsonl`):

| Ventana | w000 | w001 | w002 | w003 | w004 | w005 | w006 | w007 | w008 |
|---|---|---|---|---|---|---|---|---|---|
| bajos / puntuados | 0/10 | 2/10 | 6/10 | 6/9 | 6/10 | 6/10 | 3/10 | 1/9 | 2/10 |
| racha de `cambio-sostenido` | 0 | 0 | 1 | 2 | **3 → abre** | 4 | **0 → resuelve** | 0 | 0 |
| alertas activas (G7) | 0 | 0 | 1 | 1 | 2 | 2 | 0 | 0 | 0 |

- `s-sostenido-a001` (`baja-confianza-v1`, warning): se abre en w002 y se resuelve en w006.
- `s-sostenido-a002` (`cambio-sostenido-v1`, critical): se abre en w004. Su motivo dice «proporción baja 0.600 vs referencia 0.146 (delta +0.454, tolerancia 0.25); racha 3/3». Se resuelve en w006 y queda vinculada a 24 eventos bajos de w002–w005.
- **Persistencia comprobada:** la ventana w002, aunque excede, **no** dispara el cambio sostenido.
- Tiempo de detección desde el frame 20: **1.824 s** para baja confianza y **5.832 s** para cambio sostenido. Tiempo de recuperación desde el frame 60: 1.823 s.
- KS contra la referencia: 0.56–0.66 en las ventanas degradadas y 0.18–0.37 en las normales.

**Evidencia:**
- `evidencias/escenarios/s-sostenido/`: `run.json`, los JSONL, `recalculo.json` (71 comprobaciones, 0 fallidas) y `metricas_extra.json`.
- 64 capturas.
- Portal: [`F1-graficas-s-sostenido.png`](../evidencias/extras/portal/F1-graficas-s-sostenido.png), [`S-alerta-cambio-sostenido.png`](../evidencias/extras/portal/S-alerta-cambio-sostenido.png), [`S-ventanas-s-sostenido.png`](../evidencias/extras/portal/S-ventanas-s-sostenido.png), [`S-alertas-s-sostenido.png`](../evidencias/extras/portal/S-alertas-s-sostenido.png).

Este escenario no se superpone con C2: C2 solo acredita la alerta de baja confianza (su racha de cambio sostenido llegó a 1 de 3), mientras que aquí se demuestra la regla temporal de R3.3 con transición, persistencia y recuperación.

## S-02 · Interrupción del stream: fallo, reacción, recuperación y verificación (`s-interrupcion`)

**Entrada:** [`escenarios/s_interrupcion.csv`](../escenarios/s_interrupcion.csv), 80 frames, en tres fases:

| Frames | Fase | Contenido |
|---|---|---|
| 0–19 | normal | Originales |
| 20–49 | sin señal | La cámara deja de entregar imagen. Las filas apuntan a `fuente-sin-senal/frame-NNN.jpg`, que **no existe a propósito**; la fuente sigue emitiendo frames al mismo ritmo. |
| 50–79 | recuperación | S2 + S3 originales |

**Comando:** el mismo que S-01, cambiando el manifiesto a `escenarios/s_interrupcion.csv` y el run-id a `s-interrupcion`.

**Esperado y observado por etapa:**

| Etapa | Esperado | Observado |
|---|---|---|
| Fallo | Cada frame sin imagen se registra con `estado = error` («imagen ausente»), sin score ni zona y sin inventar confianza. | 30 eventos `error` (`/eventos?run=s-interrupcion&estado=error`). M-04, la tasa de errores, vale **1.000** en w002–w004. |
| Diagnóstico | Las ventanas sin frames puntuados son INSUFICIENTES. `baja-confianza` y `cambio-sostenido` quedan **no evaluables**: no se cierran como normales. | w002, w003 y w004: 0/10 puntuados, suficiente = 0, decisiones `None`. |
| Reacción | Tras 3 ventanas insuficientes seguidas se abre `evidencia-insuficiente-v1` (info), con su acción sugerida. | `s-interrupcion-a001` se abre en w004, vinculada a los 30 eventos sin señal. Tiempo de detección: **5.800 s** desde el frame 20. |
| Recuperación | Con frames válidos, la primera ventana suficiente resuelve la alerta. | En w005 hay 10/10 puntuados y la alerta pasa a **resuelta**. Tiempo de recuperación: 1.828 s desde el frame 50. Tasa de errores en w005–w007: 0.000. |
| Verificación posterior | El recálculo independiente confirma ventanas, zonas, métricas y vínculos. G5 refleja que los eventos sin imagen no son trazables a una imagen de origen. | `recalculo.json`: 60 comprobaciones y 0 fallidas. G5 = 50/80 = **0.625**: los 30 eventos `error` no tienen `image_source_sha256` porque no hubo imagen. Es un efecto esperado y visible, no un dato oculto. |

**Evidencia:**
- `evidencias/escenarios/s-interrupcion/` y 28 capturas. Los frames sin imagen no se pueden capturar.
- Portal: [`F1-graficas-s-interrupcion.png`](../evidencias/extras/portal/F1-graficas-s-interrupcion.png), [`S-ventanas-s-interrupcion.png`](../evidencias/extras/portal/S-ventanas-s-interrupcion.png), [`S-alertas-s-interrupcion.png`](../evidencias/extras/portal/S-alertas-s-interrupcion.png), [`S-eventos-s-interrupcion-error.png`](../evidencias/extras/portal/S-eventos-s-interrupcion-error.png).

**Límite:** la interrupción se simula en la entrada: la fuente emite frames sin imagen, como lo haría una cámara que se desconecta. No se reconecta un socket real. La reacción y la recuperación sí son las del monitor real.
