# Evidencia del recorrido integral (P5-14)

Corrida del **4 nov 2026** con commit `d69086e`, detector simulado y los módulos reales
de política (#73), adaptador (#74) y watchdog (#76):

```bash
cd Proyecto5
PYTHONPATH=src python -m p5.recorrer \
    --datos datos/simulacion \
    --config config/politica.yaml \
    --watchdog-config config/watchdog.yaml \
    --replay-dt-ms 100 \
    --salida resultados/recorrido \
    --run-id run-sim-001 \
    --commit d69086e
```

Resultado:

```text
Recorrido run-sim-001: 54 cuadros, 60 decisiones, 61 comandos
```

Archivos:

- `run.json`: `RunHeader` del contrato; incluye commit, hashes de modelo/config/manifiesto,
  runtime, hardware, `virtual_mode=true` y `replay_dt_ms=100`.
- `detecciones.jsonl`: 54 `PerceptionEvent`, uno por cuadro del manifiesto; el tiempo real
  del manifiesto queda en `t_capture_origen_ms` y el de reproducción en `t_capture_ms`.
- `decisiones.jsonl`: 60 decisiones (54 por cuadro + 6 cortes de secuencia).
- `comandos.jsonl`: 61 comandos (54 por cuadro + 6 STOP de corte + STOP de cierre).
- `traza_5_cuadros.txt`: unión por `frame_id` de los primeros cinco cuadros.

## Ritmo de reproducción

Cada secuencia avanza 100 ms por cuadro y entre secuencias se deja un hueco de 400 ms,
mayor que los plazos del watchdog. Por eso cada secuencia arranca con un STOP de watchdog
y la política vuelve a exigir sus cuadros de liberación. El resultado es válido a ese ritmo
de reproducción, no a los `t_capture_ms` originales del manifiesto sintético (que ya venían
espaciados cada 100 ms, pero sin hueco entre secuencias).

## Cobertura de la simulación

| Secuencia | Evidencia |
|---|---|
| `seq01` | Vía libre: FORWARD después de la histéresis inicial |
| `seq02` | Obstáculo central: STOP |
| `seq03` | Obstáculo a la izquierda: STEER_RIGHT |
| `seq04` | Obstáculo a la derecha: STEER_LEFT |
| `seq05` | Tres zonas ocupadas: STOP |
| `seq06` | Obstáculo persistente y reanudación tras tres cuadros despejados |
| `seq00_fallo` | Cuadro `error` y cuadro `stale` al final, ambos con STOP |

## Limitaciones

- El detector es simulado: lee `datos/simulacion/detecciones.yaml` y no abre las imágenes
  ni las anotaciones COCO. La interfaz `p5.detector.Detector` es la misma que implementa
  `DetectorONNX` en la evidencia real.
- Las secuencias son sintéticas; la corrida con las seis secuencias reales de P5-05/P5-06
  está en [`../recorrido-real/`](../recorrido-real/README.md).
- `cuadro.png` es una imagen de relleno de 640×480; el detector simulado no la lee.
