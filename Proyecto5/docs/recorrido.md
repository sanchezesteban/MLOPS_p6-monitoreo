# Recorrido integral con detector real y simulado (P5-14)

El recorrido demuestra la cadena completa:

```text
manifiesto -> detector -> PerceptionEvent -> Watchdog/Politica -> AdaptadorVirtual -> bitacora
```

El detector queda detrás de la interfaz `p5.detector.Detector`:

- `DetectorONNX` (P5-04, #81) es el detector real YOLOX-Nano sobre las capturas de #79.
- `DetectorSimulado` lee un guion de detecciones y **no abre las anotaciones COCO**; sirve
  para probar el runner sin pesos.

`p5.recorrer` elige uno u otro con `--detector`; la cadena de política, adaptador y
watchdog es la misma.

## Uso con el detector real

Primero se descargan los pesos públicos y se verifica su SHA-256:

```bash
cd Proyecto5
PYTHONPATH=src python scripts/descargar_modelo.py --destino modelo/
```

Después, sobre las capturas reales de #79:

```bash
PYTHONPATH=src python -m p5.recorrer \
    --datos datos/evaluacion \
    --manifiesto datos/evaluacion/capturas.csv \
    --config config/politica.yaml \
    --watchdog-config config/watchdog.yaml \
    --detector real \
    --detector-config config/detector.yaml \
    --ritmo-ms 100 \
    --salida resultados/recorrido-real
```

`--ritmo-ms 100` es **provisional** hasta que el PM confirme el ritmo de reproducción:
reproduce un cuadro cada 100 ms en vez de usar los `t_capture_ms` originales, que tienen
pausas largas entre capturas y reinician en cada secuencia. Sin `--ritmo-ms`, el runner
conserva los tiempos originales y separa las secuencias que reinician su reloj.

La carpeta `--salida` debe ser nueva; el runner no sobrescribe una corrida anterior.

## Uso con el detector simulado

```bash
PYTHONPATH=src python -m p5.recorrer \
    --datos datos/simulacion \
    --config config/politica.yaml \
    --salida resultados/recorrido
```

## Datos de simulación

`datos/simulacion/` contiene:

| Archivo | Qué es |
|---|---|
| `manifiesto.csv` | 54 cuadros de 7 secuencias: `seq01`–`seq06` y `seq00_fallo` |
| `detecciones.yaml` | Guion `frame_id -> detecciones`; no son anotaciones COCO |
| `cuadro.png` | Imagen de relleno de 640×480; el detector simulado no la lee |

Las secuencias representan:

| Secuencia | Qué ejercita |
|---|---|
| `seq01` | Vía libre (C1) |
| `seq02` | Obstáculo central en riesgo (C2) |
| `seq03` | Obstáculo solo a la izquierda (C3) |
| `seq04` | Obstáculo solo a la derecha (C4) |
| `seq05` | Obstáculos en las tres zonas (C5) |
| `seq06` | Obstáculo persistente y desaparición con histéresis (C7) |
| `seq00_fallo` | Cuadros vacíos, error del detector y cuadro vencido al final |

## Secuencias reales S1–S6 (#79)

El manifiesto de #79 usa `sequence_id` S1–S6 y `frame_id` con UUID. El runner normaliza
los identificadores a `S1_f0001`, `S1_f0002`, …, `S6_f0012`, que es lo que exige
`validar_secuencia` (prefijo de la secuencia y sin repetidos). También conserva el orden
del CSV y hace monotónica la línea de tiempo global.

| Secuencia | Escenario | Cuadros |
|---|---|---:|
| S1 | Camino despejado (C1) | 18 |
| S2 | Obstáculo central (C2) | 17 |
| S3 | Obstáculo a la izquierda (C3) | 13 |
| S4 | Obstáculo a la derecha (C4) | 12 |
| S5 | Varios obstáculos sin zona libre (C5) | 12 |
| S6 | Despejado → obstáculo → despejado (C7) | 12 |

## Interfaz del detector

```python
class Detector(Protocol):
    nombre: str
    model_sha256: str
    synthetic: bool

    def detectar(self, frame: Frame) -> list[Detection]: ...
```

`DetectorSimulado` implementa esa interfaz leyendo `detecciones.yaml`. Un detector real
debe devolver `p5.contrato.Detection` y declarar el SHA-256 del modelo; `p5.recorrer`
arma el `PerceptionEvent` con el run_id, los hashes y las dimensiones del manifiesto.

## Salidas

| Archivo | Contenido |
|---|---|
| `run.json` | `RunHeader` del contrato: run_id, commit, hashes de modelo/config/manifiesto, runtime, hardware y modo virtual |
| `detecciones.jsonl` | Un `PerceptionEvent` por cuadro, en el orden del manifiesto |
| `decisiones.jsonl` | Una `Decision` de la política por evento/tick |
| `comandos.jsonl` | Comandos observados en el adaptador, vinculados por `frame_id` |

El reloj es `RelojControlado` y avanza con `t_capture_ms`; no hay `sleep`. El watchdog de
P5-12 revisa vencimientos entre cuadros y deja STOP cuando corresponde. Al final,
`AdaptadorVirtual.cerrar()` registra el STOP de cierre.

## Inyección de fallo del detector (C9)

El manifiesto puede marcar un cuadro con `status: error` o `status: stale`. Además,
`p5.recorrer` captura cualquier excepción de `Detector.detectar()` y la convierte en un
evento `status: error` con `error_msg`, que termina en STOP seguro. La prueba
`test_detector_que_falla_queda_como_error_y_stop` cubre ese caso.

## Evidencia

- [`docs/evidencia/recorrido-real/`](evidencia/recorrido-real/README.md): corrida sobre
  las 84 capturas reales de #79 con `DetectorONNX` (#81) y ritmo provisional de 100 ms.
- [`docs/evidencia/recorrido/`](evidencia/recorrido/README.md): corrida sintética
  determinista con `DetectorSimulado`, útil para pruebas sin pesos.

## Pendientes

1. Confirmar con el PM el ritmo de reproducción definitivo; hoy la evidencia usa 100 ms.
2. Documentar los límites del detector real en las secuencias S2 y S6, donde el detector
   no siempre ve `person`/`dog`/`cat` ≥ 0.50 (limitación reportada en #81).
3. La inyección de fallo real (C9) ya está cubierta por `status=error` y por la excepción
   capturada en `p5.recorrer`; falta repetirla sobre una imagen truncada real.
