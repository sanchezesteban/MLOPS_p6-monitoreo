# Proyecto 5: percepción y control de un vehículo autónomo a escala

Contrato único entre percepción (grupo A) y control (grupo B): el grupo A publica un
evento por cuadro y el grupo B responde con un comando para el adaptador. El contrato
completo, los esquemas y los ejemplos viven en [`config/contrato_v1.md`](config/contrato_v1.md).

## Equipo

| Integrante | Grupo | PM | Responsabilidad |
|---|---|---|---|
| Edith (@edithflor) | A | Sebastián | A1: detector preentrenado, runtime CPU y límites conocidos |
| Emilio (@Danieltlacuache) | A | Sebastián | A2: secuencias y anotaciones |
| Bryan (@BryanRomoG) | A | Sebastián | A3: métricas y benchmark + captura con el auto |
| Ikram (@ikramzaldivar) | B | Esteban | B1: política temporal y expectativas C1–C7 |
| Juan Pablo (@jpdelmuro) | B | Esteban | B2: adaptador virtual, watchdog y emergencia |
| Uriel (@urielpinag) | B | Esteban | B3: contrato lado B, runner de casos, recorrido y entrega |
| Sebastián (@sebastian0023) | A | PM A | Revisión y aprobación del grupo A |
| Esteban (@sanchezesteban) | B | PM B | Revisión y aprobación del grupo B |

## Estructura

```
Proyecto5/
├── modelo/       pesos ONNX por enlace con SHA-256 (no en Git) y notas del detector
├── config/       contrato v1, JSON Schema y ejemplos
├── datos/        secuencias capturadas y manifiestos
├── src/p5/       contrato, política, adaptador, runner y recorrido
├── casos/        casos C01–C10 en YAML
├── resultados/   salidas generadas; se versiona el informe definitivo de métricas
├── mediciones/   benchmark y medición de recursos; se versiona la corrida real
├── docs/         documentos, decisiones y evidencias
├── tests/        pruebas con pytest
└── scripts/      herramientas de apoyo
```

## Requisitos

- Python 3.12.
- CPU. Sin cámara, GPIO ni serial: el adaptador es virtual y los motores van desconectados.
- Las versiones exactas están en [`requirements.txt`](requirements.txt), incluidas las
  dependencias indirectas.

## Versión de entrega

