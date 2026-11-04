# Eventos por secuencia para el runner (P5-14)

`S1.jsonl` … `S6.jsonl` son la salida del recorrido real con `DetectorONNX` sobre las 78
capturas de `datos/evaluacion/`, separada por `sequence_id` para que `p5.casos` pueda
reproducir C01–C07. No son la verdad de referencia ni expectativas: son eventos del
contrato v1 (`PerceptionEvent`), con las detecciones del detector y el reloj de replay.

- **Corrida:** `run-eventos-001`, commit `51d96ed`.
- **Modelo:** `c789161ed43c8269fcd4e67c67eeeb4e80c622da2eb296a20bc6007bd18a0b7d`.
- **Manifiesto:** `datos/evaluacion/capturas.csv`, SHA-256 `f8a04169…`.
- **Modo:** `cortes_sesion`; 5 cortes de sesión aplicados (S1, S2 ×3, S3).
- **Conteos:** S1 12, S2 17, S3 13, S4 12, S5 12, S6 12; total 78.
- **IDs:** los mismos de `docs/compatibilidad_ids_consumidores_p5_05b.csv`
  (`frame_id_reproductor_P514_cache`).

## Procedencia

```bash
cd Proyecto5
PYTHONPATH=src python -m p5.recorrer \
    --datos datos/evaluacion \
    --manifiesto datos/evaluacion/capturas.csv \
    --config config/politica.yaml \
    --watchdog-config config/watchdog.yaml \
    --detector real \
    --detector-config config/detector.yaml \
    --reproducir-cortes \
    --replay-dt-ms 100 \
    --salida resultados/recorrido-eventos \
    --run-id run-eventos-001

PYTHONPATH=src python scripts/exportar_eventos.py \
    --detecciones resultados/recorrido-eventos/detecciones.jsonl \
    --run resultados/recorrido-eventos/run.json \
    --cortes resultados/recorrido-eventos/cortes.json \
    --salida datos/eventos
```

`eventos_origen.json` conserva los hashes de la corrida, el modo, el total de cortes y los
conteos por secuencia. Si se regenera la corrida, `exportar_eventos.py` falla si cambia el
contenido de un archivo existente; usa `--force` solo cuando el cambio esté justificado.
