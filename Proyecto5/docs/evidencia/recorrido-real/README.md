# Evidencia del recorrido integral con detector real (P5-14)

Corrida del **3 nov 2026** con:

- `DetectorONNX` YOLOX-Nano de P5-04 (#81) y pesos con SHA-256 verificado.
- Capturas reales S1–S6 de P5-05 (#79).
- Política (#73), adaptador (#74) y watchdog (#76) de `main`.
- Commit del runner: `9e80d7b`.

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
    --ritmo-ms 100 \
    --salida resultados/recorrido-real \
    --run-id run-real-001 \
    --commit 9e80d7b
```

Resultado:

```text
Recorrido run-real-001: 84 cuadros, 84 decisiones, 85 comandos
```

- `run.json`: `RunHeader` con `model_sha256=c789161e…`, hash del manifiesto de #79,
  `runtime=yolox_nano: DetectorONNX (CPU)` y `virtual_mode=true`.
- `detecciones.jsonl`: 84 eventos; los `frame_id` se normalizaron a `S1_f0001`,
  `S1_f0002`, …, `S6_f0012` (los UUID de #79 no pasan `validar_secuencia`).
- `decisiones.jsonl`: 84 decisiones.
- `comandos.jsonl`: 85 comandos (84 cuadros + STOP de cierre).
- `resumen_secuencias.json`: acciones y clases detectadas por secuencia.
- `traza_5_cuadros.txt`: unión por `frame_id` de los primeros cinco cuadros.

## Cobertura real

| Secuencia | Acciones observadas | Lectura |
|---|---|---|
| S1 | 16 FORWARD, 2 STOP iniciales | C1, vía libre |
| S2 | 8 STOP, 9 FORWARD | C2 parcial: el detector ve `person`/`dog` en pocos cuadros |
| S3 | 4 STEER_RIGHT, 9 FORWARD | C3, no gira hacia la izquierda ocupada |
| S4 | 4 STEER_LEFT, 8 FORWARD | C4, no gira hacia la derecha ocupada |
| S5 | 12 STOP | C5, tres zonas ocupadas |
| S6 | 2 STOP, 10 FORWARD | C7 parcial: solo dos cuadros con obstáculo detectado |

## Limitaciones conocidas

- **S2 y S6:** el detector real no siempre ve `person`/`dog`/`cat` ≥ 0.50; muchas imágenes
  de pantalla de teléfono salen como `tv` o `traffic light`. Es la limitación que Esteban
  reportó en #81 y afecta la representación de C2/C7. La política ignora esas clases, así
  que no inventa obstáculos, pero tampoco puede frenar lo que no detecta.
- **Ritmo:** los `t_capture_ms` originales de #79 tienen pausas largas y reinician en cada
  secuencia. Para esta evidencia se usó `--ritmo-ms 100` (provisional) hasta que el PM
  confirme el ritmo de reproducción.
- **C9:** el runner convierte excepciones del detector y cuadros `status=error` en STOP
  seguro. La corrida de `fallo_detector/` usa un JPEG real truncado: el detector levanta
  `DetectorError`, el evento sale con `status=error` y el adaptador registra STOP.
- **Hito I1:** esta corrida ya usa una imagen real y el detector real; queda documentar la
  traza de cinco cuadros y los límites anteriores en el PR de #66.
