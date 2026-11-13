# Inventario de métricas G1–G7

Los siete grupos **aplican** (G = 7) y no se excluye ninguno: hay inferencia visual (G1, G2), un proceso local cuyos recursos se pueden medir (G3), salidas puntuadas del modelo (G4), eventos y capturas (G5), una fuente y una versión de modelo identificadas (G6) y alertas persistidas (G7).

Hay **una métrica base por grupo**, y ninguna se usa en dos grupos. Las métricas adicionales están en [`extras.md`](extras.md) y no se cuentan aquí.

## Convenciones comunes (M1–M3)

- **Unidad de análisis:** el **frame** emitido por la fuente. Un evento corresponde a un frame. Las candidatas del detector se guardan, pero no forman el denominador de ninguna métrica base.
- **Ventana:** 10 frames consecutivos del stream (2 s a 5 fps). La última ventana de una corrida puede tener menos frames. Una ventana con menos de 6 frames puntuados es **insuficiente**.
- **Estados:** `ok` (puntuado), `sin_detecciones` (el modelo corrió y no emitió candidatas) y `error` (la imagen no se pudo leer o falló el runtime). Los dos últimos no tienen zona ni score.
- **Cero observaciones o datos ausentes:** cada métrica devuelve `null` («sin datos»), nunca 0. El portal lo muestra como «—».
- **Percentil:** se usa el método de rango más cercano, es decir, el valor ordenado en la posición `ceil(p·n)`.
- **Adquisición (M2):** el propio monitor ([`src/p6/monitor.py`](../src/p6/monitor.py)) registra cada observación primaria en SQLite (`evidencias/monitoreo.db`) y la exporta a `evidencias/escenarios/<run>/` como `eventos.jsonl` (una línea por frame), `ventanas.jsonl` (una por ventana) y `alertas.jsonl`. El resultado agregado está en `run.json → metricas`.
- **Trazabilidad (M4):** cada ventana lista `frame_desde…frame_hasta` y su `window_id`, que también aparece en cada evento. Cada evento lleva `event_id`, `frame_id`, la imagen de origen y su SHA-256.
- **Verificación (M5):** [`src/p6/recalcular.py`](../src/p6/recalcular.py) recalcula todo desde los JSONL y las capturas en disco con fórmulas propias. No usa `p6.metricas` ni la base de datos. Termina con código 1 si algo no coincide, y CI lo ejecuta sobre la evidencia versionada. Se ejecuta así:

```bash
cd Proyecto6
PYTHONPATH=src python -m p6.recalcular --run evidencias/escenarios/c1-normal
```

## Métricas base

