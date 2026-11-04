# Evidencia del recorrido integral con detector real (P5-14)

Corrida del **4 nov 2026** con:

- `DetectorONNX` YOLOX-Nano de P5-04 (#81) y pesos con SHA-256 verificado.
- Capturas reales S1–S6 de P5-05 (#79) y recaptura de S2/S3/S4/S6 (#84), selección vigente en `main`.
- Política (#73), adaptador (#74) y watchdog (#76) de `main`.
- `--reproducir-cortes`: dentro de cada sesión 100 ms por cuadro y, al cambiar `session_id`, el delta real de `t_capture_ms`. Los 5 cortes quedan en `cortes.json`.
- Commit del código del recorrido: `51d96ed` (incluye #75 y #85 mergeados).

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
    --reproducir-cortes \
    --replay-dt-ms 100 \
    --salida resultados/recorrido-real \
    --run-id run-eventos-001 \
    --commit 51d96ed
```

Resultado:

```text
Recorrido run-eventos-001: 78 cuadros, 88 decisiones, 89 comandos
Cortes de sesion: 5 (cortes_sesion)
```

- `run.json`: `RunHeader` con `model_sha256=c789161e…`, hash del manifiesto vigente,
  `runtime=yolox_nano: DetectorONNX (CPU)`, `virtual_mode=true` y `replay_dt_ms=100`.
- `cortes.json`: modo `cortes_sesion`, 5 cortes aplicados y sus deltas de origen/replay.
- `detecciones.jsonl`: 78 eventos; los `frame_id` ya prefijados se conservaron
  (`S2_f0007`…`S2_f0023`, y los huecos de S3/S4) y los UUID de S1/S5 se renumeraron.
  Todos pasan `validar_secuencia`. Cada evento guarda el tiempo real del manifiesto en
  `t_capture_origen_ms`.
- `decisiones.jsonl`: 88 decisiones (78 por cuadro + 5 cortes de secuencia + 5 cortes de
  sesión del watchdog).
- `comandos.jsonl`: 89 comandos (78 por cuadro + 5 STOP de corte de secuencia + 5 STOP de
  corte de sesión + STOP de cierre).
- `resumen_secuencias.json`: acciones y clases detectadas por secuencia.
- `traza_5_cuadros.txt`: unión por `frame_id` de los primeros cinco cuadros de S1; no
  incluye ningún corte.

## Ritmo de reproducción y cortes de sesión

Dentro de cada secuencia y de cada sesión los cuadros se reproducen en orden cada
**100 ms** (`--replay-dt-ms 100`). Al cambiar de secuencia se deja un hueco de 400 ms
(`max(max_edad_ms, vencimiento_ms) + replay_dt_ms`), mayor que los plazos del watchdog
(300 ms y 250 ms). Con `--reproducir-cortes`, al cambiar `session_id` dentro de una
secuencia se conserva el delta real del manifiesto en lugar de comprimirlo a 100 ms:

| Secuencia | Transición | Pausa de origen | Pausa de replay |
|---|---|---:|---:|
| S1 | `S1_f0009` → `S1_f0010` | 3,623,351 ms | 3,623,351 ms |
| S2 | `S2_f0008` → `S2_f0009` | 241,906 ms | 241,906 ms |
| S2 | `S2_f0016` → `S2_f0017` | 1,992,758 ms | 1,992,758 ms |
| S2 | `S2_f0017` → `S2_f0018` | 1,817,039 ms | 1,817,039 ms |
| S3 | `S3_f0007` → `S3_f0008` | 674,441 ms | 674,441 ms |

El watchdog revisa vencimientos antes del cuadro siguiente, así que cada corte deja un
STOP y no se asume vía libre durante la ausencia de evidencia. No se inventan cuadros ni
se duerme: el reloj controlado avanza el delta real. El resultado es válido a 10 cuadros/s
dentro de cada sesión y a los cortes reales entre sesiones; no es una reproducción en
tiempo real de la captura original.

Sin `--reproducir-cortes`, la corrida sigue siendo la **cadencia virtual** de 100 ms:
`cortes.json` lista los mismos 5 cortes con `aplicado=false` y el delta comprimido. Esa
corrida no debe presentarse como continuidad de captura.

## Cobertura real

| Secuencia | Acciones observadas | Lectura |
|---|---|---|
| S1 | 8 FORWARD, 4 STOP | C1, vía libre; los STOP extra son el inicio y el corte de sesión |
| S2 | 10 STOP, 7 FORWARD | C2 parcial: el detector ve `person` en 4 cuadros y `dog` en 2, con clases espurias |
| S3 | 5 FORWARD, 1 STEER_RIGHT, 7 STOP | C3 parcial: `person` en 4 cuadros; la política no gira hacia la izquierda ocupada |
| S4 | 6 FORWARD, 4 STEER_LEFT, 2 STOP | C4 parcial: `person` en 4 cuadros; la política no gira hacia la derecha ocupada |
| S5 | 12 STOP | C5, tres zonas ocupadas |
| S6 | 10 FORWARD, 2 STOP | C7 parcial: el detector no produjo `person`/`dog` en esta corrida |

## Fallo real del detector (C9)

`fallo_detector/` repite la corrida sobre un JPEG real truncado:

```text
Recorrido run-fallo-real: 1 cuadros, 1 decisiones, 2 comandos
```

El detector levanta `DetectorError`, el evento sale con `status=error`, la política pasa a
`FALLA` y el adaptador registra STOP. La evidencia incluye `run.json`,
`detecciones.jsonl`, `decisiones.jsonl` y `comandos.jsonl` de esa corrida. Es una corrida
de una sola imagen, sin cortes de sesión; conserva su commit original.

## Limitaciones conocidas

- **S2, S3, S4 y S6:** el detector real no siempre ve `person`/`dog`/`cat` ≥ 0.50. En S2,
  S3 y S4 aparece `person` en cuatro cuadros; en S6 no apareció ninguna detección de
  `person`/`dog`. También hay clases espurias (`kite`, `toilet`, `fire hydrant`, `oven`,
  etc.). La política ignora esas clases, así que no inventa obstáculos, pero tampoco puede
  frenar lo que no detecta. C2 y C7 quedan parciales.
- **S5** conserva el protocolo anterior con estímulos en pantalla de teléfono; por eso el
  detector produce `tv` además de `person`/`cat`/`dog`.
- **Arranque y cortes:** el hueco entre secuencias y los cortes de sesión fuerzan un STOP
  de watchdog; las primeras dos decisiones de cada secuencia son STOP por la histéresis de
  la política.
- **Hito I1:** la corrida usa imágenes reales y el detector real; la traza de cinco cuadros
  y los límites de S2/S6 quedan documentados aquí y en `docs/recorrido.md`.
