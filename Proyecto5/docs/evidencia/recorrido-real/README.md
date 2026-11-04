# Evidencia del recorrido integral con detector real (P5-14)

Corrida del **4 nov 2026** con:

- `DetectorONNX` YOLOX-Nano de P5-04 (#81) y pesos con SHA-256 verificado.
- Capturas reales S1–S6 de P5-05 (#79) y recaptura de S2/S3/S4/S6 (#84), selección vigente en `main`.
- Política (#73), adaptador (#74) y watchdog (#76) de `main`.
- Commit del runner: `8b3b9bf`.

```bash
cd Proyecto5
PYTHONPATH=src python scripts/descargar_modelo.py --destino modelo/
PYTHONPATH=src python -m p5.recorrer \
    --datos datos/evaluacion \
    --manifiesto datos/evaluacion/capturas.csv \
    --config config/politica.yaml \
    --watchdog-config config/watchdog.yaml \
    --detector real \
    --detector-config config/detector.yaml \
    --replay-dt-ms 100 \
    --salida resultados/recorrido-real \
    --run-id run-real-001 \
    --commit 8b3b9bf
```

Resultado:

```text
Recorrido run-real-001: 78 cuadros, 83 decisiones, 84 comandos
```

- `run.json`: `RunHeader` con `model_sha256=c789161e…`, hash del manifiesto vigente,
  `runtime=yolox_nano: DetectorONNX (CPU)`, `virtual_mode=true` y `replay_dt_ms=100`.
- `detecciones.jsonl`: 78 eventos; los `frame_id` ya prefijados se conservaron
  (`S2_f0007`…`S2_f0023`) y los UUID de S1/S5 se renumeraron. Todos pasan
  `validar_secuencia`. Cada evento guarda el tiempo real del manifiesto en
  `t_capture_origen_ms`.
- `decisiones.jsonl`: 83 decisiones (78 por cuadro + 5 cortes de secuencia del watchdog).
- `comandos.jsonl`: 84 comandos (78 por cuadro + 5 STOP de corte + STOP de cierre).
- `resumen_secuencias.json`: acciones y clases detectadas por secuencia.
- `traza_5_cuadros.txt`: unión por `frame_id` de los primeros cinco cuadros.

## Ritmo de reproducción

Los cuadros de cada secuencia se reproducen en orden cada **100 ms**
(`--replay-dt-ms 100`). Entre secuencias se deja un hueco de 400 ms
(`max(max_edad_ms, vencimiento_ms) + replay_dt_ms`), mayor que los plazos del watchdog
(300 ms y 250 ms). Por eso cada secuencia arranca con un STOP de watchdog y la política
vuelve a exigir sus cuadros de liberación antes de moverse. El resultado es válido a ese
ritmo de reproducción (10 cuadros/s), no a los `t_capture_ms` originales, que tienen
pausas largas y reinician en cada secuencia.

## Cobertura real

| Secuencia | Acciones observadas | Lectura |
|---|---|---|
| S1 | 10 FORWARD, 2 STOP iniciales | C1, vía libre |
| S2 | 10 STOP, 7 FORWARD | C2 parcial: el detector ve `person` en 4 cuadros y `dog` en 2, con clases espurias |
| S3 | 7 FORWARD, 1 STEER_RIGHT, 5 STOP | C3 parcial: `person` en 4 cuadros; la política no gira hacia la izquierda ocupada |
| S4 | 6 FORWARD, 4 STEER_LEFT, 2 STOP | C4 parcial: `person` en 4 cuadros; la política no gira hacia la derecha ocupada |
| S5 | 12 STOP | C5, tres zonas ocupadas |
| S6 | 10 FORWARD, 2 STOP iniciales | C7 parcial: el detector no produjo `person`/`dog` en esta corrida |

## Fallo real del detector (C9)

`fallo_detector/` repite la corrida sobre un JPEG real truncado:

```text
Recorrido run-fallo-real: 1 cuadros, 1 decisiones, 2 comandos
```

El detector levanta `DetectorError`, el evento sale con `status=error`, la política pasa a
`FALLA` y el adaptador registra STOP. La evidencia incluye `run.json`,
`detecciones.jsonl`, `decisiones.jsonl` y `comandos.jsonl` de esa corrida.

## Limitaciones conocidas

- **S2, S3, S4 y S6:** el detector real no siempre ve `person`/`dog`/`cat` ≥ 0.50. En S2,
  S3 y S4 aparece `person` en cuatro cuadros; en S6 no apareció ninguna detección de
  `person`/`dog`. También hay clases espurias (`kite`, `toilet`, `fire hydrant`, `oven`,
  etc.). La política ignora esas clases, así que no inventa obstáculos, pero tampoco puede
  frenar lo que no detecta. C2 y C7 quedan parciales.
- **S5** conserva el protocolo anterior con estímulos en pantalla de teléfono; por eso el
  detector produce `tv` además de `person`/`cat`/`dog`.
- **Arranque de secuencia:** el hueco entre secuencias fuerza un STOP de watchdog; las
  primeras dos decisiones de cada secuencia son STOP por la histéresis de la política.
- **Hito I1:** la corrida usa imágenes reales y el detector real; la traza de cinco cuadros
  y los límites de S2/S6 quedan documentados aquí y en `docs/recorrido.md`.
