# Índice de evidencias · Proyecto 6

- **Estudiante:** Esteban Sánchez (@sanchezesteban). Entrega individual.
- **Repositorio:** https://github.com/sanchezesteban/MLOPS_p6-monitoreo

## Revisiones Git

| Revisión | Contenido |
|---|---|
| `6184d32` | **Código y configuración ejecutados** en las corridas `ref-carrito`, `c1-normal` y `c2-baja-confianza`. Cada `run.json` registra `git_commit = 6184d32a8e96…` y `git_sucio = 0`, es decir, `src/` y `config/` sin cambios locales. |
| commits posteriores en la misma rama o PR | Solo agregan esta evidencia y la documentación; no cambian `src/` ni `config/` de las corridas base. Los extras agregan código **nuevo** en PRs aparte, y sus corridas registran su propio commit. |
| `4bb00ad` (PR P6-02) | Commit ejecutado en las corridas **extra** `s-sostenido` y `s-interrupcion`. Solo agrega entradas (`scripts/preparar_extras.py`, `escenarios/s_*.csv`, `datos/s_sostenido_jpeg5/`); `src/` y `config/` son idénticos a `6184d32`, así que `config_sha256` es el mismo. |
| commits posteriores de P6-02 | Agregan funciones **nuevas** que no usa el monitor: `src/p6/extras.py` (métricas M-01 a M-08, calculadas fuera de línea desde los JSONL) y las rutas `/graficas`, `/capturas` y `/exportar` del portal. Además agregan sus pruebas, las capturas y la documentación. No cambian `fuente`, `detector`, `politica`, `reglas`, `almacen` ni `monitor`, que se pueden comparar con `git diff 6184d32 -- Proyecto6/src/p6/{fuente,detector,politica,metricas,reglas,almacen,monitor}.py`. |

Para comprobar que el código de las corridas base no cambió, ejecuta `git diff 6184d32 -- Proyecto6/config`, que no debe mostrar diferencias. Las funciones que usan las corridas base están en `src/p6/{fuente,detector,politica,metricas,reglas,almacen,monitor}.py`.

## Identidades usadas en todas las corridas base

| Elemento | Valor |
|---|---|
| Modelo | `yolox_nano.onnx`, SHA-256 `c789161ed43c8269fcd4e67c67eeeb4e80c622da2eb296a20bc6007bd18a0b7d` |
| Configuración del detector | `config/detector.yaml`, SHA-256 `dc30841a05248e78a06cc74c4e57421c57bb33ce9f9919e56d40c25809e7c81b` |
| Configuración de monitoreo | `config/monitoreo.yaml` (`p6-config-v1`), SHA-256 `62a273b92cf80252791602df8da8a315107bfe756a8e1cdf8f11f2593e07da4c` |
| Referencia | `evidencias/referencia/referencia.json`, SHA-256 `5d512afca6d72e28f2c08783af5d66ce3bc58a082a9b5813ed63929d39c929c5` (la usan C1 y C2) |
| Base del portal | `evidencias/monitoreo.db` (SQLite; tablas `runs`, `configs`, `eventos`, `ventanas`, `alertas`, `alerta_eventos`) |

## Criterio → evidencia