Tag anotado `p5-entrega` (#70); el commit de entrega es el del tag. Python 3.12, CPU,
modo virtual y motores desconectados.

## Arranque

```bash
cd Proyecto5
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt -r requirements-capturas.txt
pytest
ruff check .
ruff format --check .
```

`requirements-capturas.txt` aporta OpenCV para las pruebas y scripts de captura.
`requirements-datos.txt` solo hace falta para el conteo informativo de casi duplicados
por pHash de P5-06. Las pruebas del contrato no necesitan pesos ni datos: validan los
ejemplos de `config/ejemplos/` y rechazan los mensajes fuera de contrato.

## Pesos del detector

YOLOX-Nano preentrenado en COCO (Apache-2.0), en ONNX para CPU. URL pública, versión,
tamaño, SHA-256, licencia y clases en [`modelo/descriptor.yaml`](modelo/descriptor.yaml).
Los pesos no van en Git; se descargan sin credenciales:

```bash
python scripts/descargar_modelo.py --destino modelo/
```

Sale con código 1 y no deja archivo si el SHA-256 o el tamaño no coinciden.

## Inferencia por imagen

Detector real en CPU sobre imágenes o carpetas elegidas (recorre subcarpetas). Escribe
`run.json` y `detecciones.jsonl` (un evento del contrato v1 por imagen) en una carpeta nueva.
Se corre desde `Proyecto5/` con `src` en `PYTHONPATH` (el paquete `p5` no se instala; sin
esto sale `No module named 'p5'`):

```bash
PYTHONPATH=src python -m p5.detectar \
    --imagenes datos/evaluacion/S1 \
    --config config/detector.yaml \
    --salida resultados/inferencia_s1
```

Cambia `datos/evaluacion/S1` por la carpeta o los archivos que quieras; la salida debe ser
una carpeta nueva. En PowerShell: `$env:PYTHONPATH = "src"` y después el mismo
`python -m p5.detectar …`.

Una imagen sin objetos sale con `status=ok` y `detections=[]`; una ilegible, con
`status=error`. Preprocesamiento, umbral (0.30) y NMS (0.45) en
[`config/detector.yaml`](config/detector.yaml) y en `src/p5/detector_onnx.py`.

Origen, licencia, clases, transformaciones, congelado, resultados en S2/S6 y límites
conocidos del detector: [`docs/detector.md`](docs/detector.md).

## Recorrido integral

Sobre las 78 capturas reales, con el detector en CPU y los cortes de sesión de S1/S2/S3:

```bash
PYTHONPATH=src python -m p5.recorrer \
    --datos datos/evaluacion \
    --manifiesto datos/evaluacion/capturas.csv \
    --config config/politica.yaml \
    --watchdog-config config/watchdog.yaml \
    --detector real \
    --detector-config config/detector.yaml \
    --reproducir-cortes \
    --replay-dt-ms 100 \
    --salida resultados/recorrido
```

La salida debe ser una carpeta nueva. Escribe `run.json`, `cortes.json`,
`detecciones.jsonl`, `decisiones.jsonl` y `comandos.jsonl`. Detalle del reloj y de los
cortes en [`docs/recorrido.md`](docs/recorrido.md).

## Casos C01–C10

Los eventos versionados están en `datos/eventos/S1.jsonl` … `S6.jsonl`. Para regenerarlos
con la corrida de «Recorrido integral»:

```bash
PYTHONPATH=src python scripts/exportar_eventos.py \
    --detecciones resultados/recorrido/detecciones.jsonl \
    --run resultados/recorrido/run.json \
    --cortes resultados/recorrido/cortes.json \
    --salida resultados/eventos
```

Para que el runner los use, en una copia: `--salida datos/eventos --force`:

```bash
PYTHONPATH=src python scripts/exportar_eventos.py \
    --detecciones resultados/recorrido/detecciones.jsonl \
    --run resultados/recorrido/run.json \
    --cortes resultados/recorrido/cortes.json \
    --salida datos/eventos --force
```

Límite: al regenerar en otra máquina, el `run_id` cambia y las confianzas pueden variar del
orden de 1e-6 (runtime/CPU), por eso el contenido difiere de los `datos/eventos/*.jsonl`
versionados; no es un error del detector ni de la política.

El script valida cada evento, exige un `run_id`, `frame_id` canónico y tiempos crecientes.
Si el contenido de un archivo que ya existe en la salida cambia, falla salvo `--force`. Por
eso el primer comando escribe en `resultados/eventos/`, que no está versionado, y verifica
sin tocar la evidencia; `--force` sobre `datos/eventos/` solo se usa en la copia. Después, el
runner, que lee `datos/eventos/`:

```bash
PYTHONPATH=src python -m p5.casos \
    --casos casos \
    --config config/politica.yaml \
    --control-config config/watchdog.yaml \
    --salida resultados/casos
```

La corrida del 4 nov 2026 da **7/10**; los fallos de C02, C03 y C07 son límites del
detector y están explicados en [`docs/evidencia/casos/`](docs/evidencia/casos/README.md).

## Métricas de detección (P5-07)

Calcula TP/FP/FN, Precision/Recall/F1 y soporte por clase y micro sobre todos los
cuadros, incluidos negativos, errores y omisiones. No abre imágenes, pesos ni hardware.
Detalle y casos calculados a mano: [`docs/metricas.md`](docs/metricas.md).

Requiere una corrida de la sección «Recorrido integral». Desde `Proyecto5`:

```bash
PYTHONPATH=src python -m p5.metricas \
    --gt datos/anotaciones.json \
    --pred resultados/recorrido/detecciones.jsonl \
    --manifiesto datos/manifiesto.csv \
    --iou 0.50 \
    --cuadros-esperados 78 \
    --salida resultados/metricas_reproduccion
```

La carpeta de salida debe ser nueva. La evaluación definitiva de los 78 cuadros
(20 negativos, IoU 0.50) está en
[`resultados/metricas/metricas.json`](resultados/metricas/metricas.json):
**TP=42, FP=4, FN=40; Precision micro=0.913043, Recall=0.512195, F1=0.656250**.
[Guía y comandos de Windows](docs/metricas.md),
[validación](docs/evidencia/p5-07-validacion.md).

## Benchmark por etapas (P5-08)

Mide preprocesamiento, inferencia, posprocesamiento y política + adaptador con
10 calentamientos excluidos y 100 mediciones válidas. No incluye red, cámara ni
frenado físico. Detalle y protocolo: [`docs/benchmark.md`](docs/benchmark.md).

Desde `Proyecto5`:

```bash
PYTHONPATH=src python -m p5.benchmark \
    --modo real \
    --imagen datos/evaluacion/S2/S2_0000058828_S2_f0008.jpg \
    --calentamientos 10 \
    --ejecuciones 100 \
    --salida mediciones/reproduccion_p5_08
```

La carpeta de salida debe ser nueva. La evidencia real está en
[`mediciones/real_cpu_predeterminado_20261104T232545932025Z/`](mediciones/real_cpu_predeterminado_20261104T232545932025Z/):
p50=15.868 ms, p95=19.196 ms, máximo=22.059 ms; p95 y máximo quedan por debajo de
100 y 250 ms. [Validación](docs/evidencia/p5-08-validacion.md).

## Entradas, etiquetas y expectativas

- Entradas de inferencia: `datos/evaluacion/capturas.csv` y los JPEG de `datos/evaluacion/`.
  El detector solo recibe la imagen y el manifiesto; no lee etiquetas. `capturas.csv`
  incluye `scene_label` y `outside_risk`, que el recorrido no lee (ver `docs/datos.md`).
- Verdad de referencia: `datos/anotaciones.json` y `datos/manifiesto.csv`; no se usan en
  inferencia, recorrido ni política.
- Expectativas de casos: `casos/expectativas/`; el runner las lee solo al final para
  comparar y nunca se pasan a la política ni al detector.

Ningún módulo de inferencia, política o control importa `p5.datos` ni `p5.expectativas`.

## Estado

El detector real, el recorrido integral y los eventos por secuencia están implementados.
La corrida de casos del 4 nov 2026 da **7/10**: C01, C04, C05, C06 y C08–C10 pasan; C02,
C03 y C07 fallan por recall del detector congelado, documentado en
[`docs/evidencia/casos/`](docs/evidencia/casos/README.md) y en
[`docs/detector.md`](docs/detector.md). El recorrido real reproduce los cortes de sesión
de S1, S2 y S3 con `--reproducir-cortes`; la evidencia está en
[`docs/evidencia/recorrido-real/`](docs/evidencia/recorrido-real/README.md).

Índice E1–E7:

| ID | Rúbrica | Dónde |
|---|---|---|
| E1 | Repo, README, versiones e instalación | [`README.md`](README.md), [`requirements.txt`](requirements.txt) |
| E2 | Detector | [`modelo/descriptor.yaml`](modelo/descriptor.yaml), [`scripts/descargar_modelo.py`](scripts/descargar_modelo.py), [`config/detector.yaml`](config/detector.yaml), [`src/p5/detector_onnx.py`](src/p5/detector_onnx.py), [`docs/detector.md`](docs/detector.md) |
| E3 | Secuencias etiquetadas | [`datos/`](datos/), [`docs/datos.md`](docs/datos.md), [`docs/conteo_datos.md`](docs/conteo_datos.md) |
| E4 | Política y adaptador | [`config/contrato_v1.md`](config/contrato_v1.md), [`config/politica.yaml`](config/politica.yaml), [`config/watchdog.yaml`](config/watchdog.yaml), [`docs/politica.md`](docs/politica.md), [`docs/watchdog.md`](docs/watchdog.md), [`docs/mapeo_actuacion.md`](docs/mapeo_actuacion.md) |
| E5 | Diez casos | [`casos/`](casos/), [`docs/casos.md`](docs/casos.md), [`docs/evidencia/casos/`](docs/evidencia/casos/README.md) |
| E6 | Resultados primarios y métricas | [`docs/evidencia/recorrido-real/`](docs/evidencia/recorrido-real/README.md), [`datos/eventos/`](datos/eventos/README.md), [`docs/metricas.md`](docs/metricas.md), [`resultados/metricas/metricas.json`](resultados/metricas/metricas.json), [métricas del #59](https://github.com/sebastian0023/Proyecto-3-Clasificador-de-imagenes/issues/59) |
| E7 | Benchmark y límites | [#60](https://github.com/sebastian0023/Proyecto-3-Clasificador-de-imagenes/issues/60), [`docs/benchmark.md`](docs/benchmark.md), [`mediciones/real_cpu_predeterminado_20261104T232545932025Z/`](mediciones/real_cpu_predeterminado_20261104T232545932025Z/), [`docs/detector.md`](docs/detector.md) §6, [`docs/recorrido.md`](docs/recorrido.md) |
