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

## Estado

Esqueleto inicial de la entrega (P5-02). El README final, con los comandos del detector,
el recorrido completo, los casos C1–C10, las métricas y el benchmark, se cierra en el
issue #68.
