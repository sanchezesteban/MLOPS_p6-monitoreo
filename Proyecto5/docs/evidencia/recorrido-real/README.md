# Evidencia del recorrido integral con detector real (P5-14)

Corrida del **4 nov 2026** con:

- `DetectorONNX` YOLOX-Nano de P5-04 (#81) y pesos con SHA-256 verificado.
- Capturas reales S1–S6 de P5-05 (#79), selección vigente en `main`.
- Política (#73), adaptador (#74) y watchdog (#76) de `main`.
- Commit del runner: `d69086e`.

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
    --commit d69086e
```

Resultado:

```text
Recorrido run-real-001: 78 cuadros, 83 decisiones, 84 comandos
```

- `run.json`: `RunHeader` con `model_sha256=c789161e…`, hash del manifiesto de #79,
  `runtime=yolox_nano: DetectorONNX (CPU)`, `virtual_mode=true` y `replay_dt_ms=100`.
- `detecciones.jsonl`: 78 eventos; los `frame_id` se normalizaron a `S1_f0001`,
  `S1_f0002`, …, `S6_f0012` (los UUID de #79 no pasan `validar_secuencia`). Cada evento
  guarda el tiempo real del manifiesto en `t_capture_origen_ms`.
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
| S2 | 8 STOP, 9 FORWARD | C2 parcial: el detector ve `person`/`dog` en pocos cuadros |
| S3 | 9 FORWARD, 2 STEER_RIGHT, 2 STOP iniciales | C3, no gira hacia la izquierda ocupada |
| S4 | 7 FORWARD, 3 STEER_LEFT, 2 STOP iniciales | C4, no gira hacia la derecha ocupada |
| S5 | 12 STOP | C5, tres zonas ocupadas |
| S6 | 10 FORWARD, 2 STOP iniciales | C7 parcial: solo dos cuadros con obstáculo detectado |

## Fallo real del detector (C9)

`fallo_detector/` repite la corrida sobre un JPEG real truncado:

```text
Recorrido run-fallo-real: 1 cuadros, 1 decisiones, 2 comandos
```

El detector levanta `DetectorError`, el evento sale con `status=error`, la política pasa a
`FALLA` y el adaptador registra STOP. La evidencia incluye `run.json`,
`detecciones.jsonl`, `decisiones.jsonl` y `comandos.jsonl` de esa corrida.

## Limitaciones conocidas

- **S2 y S6:** el detector real no siempre ve `person`/`dog`/`cat` ≥ 0.50; muchas imágenes
  de pantalla de teléfono salen como `tv` o `traffic light`. Es la limitación que Esteban
  reportó en #81 y afecta la representación de C2/C7. La política ignora esas clases, así
  que no inventa obstáculos, pero tampoco puede frenar lo que no detecta.
- **Arranque de secuencia:** el hueco entre secuencias fuerza un STOP de watchdog; las
  primeras dos decisiones de cada secuencia son STOP por la histéresis de la política.
- **Hito I1:** la corrida usa imágenes reales y el detector real; la traza de cinco cuadros
  y los límites de S2/S6 quedan documentados aquí y en `docs/recorrido.md`.