| Grupo | Métrica base | Definición (M1) | Instrumentación (M2) | Cálculo (M3) | Primarias (M4) |
|---|---|---|---|---|---|
| **G1** Salud y rendimiento | **Tiempo de inferencia p50/p95** | Duración de `session.run` del modelo ONNX en ms por frame, **sin** lectura, preprocesamiento ni posprocesamiento. Población: frames con inferencia completa (se excluyen los `error`). Se calcula por ventana y por corrida. | `time.perf_counter()` alrededor de `session.run` en [`detector.py`](../src/p6/detector.py) → campo `inferencia_ms` | Percentil de rango más cercano 0.50 y 0.95. Sin frames → `null`. | `eventos.jsonl: inferencia_ms` |
| **G2** Captura y stream | **FPS de procesamiento** | Frames inferidos / (fin del último frame − emisión del primero), en segundos. Inferidos = `ok` + `sin_detecciones`. Se calcula por ventana y por corrida. | Reloj monótono: `t_captura_mono` (emisión de la fuente) y `t_fin_mono` (fin del procesamiento) | Con menos de 2 frames o duración 0 → `null`. | `eventos.jsonl: t_captura_mono, t_fin_mono, inferencia_ms` |
| **G3** Recursos | **RSS del proceso de monitoreo (MiB)** | Memoria residente del proceso Python que ejecuta fuente, modelo y reglas. Una muestra al cierre de cada ventana; en la corrida se reportan el máximo y la media. | `psutil.Process().memory_info().rss / 2**20` | Sin muestras → `null`. | `ventanas.jsonl: rss_mib` |
| **G4** Predicciones | **Proporción de baja confianza** | Frames con s < umbral inferior (0.25) / frames puntuados (`ok`). Se excluyen `sin_detecciones` y `error`, porque no tienen score. Se calcula por ventana y por corrida. **No mide acierto.** | Política en [`politica.py`](../src/p6/politica.py) → `estado`, `score_principal`, `zona` | 0 frames puntuados → `null` (ventana insuficiente). | `eventos.jsonl: estado, score_principal, detecciones[]` |
| **G5** Datos y trazabilidad | **Cobertura de trazabilidad** | Eventos trazables / eventos registrados. Un evento es trazable si tiene `event_id, run_id, frame_id, source_id, t_captura, image_source_sha256, model_sha256, detector_config_sha256, config_sha256, estado, window_id`; si es `ok`, también score y zona; y si declara captura, el archivo existe y su SHA-256 coincide. | Campos de [`monitor.py`](../src/p6/monitor.py) y comprobación del archivo en disco | 0 eventos → `null`. | `eventos.jsonl` + `evidencias/capturas/**` |
| **G6** Fuentes y versiones | **Versión esperada frente a reportada** | Eventos cuyo `model_sha256` reportado coincide con el SHA-256 esperado del descriptor (`c789161e…`) / eventos. También se listan las versiones reportadas. | El detector calcula el SHA-256 de los pesos al cargar y falla si no coincide con `Proyecto5/modelo/descriptor.yaml` | 0 eventos → `null`. | `eventos.jsonl: model_sha256`, `run.json: model_sha256` |
| **G7** Alertas | **Alertas activas** | Alertas abiertas al cierre de cada ventana: abiertas en la ventana ≤ w y no resueltas en una ventana ≤ w. También se reporta el valor al final de la corrida. | Ciclo de vida de alertas en `Monitor._ciclo_alerta` (abrir, mantener, resolver) | Entero ≥ 0. Sin ventanas no se define. | `alertas.jsonl: abierta_ventana, resuelta_ventana` y `ventanas.jsonl: alertas_activas` |

## Resultados (evidencia versionada, commit de código `6184d32`)

| Corrida | G1 p50 / p95 ms | G2 fps | G3 RSS máx MiB | G4 baja | G5 cobertura | G6 | G7 al final (máx) |
|---|---|---|---|---|---|---|---|
| `ref-carrito` (referencia) | 16.38 / 28.88 | 5.106 | 101.8 | 6/41 = 0.146 | 42/42 = 1.000 | 42/42 | 0 (0) |
| `c1-normal` (C1) | 20.38 / 28.47 | 5.121 | 102.0 | 8/24 = 0.333 | 36/36 = 1.000 | 36/36 | 0 (0) |
| `c2-baja-confianza` (C2) | 17.27 / 23.03 | 5.068 | 102.1 | 21/59 = 0.356 | 66/66 = 1.000 | 66/66 | 0 (1, ventana w000) |

Recálculo: `evidencias/escenarios/<run>/recalculo.json`. Hay 41, 35 y 57 comprobaciones con **0 fallidas**.

**Límites:**
- G2 ronda los 5 fps porque la fuente se reproduce a 5 fps declarados. El valor mide el ritmo sostenido, no la capacidad máxima del modelo.
- G3 incluye el intérprete, ONNX Runtime y las librerías cargadas.
- Los tiempos dependen del equipo. Las corridas se hicieron en Linux x86_64 con 2 CPU, Python 3.13 y onnxruntime 1.31.1 en CPU (ver `run.json → entorno`).