| Criterio | Evidencia principal | Cómo verificar |
|---|---|---|
| R1.1 Fuente como stream | `src/p6/fuente.py`, `config/monitoreo.yaml → fuente` (5 fps), `escenarios/*.csv`; `t_captura` y `t_captura_mono` en `eventos.jsonl` | G2 ≈ 5.1 fps en cada `run.json`; `tests/test_fuente.py` |
| R1.2 Inferencia real | `src/p6/detector.py` → `Proyecto5/src/p5/detector_onnx.py`; `detecciones[]` crudas, `inferencia_ms`, `model_sha256` y `synthetic = 0` en cada evento | `tests/test_modelo_real.py`; volver a correr C1 y comparar los scores (±1e-6) |
| R1.3 Identidad del modelo | `README.md` (Tarea, fuente y modelo), `Proyecto5/modelo/descriptor.yaml`, `config/detector.yaml`, `run.json → entorno` | `descargar_modelo.py` verifica el SHA-256 |
| R2 Métricas G1–G7 | `docs/metricas.md`, `run.json → metricas`, `ventanas.jsonl`, `eventos.jsonl` | `python -m p6.recalcular --run evidencias/escenarios/<run>` → `recalculo.json` (0 fallidas) |
| R3.1 Umbrales justificados | `docs/umbrales.md`, `evidencias/referencia/referencia.json` (cuantiles y scores ordenados) | 6 de 41 frames < 0.25 en `ref-carrito/eventos.jsonl` |
| R3.2 Tres zonas y estados aparte | `src/p6/politica.py`; `zona` por frame y por candidata; `sin_detecciones` y `error` sin score | `tests/test_politica_metricas.py`; `/eventos?zona=baja` |
| R3.3 Referencia, ventanas y regla sostenida | `referencia.json`, `config/monitoreo.yaml → ventanas, reglas.cambio_sostenido`, `src/p6/reglas.py`; ventanas INSUFICIENTES en `ventanas.jsonl` | `tests/test_reglas.py`; `/ventanas` |
| R4.1 Campos del evento | `eventos.jsonl` (ver la correspondencia abajo) | `/eventos/c2-baja-confianza-e00002` |
| R4.2 Persistencia y consulta | `monitoreo.db`, portal `/eventos` y `/eventos/{id}` | `portal/02-…`, `03-…`, `04-….png`; `tests/test_monitor_portal.py` |
| R4.3 Capturas sin expiración | `evidencias/capturas/<run>/` (86 archivos), política en `config/monitoreo.yaml → captura`; `image_ref` e `image_sha256` en cada evento capturado | `recalculo.json → capturas` (23/23, 21/21, 37/37 resuelven con su SHA-256) |
| R5.1 Reglas explícitas | `config/monitoreo.yaml → reglas`, `docs/umbrales.md`, `src/p6/reglas.py` | `tests/test_reglas.py` |
| R5.2 Alerta desde observaciones reales | `c2-baja-confianza/alertas.jsonl` (`c2-baja-confianza-a001`: ventana w000, 6 `event_ids`, `config_sha256`) | `recalculo.json`: ventana de apertura cumple y eventos en zona baja |
| R5.3 Alertas en el portal | `/alertas` y `/alertas/{id}` con momento, motivo, severidad y acción sugerida | `portal/05-alertas.png`, `06-alerta-c2.png` |
| R6.1 C1 | `docs/escenarios.md#c1`, `evidencias/escenarios/c1-normal/` | Ver C1 en `docs/escenarios.md` |
| R6.2 C2 | `docs/escenarios.md#c2`, `evidencias/escenarios/c2-baja-confianza/`, `datos/c2_desenfoque/` | Ver C2 en `docs/escenarios.md` |
| R7.1 Reproducibilidad | `README.md`, `requirements.txt`, `.github/workflows/p6-ci.yml` | CI: ruff, pytest y recálculo |
| R7.2 Evidencias | Este índice; [`reproduccion/README.md`](reproduccion/README.md) (C1 y C2 reproducidos desde un clon limpio: scores idénticos, mismas zonas y alertas) | `scripts/comparar_corridas.py`; CI (`P6 CI`) ejecuta `p6.recalcular` sobre cada corrida versionada en Python 3.12 |
| R7.3 Autoría y procedencia | `README.md → Autoría y procedencia` | — |
| Extras | [`docs/extras.md`](../docs/extras.md) (inventario F-01–F-03, M-01–M-08, S-01–S-02) y [`docs/escenarios_extra.md`](../docs/escenarios_extra.md) | `evidencias/escenarios/<run>/metricas_extra.json`, `evidencias/escenarios/s-*/`, `evidencias/extras/portal/*.png`, `tests/test_extras.py` |

## Correspondencia del evento con la guía (R4.1)

| Guía | Este proyecto |
|---|---|
| `event_id`, `run_id`, `frame_id`, `timestamp` | `event_id`, `run_id`, `frame_id`, `t_captura` (más `t_fin`) |
| `source_id`, `task` | `source_id` (`carrito-p5-esp32cam`), `task = detection` |
| `model_ref` | `model_nombre` + `model_sha256` (+ `detector_config_sha256`) |
| `status` | `estado` (`ok`, `sin_detecciones`, `error`) + `error_msg` |
| `prediction` | `detecciones[]` (clase, `class_id`, score, caja xyxy, zona) + `score_principal` y `clase_principal` |
| `confidence_zone` | `zona` (`aceptada`, `duda`, `baja`; `null` en los estados aparte) |
| `config_ref` | `config_sha256` (texto en la tabla `configs` y en `/config/{sha}`) |
| `image_ref` | `image_ref` + `image_sha256` + `captura_motivo`; origen en `image_source` + `image_source_sha256` |

## Cadena de una muestra: imagen → modelo → evento → captura → alerta

1. **Imagen de origen:** `Proyecto6/datos/c2_desenfoque/c2_S2_0000300734_S2_f0009.jpg`, con SHA-256 `69a2792b…`. Se obtiene desenfocando `Proyecto5/datos/evaluacion/S2/S2_0000300734_S2_f0009.jpg` (fila 4 de `escenarios/c2_baja_confianza.csv`).
2. **Frame:** el stream la emite como `carrito-p5-esp32cam-f00002` de la corrida `c2-baja-confianza`.
3. **Salida del modelo:** candidata principal `cat` con score 0.2265 → zona **baja** (0.2265 < 0.25). El evento es `c2-baja-confianza-e00002`.
4. **Captura:** `evidencias/capturas/c2-baja-confianza/carrito-p5-esp32cam-f00002.jpg`, guardada con motivo «zona baja» y el mismo SHA-256 que la imagen inferida.
5. **Ventana:** el evento cae en `c2-baja-confianza-w000`, con 6 de 9 frames bajos (0.667).
6. **Alerta:** se abre `c2-baja-confianza-a001` con la regla `baja-confianza-v1`; queda vinculada a e00002 y a otros 5 eventos, con la configuración `62a273b9…`.
7. **Portal:** el recorrido se ve en `portal/06-alerta-c2.png` y `portal/04-evento-c2-baja.png`.

## Corridas exploratorias

Durante el desarrollo hubo corridas exploratorias, por ejemplo para elegir la degradación de C2 y el tamaño de ventana. Se hicieron en bases temporales y **no forman parte de esta evidencia**. Las únicas corridas evaluables son las que están en `monitoreo.db` y en `evidencias/escenarios/`.
