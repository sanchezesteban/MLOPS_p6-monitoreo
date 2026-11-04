# Evidencia del runner de casos (P5-13)

Corrida del **4 nov 2026** con `p5.casos` contra la política de P5-10 (#73), el
adaptador virtual de P5-11 (#74) y el watchdog de P5-12 (#76), ya mergeados en `main`.
Los casos C08–C10 son sintéticos; no usan detector ni datos reales.

```bash
cd Proyecto5
PYTHONPATH=src python -m p5.casos \
    --casos casos \
    --config config/politica.yaml \
    --salida resultados/casos
```

Resultado:

```
C08  pass   Corte de cuadros y cuadro vencido
C09  pass   Error del detector, imagen ilegible y salida no finita
C10  pass   Emergencia, rearme y cierre

Resultado: 3/3 casos pasan (codigo de salida 0)
```

Archivos:

- `resumen.json`: resumen de la corrida, hashes de expectativas y referencias a los
  comandos observados.
- `C08/comandos.jsonl`, `C09/comandos.jsonl`, `C10/comandos.jsonl`: bitácoras por caso.
- `fallo_inducido.txt`: salida de la misma corrida sobre una copia de `casos/` con la
  expectativa de `c08_f0004` cambiada a `FORWARD`. El runner sale con código 1.
- `fallo_inducido_resumen.json`: resumen JSON de ese fallo.

## Pendiente

- Repetir la corrida cuando se mergee la integración final de #65.
- Agregar C01–C07 reales cuando existan `datos/eventos/seqXX.jsonl` y el
  `cuadros.csv` congelado de P5-06/P5-15.
