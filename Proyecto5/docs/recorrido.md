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
    --reproducir-cortes \
    --replay-dt-ms 100 \
    --salida resultados/recorrido-real
```

`--replay-dt-ms` vale **100 ms por defecto**. Dentro de cada secuencia y de cada sesión los
cuadros se reproducen en orden a ese intervalo; al cambiar de secuencia se deja un hueco de
`max(max_edad_ms, vencimiento_ms) + replay_dt_ms` (con `config/watchdog.yaml`, 400 ms),
mayor que los plazos del watchdog para que el corte se note y quede un STOP entre
secuencias. Con `--reproducir-cortes`, al cambiar `session_id` dentro de una secuencia se
conserva el delta real de `t_capture_ms` (las pausas de S1, S2 y S3) en lugar de comprimirlo
a 100 ms. El watchdog revisa el vencimiento antes del cuadro siguiente y deja un STOP; no se
inventan cuadros ni se asume vía libre durante el hueco.

El resultado es válido **a 10 cuadros/s dentro de cada sesión y a los cortes reales entre
sesiones**, no a los `t_capture_ms` originales de toda la captura. Sin `--reproducir-cortes`
la corrida es la **cadencia virtual** de 100 ms y `cortes.json` marca los cortes como
comprimidos (`aplicado: false`); esa corrida no debe presentarse como continuidad de captura.

El `t_capture_ms` real no se pierde: sigue en `datos/evaluacion/capturas.csv` y cada evento
lo copia como `t_capture_origen_ms`. El reloj de la ejecución (`t_capture_ms` del evento)
es el de la reproducción. `run.json` declara `replay_dt_ms: 100`; `cortes.json` declara el
modo (`cortes_sesion` o `cadencia_virtual`) y los cortes aplicados o comprimidos.

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

El manifiesto real usa `sequence_id` S1–S6. La regla de IDs es la misma en `p5.recorrer`
y `p5.expectativas`: **conserva** los `frame_id` que ya vienen como `<secuencia>_fNNNN` y
**renumera** los UUID o ids no prefijados por posición en orden de `t_capture_ms`
(`S1_f0001`, `S5_f0001`, …). Los 78 IDs coinciden con la columna
`frame_id_reproductor_P514_cache` de
[`compatibilidad_ids_consumidores_p5_05b.csv`](compatibilidad_ids_consumidores_p5_05b.csv).
S2, S3, S4 y S6 conservan los IDs del CSV con sus huecos; S1 y S5 se renumera por posición.
Ambos casos cumplen `validar_secuencia` (prefijo de la secuencia y sin repetidos).

| Secuencia | Escenario | Cuadros | `frame_id` vigentes |
|---|---|---:|---|
| S1 | Camino despejado (C1) | 12 | `S1_f0001`–`S1_f0012` (posicional) |
| S2 | Obstáculo central (C2) | 17 | `S2_f0007`–`S2_f0023` (conserva hueco inicial) |
| S3 | Obstáculo a la izquierda (C3) | 13 | `S3_f0001`–`S3_f0003`, `S3_f0006`–`S3_f0015` |
| S4 | Obstáculo a la derecha (C4) | 12 | `S4_f0001`, `S4_f0003`–`S4_f0007`, `S4_f0009`–`S4_f0014` |
| S5 | Varios obstáculos sin zona libre (C5) | 12 | `S5_f0001`–`S5_f0012` (posicional) |
| S6 | Despejado → obstáculo → despejado (C7) | 12 | `S6_f0001`–`S6_f0012` |

### Cortes de sesión

El manifiesto trae `session_id` y el `t_capture_ms` real. Con `--reproducir-cortes`, el
reloj de replay conserva las pausas entre sesiones en lugar de comprimirlas a 100 ms:

| Secuencia | Transición | Pausa de origen |
|---|---|---:|
| S1 | `S1_f0009` → `S1_f0010` | 3,623,351 ms |
| S2 | `S2_f0008` → `S2_f0009` | 241,906 ms |
| S2 | `S2_f0016` → `S2_f0017` | 1,992,758 ms |
| S2 | `S2_f0017` → `S2_f0018` | 1,817,039 ms |
| S3 | `S3_f0007` → `S3_f0008` | 674,441 ms |

El watchdog revisa el vencimiento antes del cuadro siguiente y deja un STOP en cada corte;
no se inventan cuadros ni se asume vía libre durante la ausencia de evidencia. Los cortes
aplicados (o comprimidos, en modo virtual) quedan en `cortes.json`. El modo de 100 ms sin
el flag se conserva para pruebas deterministas y se identifica como `cadencia_virtual`.

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
| `cortes.json` | Modo de reproducción (`cortes_sesion` o `cadencia_virtual`), cortes de sesión con frame previo/siguiente, sesiones, delta de origen, delta de replay y `aplicado` |
| `detecciones.jsonl` | Un `PerceptionEvent` por cuadro, en el orden del manifiesto; `t_capture_ms` es el reloj de reproducción y `t_capture_origen_ms` la procedencia real |
| `decisiones.jsonl` | Una `Decision` de la política por evento/tick |
| `comandos.jsonl` | Comandos observados en el adaptador, vinculados por `frame_id` |

El reloj es `RelojControlado` y avanza con el calendario de reproducción; no hay `sleep`.
El watchdog de P5-12 revisa vencimientos entre cuadros y deja STOP cuando corresponde,
incluido el hueco entre secuencias y cada corte de sesión. Al final,
`AdaptadorVirtual.cerrar()` registra el STOP de cierre.

## Inyección de fallo del detector (C9)

El manifiesto puede marcar un cuadro con `status: error` o `status: stale`. Además,
`p5.recorrer` captura cualquier excepción de `Detector.detectar()` y la convierte en un
evento `status: error` con `error_msg`, que termina en STOP seguro. La prueba
`test_detector_que_falla_queda_como_error_y_stop` cubre ese caso.

## Evidencia

- [`docs/evidencia/recorrido-real/`](evidencia/recorrido-real/README.md): corrida sobre
  las 78 capturas reales vigentes en `main` con `DetectorONNX` (#81),
  `--reproducir-cortes` y `--replay-dt-ms 100`; incluye `cortes.json` con los 5 cortes.
- [`docs/evidencia/recorrido/`](evidencia/recorrido/README.md): corrida sintética
  determinista con `DetectorSimulado`, útil para pruebas sin pesos.

## Pendientes

1. Mantener la evidencia sincronizada si cambia el dataset (por ejemplo, otra recaptura)
   o el detector; la corrida actual usa el manifiesto de #79/#84.
2. Documentar los límites del detector real en S2, S3, S4 y S6, donde no siempre ve
   `person`/`dog`/`cat` ≥ 0.50 (limitación reportada en #81).
3. La inyección de fallo real (C9) está cubierta en `recorrido-real/fallo_detector/` con
   un JPEG truncado y enlazada desde [`evidencia/recorrido-real/README.md`](evidencia/recorrido-real/README.md).
