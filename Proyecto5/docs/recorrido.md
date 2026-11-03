# Recorrido integral con detector simulado (P5-14)

El recorrido demuestra la cadena completa:

```text
manifiesto -> detector -> PerceptionEvent -> Watchdog/Politica -> AdaptadorVirtual -> bitacora
```

El detector queda detrás de la interfaz `p5.detector.Detector`; el default es
`DetectorSimulado`, que lee un guion de detecciones y **no abre las anotaciones COCO**.
Cuando el detector real de P5-04 (#56) esté listo, solo tiene que implementar la misma
interfaz y `p5.recorrer` no cambia.

## Uso

```bash
cd Proyecto5
PYTHONPATH=src python -m p5.recorrer \
    --datos datos/simulacion \
    --config config/politica.yaml \
    --salida resultados/recorrido
```

Para una corrida reproducible en evidencia:

```bash
PYTHONPATH=src python -m p5.recorrer \
    --datos datos/simulacion \
    --config config/politica.yaml \
    --salida resultados/recorrido \
    --run-id run-sim-001 \
    --commit "$(git rev-parse --short HEAD)"
```

La carpeta `--salida` debe ser nueva; el runner no sobrescribe una corrida anterior.

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

El detector real deberá producir las detecciones desde las imágenes; el manifiesto y la
interfaz no cambian.

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

[`docs/evidencia/recorrido/`](evidencia/recorrido/README.md) guarda la corrida de
`datos/simulacion/` con `run-sim-001`, el `run.json`, las bitácoras y una traza de cinco
cuadros.

## Pendientes para el detector real

1. Implementar `p5.detector.Detector` con el runtime CPU de P5-04 (#56).
2. Declarar el SHA-256 del modelo y el nombre del runtime en `run.json`.
3. Repetir el recorrido sobre las seis secuencias reales de P5-05/P5-06.
4. Documentar los límites del detector y la inyección de fallo real (C9).
