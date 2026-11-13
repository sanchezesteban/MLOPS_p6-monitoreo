# Escenarios base C1 y C2

Ambos escenarios usan el **mismo** modelo (`yolox_nano`, SHA-256 `c789161e…`), la misma configuración del detector (`dc30841a…`), la misma configuración de monitoreo (`p6-config-v1`, `62a273b9…`), la misma referencia (`5d512afc…`) y el mismo commit de código (`6184d32`, árbol limpio: `git_sucio = 0` en `run.json`).

Todas las puntuaciones salen de inferencia real con ONNX Runtime (`synthetic = 0` en cada evento). No se inyecta ni se modifica ningún score.

## C1 · Operación normal

| Elemento | Valor |
|---|---|
| Entrada | [`escenarios/c1_normal.csv`](../escenarios/c1_normal.csv): 36 capturas reales de la ESP32-CAM del carrito (P5, secuencias S1, S4 y S6), con SHA-256 verificado contra el manifiesto. No se usaron para fijar umbrales. |
| Comando | `PYTHONPATH=src python -m p6.monitor --manifiesto escenarios/c1_normal.csv --escenario C1 --run-id c1-normal --db evidencias/monitoreo.db --capturas evidencias/capturas --salida evidencias/escenarios/c1-normal` |
| Esperado | Inferencias reales a ~5 fps, zonas asignadas por la política, eventos persistidos y métricas coherentes. Las alertas solo aparecen si su regla se cumple. |
| Observado | 36 eventos: 24 `ok` (8 aceptada, 8 duda, 8 baja), 12 `sin_detecciones` (10 son de S1, escenas despejadas) y 0 errores. 4 ventanas: w001 y w002 suficientes con proporción baja 0.333 y 0.200, ambas < 0.5. w000 (1 puntuado) y w003 (4 puntuados) son **insuficientes**: se muestran como tales y no se cuentan como normales. **0 alertas**, lo que corresponde a la regla: ninguna ventana suficiente llegó a 0.5, la racha del cambio sostenido no pasó de 1 y nunca hubo 3 ventanas insuficientes seguidas. G1–G7 en [`metricas.md`](metricas.md). |
| Evidencia | [`evidencias/escenarios/c1-normal/`](../evidencias/escenarios/c1-normal/) (`run.json`, `eventos.jsonl`, `ventanas.jsonl`, `alertas.jsonl` vacío, `recalculo.json`); 21 capturas en `evidencias/capturas/c1-normal/`; portal: [`02-eventos-c1.png`](../evidencias/portal/02-eventos-c1.png), [`07-ventanas-c1.png`](../evidencias/portal/07-ventanas-c1.png), [`09-alertas-c1-vacio.png`](../evidencias/portal/09-alertas-c1-vacio.png) |
| Nivel | Reproducido: ejecutado con el modelo identificado y recalculado con 35 comprobaciones y 0 fallidas. |

La proporción baja de C1 (0.333) es mayor que la de la referencia (0.146), pero ninguna ventana suficiente alcanza la condición de alerta. Si se hubiera fabricado un estado saludable, las ventanas insuficientes aparecerían como normales; aquí no ocurre.

## C2 · Baja confianza

| Elemento | Valor |
|---|---|
| Entrada | [`escenarios/c2_baja_confianza.csv`](../escenarios/c2_baja_confianza.csv): 66 imágenes en `datos/c2_desenfoque/`, preparadas por [`scripts/preparar_c2.py`](../scripts/preparar_c2.py) a partir de capturas reales del carrito (S2–S6) con un **desenfoque gaussiano de radio 2 px**, que simula una cámara desenfocada o en movimiento. El manifiesto registra, para cada imagen, el origen, el SHA-256 de origen, la transformación y el SHA-256 resultante. |
| Comando | `python scripts/preparar_c2.py` y luego `PYTHONPATH=src python -m p6.monitor --manifiesto escenarios/c2_baja_confianza.csv --escenario C2 --run-id c2-baja-confianza --db evidencias/monitoreo.db --capturas evidencias/capturas --salida evidencias/escenarios/c2-baja-confianza` |
| Umbrales y ventana | 0.25 / 0.50, ventanas de 10 frames con mínimo de 6 puntuados, y regla `baja-confianza-v1` (proporción ≥ 0.5). Se fijaron antes de esta corrida. |
| Esperado | Frames clasificados en zona baja con score real, capturas y eventos conservados, y la alerta `baja-confianza-v1` abierta en la ventana donde se cumple la condición. |
| Observado | 66 eventos: 59 `ok` (30 aceptada, 8 duda, **21 baja**) y 7 `sin_detecciones`. En la **ventana w000**, 6 de 9 frames puntuados tienen s < 0.25 (proporción **0.667 ≥ 0.5**), lo que abre la alerta **`c2-baja-confianza-a001`** (warning). La alerta queda vinculada a los 6 eventos bajos (`…e00002, e00004, e00005, e00007, e00008, e00009`), con scores de 0.140 a 0.241, a sus capturas y a la configuración. En w001 la proporción baja a 0.375 < 0.5 y la alerta pasa a **resuelta**. Las 21 imágenes en zona baja se conservaron como captura. |
| Evidencia | [`evidencias/escenarios/c2-baja-confianza/`](../evidencias/escenarios/c2-baja-confianza/), `evidencias/capturas/c2-baja-confianza/` (37 capturas); portal: [`03-eventos-c2-zona-baja.png`](../evidencias/portal/03-eventos-c2-zona-baja.png), [`04-evento-c2-baja.png`](../evidencias/portal/04-evento-c2-baja.png), [`05-alertas.png`](../evidencias/portal/05-alertas.png), [`06-alerta-c2.png`](../evidencias/portal/06-alerta-c2.png), [`08-ventanas-c2.png`](../evidencias/portal/08-ventanas-c2.png) |
| Nivel | Reproducido: 57 comprobaciones y 0 fallidas; el recálculo verifica que la ventana de apertura cumple la condición y que los eventos vinculados están en zona baja. |

**Límite observado:**
- **Desenfoque más fuerte:** con radio 3–4 px, o al oscurecer la imagen, YOLOX-Nano tiende a no emitir candidatas (`sin_detecciones`) en lugar de dar puntuaciones bajas. Esos frames no cuentan como baja confianza, por eso se eligió radio 2.
- **Alcance de la alerta:** el efecto es más claro en la secuencia S2 (ventana w000). En el resto de C2 la proporción queda entre 0.2 y 0.375, por debajo de la condición, y la alerta se resolvió según su regla.
- **Cambio sostenido:** C2 **no** acredita un cambio sostenido; la racha llegó como máximo a 1 de 3.
