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
├── resultados/   salidas generadas (no se versionan)
├── mediciones/   benchmark y medición de recursos
├── docs/         documentos, decisiones y evidencias
├── tests/        pruebas con pytest
└── scripts/      herramientas de apoyo
```

## Requisitos

- Python 3.12.
- CPU. Sin cámara, GPIO ni serial: el adaptador es virtual y los motores van desconectados.
- Las versiones exactas están en [`requirements.txt`](requirements.txt), incluidas las
  dependencias indirectas.

## Arranque

```bash
cd Proyecto5
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pytest
ruff check .
```

Las pruebas del contrato no necesitan pesos ni datos: validan los ejemplos de
`config/ejemplos/` y rechazan los mensajes fuera de contrato.

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
PYTHONPATH=src python -m p5.detectar --imagenes <carpeta|archivos...> --config config/detector.yaml --salida <carpeta nueva>
```

En PowerShell: `$env:PYTHONPATH = "src"` y después el mismo `python -m p5.detectar …`.

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

```bash
PYTHONPATH=src python -m p5.casos \
    --casos casos \
    --config config/politica.yaml \
    --control-config config/watchdog.yaml \
    --salida resultados/casos
```

Los casos reales usan `datos/eventos/S1.jsonl` … `S6.jsonl`. La corrida del 4 nov 2026 da
**7/10**; los fallos de C02, C03 y C07 son límites del detector y están explicados en
[`docs/evidencia/casos/`](docs/evidencia/casos/README.md).

## Estado

El detector real, el recorrido integral y los eventos por secuencia están implementados.
La corrida de casos del 4 nov 2026 da **7/10**: C01, C04, C05, C06 y C08–C10 pasan; C02,
C03 y C07 fallan por recall del detector congelado, documentado en
[`docs/evidencia/casos/`](docs/evidencia/casos/README.md) y en
[`docs/detector.md`](docs/detector.md). El recorrido real reproduce los cortes de sesión
de S1, S2 y S3 con `--reproducir-cortes`; la evidencia está en
[`docs/evidencia/recorrido-real/`](docs/evidencia/recorrido-real/README.md).

La fase 2 de P5-06 (#87) ya está integrada. El README final, con el índice E1–E7, las
métricas y el benchmark, se cierra en el issue #68 cuando estén mergeados #59/#60.
