# Proyecto 6 · Centro de monitoreo de computer vision

Portal que convierte un stream visual en inferencias reales, eventos, capturas y alertas explicables con evidencia. **Entrega individual.**

```
fuente (secuencia del carrito @ 5 fps)
   │  frame_id, t_captura, sha256 de la imagen
   ▼
detector YOLOX-Nano ONNX (CPU, piso 0.05, NMS 0.45)    ← reutilizado del Proyecto 5
   │  candidatas: clase, caja, score · tiempos por etapa
   ▼
política 2 umbrales / 3 zonas por frame  ──►  evento (SQLite + JSONL) ──► captura (sin expiración)
   │                                              │
   ▼                                              ▼
ventana de 10 frames ──► reglas (baja confianza, cambio sostenido, evidencia insuficiente)
   │                                              │
   ▼                                              ▼
métricas G1–G7 por ventana y corrida          alertas (abrir / mantener / resolver)
                     └──────────────► portal FastAPI: /eventos  /alertas  /ventanas  /runs
```

## Autoría y procedencia (R7.3)

| | |
|---|---|
| Autor | **Esteban Sánchez** (@sanchezesteban), entrega individual del Proyecto 6 |
| Repositorio | fork de `sebastian0023/Proyecto-3-Clasificador-de-imagenes` (monorepo P1–P5 del equipo); el P6 vive solo en `Proyecto6/` |
| Aportación propia (P6) | Todo `Proyecto6/`: fuente de stream, envoltorio del detector con tiempos por etapa, política de zonas, eventos y persistencia, capturas, ventanas, reglas y ciclo de vida de alertas, métricas G1–G7, recálculo independiente, portal, escenarios, pruebas, CI `.github/workflows/p6-ci.yml` y documentación |
| Reutilizado del P5 (trabajo de equipo) | `Proyecto5/src/p5/detector_onnx.py` (carga y verificación SHA-256, letterbox, decodificación y NMS), `Proyecto5/src/p5/contrato.py` (`Detection`), `Proyecto5/scripts/descargar_modelo.py`, `Proyecto5/modelo/descriptor.yaml` y las 78 capturas de `Proyecto5/datos/evaluacion/` (ESP32-CAM del carrito, consentimiento de publicación en `Proyecto5/docs/autorizaciones_finales_p5_05b.md`). No se modificó nada dentro de `Proyecto5/`. |
| Modelo | **YOLOX-Nano** preentrenado en COCO (80 clases), release `0.1.1rc0` de Megvii-BaseDetection, licencia Apache-2.0, `yolox_nano.onnx` (3 659 407 bytes, SHA-256 `c789161ed43c8269fcd4e67c67eeeb4e80c622da2eb296a20bc6007bd18a0b7d`). Se usa sin entrenar ni ajustar. Se descarga de una URL pública y se verifica (ver Instalación). |
| Asistencia | Diseño y código desarrollados con apoyo de un asistente de IA (Claude); el autor revisó, ejecutó y aprobó cada cambio. |

## Tarea, fuente y modelo (R1)

| | |
|---|---|
| Tarea | **Detección de objetos** (cajas, clase COCO y score por candidata; contexto por frame) |
| Fuente | **Secuencia de imágenes** capturadas por la cámara ESP32-CAM del carrito del P5 (400×296 JPEG), reproducida como stream por [`src/p6/fuente.py`](src/p6/fuente.py) |
| Frecuencia y muestreo | **5 fps declarados**: cada imagen del manifiesto se emite una vez y en orden, cada 200 ms, sin descartes. Si la inferencia se atrasa, el siguiente frame sale de inmediato y el retraso queda en `t_captura`/`t_fin`. Configurado en `config/monitoreo.yaml → fuente` |
| Preprocesamiento | Igual que el P5: RGB → letterbox 416×416 proporcional, pegado arriba a la izquierda, relleno 114 → BGR, NCHW, float32 0–255 sin normalizar |
| Posprocesamiento | Decodificación de la rejilla (strides 8/16/32), `score = objectness × prob_clase`, **piso 0.05**, NMS por clase con IoU 0.45, máximo 100 ([`config/detector.yaml`](config/detector.yaml)) |
| Entorno de las corridas versionadas | Linux x86_64, 2 CPU, Python 3.13.18, onnxruntime 1.31.1 `CPUExecutionProvider` (detalle en cada `run.json → entorno`). CI: Python 3.12 |
| Atribución | Cada evento guarda `model_sha256`, `detector_config_sha256`, `config_sha256`, `synthetic = 0`, las candidatas crudas y los tiempos de `session.run`. No existe un generador de scores en el código de producción. |

