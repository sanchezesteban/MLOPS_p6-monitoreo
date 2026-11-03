# Evidencia del recorrido integral (P5-14)

Corrida del **3 nov 2026** con commit `e67fa12`, detector simulado y los módulos reales
de política (#73), adaptador (#74) y watchdog (#76):

```bash
cd Proyecto5
PYTHONPATH=src python -m p5.recorrer \
    --datos datos/simulacion \
    --config config/politica.yaml \
    --salida resultados/recorrido \
    --run-id run-sim-001 \
    --commit e67fa12
```

Resultado:

```text
Recorrido run-sim-001: 54 cuadros, 54 decisiones, 55 comandos
```

Archivos:

- `run.json`: `RunHeader` del contrato; incluye commit, hashes de modelo/config/manifiesto,
  runtime, hardware y `virtual_mode=true`.
- `detecciones.jsonl`: 54 `PerceptionEvent`, uno por cuadro del manifiesto.
- `decisiones.jsonl`: 54 decisiones de la política.
- `comandos.jsonl`: 55 comandos del adaptador (54 cuadros + STOP de cierre).
- `traza_5_cuadros.txt`: unión por `frame_id` de los primeros cinco cuadros.

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
  ni las anotaciones COCO. La interfaz `p5.detector.Detector` es la misma que deberá
  implementar el detector real de P5-04 (#56).
- Las secuencias son sintéticas; la corrida con las seis secuencias reales de P5-05/P5-06
  queda pendiente.
- `cuadro.png` es una imagen de relleno de 640×480; el detector simulado no la lee.
