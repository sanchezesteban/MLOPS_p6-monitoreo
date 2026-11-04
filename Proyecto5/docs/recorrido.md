# Recorrido integral con detector real y simulado (P5-14)

El recorrido demuestra la cadena completa:

```text
manifiesto -> detector -> PerceptionEvent -> Watchdog/Politica -> AdaptadorVirtual -> bitacora
```

El detector queda detrás de la interfaz `p5.detector.Detector`:

- `DetectorONNX` (P5-04, #81) es el detector real YOLOX-Nano sobre las capturas de #79 y la recaptura de #84.
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

Después, sobre las capturas reales de #79/#84:

```bash
PYTHONPATH=src python -m p5.recorrer \
    --datos datos/evaluacion \
    --manifiesto datos/evaluacion/capturas.csv \
    --config config/politica.yaml \
    --watchdog-config config/watchdog.yaml \
    --detector real \
    --detector-config config/detector.yaml \
    --replay-dt-ms 100 \
    --salida resultados/recorrido-real
```

`--replay-dt-ms` vale **100 ms por defecto**. Dentro de cada secuencia los cuadros se
reproducen en orden a ese intervalo; al cambiar de secuencia se deja un hueco de
`max(max_edad_ms, vencimiento_ms) + replay_dt_ms` (con `config/watchdog.yaml`, 400 ms),
mayor que los plazos del watchdog para que el corte se note y quede un STOP entre
secuencias. El resultado es válido **a ese ritmo de reproducción (10 cuadros/s)**, no a los
`t_capture_ms` originales, que tienen pausas largas y reinician en cada secuencia.

El `t_capture_ms` real no se pierde: sigue en `datos/evaluacion/capturas.csv` y cada evento
lo copia como `t_capture_origen_ms`. El reloj de la ejecución (`t_capture_ms` del evento)
es el de la reproducción. `run.json` declara `replay_dt_ms: 100`.

La carpeta `--salida` debe ser nueva; el runner no sobrescribe una corrida anterior.

## Uso con el detector simulado

```bash
PYTHONPATH=src python -m p5.recorrer \
    --datos datos/simulacion \
    --config config/politica.yaml \
    --salida resultados/recorrido
```

El detector simulado usa el mismo reproductor: 100 ms por cuadro dentro de cada secuencia
y el hueco entre secuencias descrito arriba.

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

## Secuencias reales S1–S6 (#79 y #84)

El manifiesto real usa `sequence_id` S1–S6. El runner **conserva** los `frame_id` que ya
vienen como `<secuencia>_fNNNN` (por ejemplo `S2_f0007`…`S2_f0023`, porque #84 mantuvo la
numeración original al recortar cuadros) y **renumera** los UUID a `<secuencia>_fNNNN` en el
orden del CSV (`S1_f0001`, `S5_f0001`, …). Ambos casos cumplen `validar_secuencia`
(prefijo de la secuencia y sin repetidos). También conserva el orden del CSV y reproduce
cada secuencia a 100 ms por cuadro con el hueco entre secuencias descrito arriba.

| Secuencia | Escenario | Cuadros |
|---|---|---:|
| S1 | Camino despejado (C1) | 12 |
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
| `run.json` | `RunHeader` del contrato: run_id, commit, hashes de modelo/config/manifiesto, runtime, hardware, modo virtual y `replay_dt_ms` |
| `detecciones.jsonl` | Un `PerceptionEvent` por cuadro, en el orden del manifiesto; `t_capture_ms` es el reloj de reproducción y `t_capture_origen_ms` la procedencia real |
| `decisiones.jsonl` | Una `Decision` de la política por evento/tick |
| `comandos.jsonl` | Comandos observados en el adaptador, vinculados por `frame_id` |

El reloj es `RelojControlado` y avanza con el calendario de reproducción; no hay `sleep`.
El watchdog de P5-12 revisa vencimientos entre cuadros y deja STOP cuando corresponde,
incluido el hueco entre secuencias. Al final, `AdaptadorVirtual.cerrar()` registra el STOP
de cierre.

## Inyección de fallo del detector (C9)

El manifiesto puede marcar un cuadro con `status: error` o `status: stale`. Además,
`p5.recorrer` captura cualquier excepción de `Detector.detectar()` y la convierte en un
evento `status: error` con `error_msg`, que termina en STOP seguro. La prueba
`test_detector_que_falla_queda_como_error_y_stop` cubre ese caso.

## Evidencia

- [`docs/evidencia/recorrido-real/`](evidencia/recorrido-real/README.md): corrida sobre
  las 78 capturas reales vigentes en `main` con `DetectorONNX` (#81) y `--replay-dt-ms 100`.
- [`docs/evidencia/recorrido/`](evidencia/recorrido/README.md): corrida sintética
  determinista con `DetectorSimulado`, útil para pruebas sin pesos.

## Pendientes

1. Mantener la evidencia sincronizada si cambia el dataset (por ejemplo, otra recaptura)
   o el detector; la corrida actual usa el manifiesto de #79/#84.
2. Documentar los límites del detector real en S2, S3, S4 y S6, donde no siempre ve
   `person`/`dog`/`cat` ≥ 0.50 (limitación reportada en #81).
3. La inyección de fallo real (C9) está cubierta en `recorrido-real/fallo_detector/` con
   un JPEG truncado; falta enlazarla desde el cierre de #66.