¿Por qué no la cámara en vivo? El evaluador no tiene acceso al carrito. Reproducir las capturas reales del carrito permite repetir C1 y C2 en cualquier equipo con las mismas entradas.

## Instalación (R7.1)

Requisitos: Python 3.12 o superior, CPU y red para descargar los pesos públicos. No hace falta GPU, Docker ni AWS.

```bash
git clone https://github.com/sanchezesteban/MLOPS_p6-monitoreo.git
cd MLOPS_p6-monitoreo/Proyecto6
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
# Pesos públicos de YOLOX-Nano: sale con código 1 si el SHA-256 o el tamaño no coinciden
python ../Proyecto5/scripts/descargar_modelo.py --destino ../Proyecto5/modelo/
pytest            # 23+ pruebas; la del modelo real se omite si no hay pesos
ruff check .
```

En PowerShell, en lugar de `PYTHONPATH=src …` usa `$env:PYTHONPATH = "src"` y luego el mismo comando `python -m …`.

## Ver la evidencia versionada en el portal

```bash
PYTHONPATH=src python -m p6.portal --db evidencias/monitoreo.db      # http://127.0.0.1:8060
```

| Ruta | Qué muestra |
|---|---|
| `/runs` | Corridas con commit, modelo, configuración y métricas G1–G7 |
| `/eventos` | Eventos con filtros por corrida, zona y estado. Enlaces a la captura, la ventana y las alertas |
| `/eventos/{id}` | Identidad, imagen de origen y su SHA-256, modelo, estado, score y zona, tiempos, candidatas con su zona, configuración, ventana, alertas y captura |
| `/alertas` | Momento, severidad, regla, motivo, acción sugerida, estado y captura. Filtros por corrida, estado y severidad |
| `/alertas/{id}` | Regla, configuración, ventanas que la sustentan y eventos que la originaron, con sus capturas |
| `/ventanas` | Cada ventana con su estado suficiente o INSUFICIENTE, las decisiones de las 3 reglas y las métricas por ventana |
| `/config/{sha}` | Texto exacto de `monitoreo.yaml` y `detector.yaml` usados |
| `/graficas?run=` | *Extra F-01:* historia del score por frame con umbrales y alertas, proporción por ventana frente a la referencia, métricas adicionales e incidente |
| `/capturas` | *Extra F-02:* galería de capturas conservadas, con filtros |
| `/exportar/eventos.csv` | *Extra F-03:* exportación CSV con los mismos filtros de `/eventos` |

## Reproducir los escenarios

Ejecuta los comandos desde `Proyecto6/` y escribe las corridas nuevas en `var/`, que está ignorada por Git, para no tocar la evidencia:

```bash
export PYTHONPATH=src
python scripts/construir_manifiestos.py           # referencia.csv y c1_normal.csv (ya versionados)
python scripts/preparar_c2.py --destino var/c2 --manifiesto var/c2.csv   # C2 (versionado en datos/)
# Referencia, C1 y C2 (los run_id no deben existir en la base elegida)
python -m p6.monitor --manifiesto escenarios/referencia.csv --escenario REF --run-id ref --db var/m.db --salida var/ref
python -m p6.referencia --run var/ref --config config/monitoreo.yaml --salida var/referencia.json
python -m p6.monitor --manifiesto escenarios/c1_normal.csv --escenario C1 --run-id c1 --db var/m.db --salida var/c1
python -m p6.monitor --manifiesto escenarios/c2_baja_confianza.csv --escenario C2 --run-id c2 --db var/m.db --salida var/c2
python -m p6.recalcular --run var/c2              # recálculo independiente; código 1 si algo no coincide
python -m p6.extras --run var/c2                  # métricas adicionales (extras M)
# Escenarios adicionales (extras S)
python scripts/preparar_extras.py                 # ya versionado: escenarios/s_*.csv y datos/s_sostenido_jpeg5/
python -m p6.monitor --manifiesto escenarios/s_sostenido.csv --escenario S-sostenido --run-id s1 --db var/m.db --salida var/s1
python -m p6.monitor --manifiesto escenarios/s_interrupcion.csv --escenario S-interrupcion --run-id s2 --db var/m.db --salida var/s2
python -m p6.portal --db var/m.db
```

Notas sobre la reproducción:
- **Referencia:** `config/monitoreo.yaml` apunta a la referencia versionada `evidencias/referencia/referencia.json`. Su identidad (modelo, configuración del detector y umbral inferior) es la misma que tendrá una corrida local con los mismos pesos.
- **Variación numérica:** en otra CPU o versión de runtime, las confianzas pueden variar del orden de 1e-6 y los tiempos (G1–G3) cambian.

## Documentación y evidencia

| Documento | Contenido |
|---|---|
| [`evidencias/INDICE.md`](evidencias/INDICE.md) | **Índice**: criterio → archivo, ID, configuración y revisión Git |
| [`docs/metricas.md`](docs/metricas.md) | Inventario G1–G7: aplicabilidad, métrica base, M1–M5 y resultados |
| [`docs/umbrales.md`](docs/umbrales.md) | Zonas, referencia, justificación de umbrales, ventanas y reglas |
| [`docs/escenarios.md`](docs/escenarios.md) | C1 y C2: entrada, comando, esperado, observado y evidencia |
| [`docs/extras.md`](docs/extras.md) | Inventario de adicionales reclamados (F-01–F-03, M-01–M-08, S-01–S-02) |
| [`docs/escenarios_extra.md`](docs/escenarios_extra.md) | Escenarios adicionales: cambio sostenido e interrupción del stream |

## Estructura

```
Proyecto6/
├── config/          monitoreo.yaml (umbrales, ventanas, reglas, captura), detector.yaml
├── src/p6/          fuente, detector, política, métricas, reglas, almacén, monitor,
│                    referencia, recalcular, extras (métricas adicionales),
│                    portal/ (FastAPI + Jinja2 + gráficas SVG)
├── escenarios/      manifiestos de stream (referencia, C1, C2)
├── datos/           entrada preparada de C2 (desenfoque de capturas reales)
├── scripts/         construir_manifiestos.py, preparar_c2.py, preparar_extras.py
├── evidencias/      monitoreo.db, capturas/, escenarios/<run>/, referencia/, portal/, INDICE.md
├── docs/            métricas, umbrales, escenarios, extras
└── tests/           pytest (política, reglas, métricas, fuente, monitor→portal, modelo real)
```

## Límites conocidos

- La fuente es una secuencia reproducida, no la cámara en vivo. El lector MJPEG del P5 (`Proyecto5/scripts/capturar_esp32.py`) no se integró al monitor.
- La confianza de YOLOX-Nano no está calibrada: describe la salida del modelo, no su acierto. No se evalúa calidad predictiva.
- Las capturas y la base viven en el repositorio. No hay expiración, borrado ni TTL; para borrarlas hay que hacerlo manualmente.
- El portal es de solo lectura y no tiene autenticación. Está pensado para uso local (`127.0.0.1`).
