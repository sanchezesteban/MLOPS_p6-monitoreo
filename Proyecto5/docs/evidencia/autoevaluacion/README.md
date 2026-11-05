# Autoevaluación con el prompt del profesor (P5-17)

Se aplicó [`prompt-evaluacion-proyecto-5.md`](../../prompt-evaluacion-proyecto-5.md) sobre una
copia limpia de `main` en `ba81495` (merge del #91), con CPU, adaptador virtual y sin hardware.
**Resultado: 89.5 / 100, requisitos M1–M3 cumplen, compuerta no activada.**

| Archivo | Contenido |
|---|---|
| `reporte-MiniTesla.html` | Reporte completo, autocontenido (apartados A–F del prompt) |
| `evaluacion.md` / `evaluacion.json` | Mismos puntos y evidencias en Markdown y JSON |
| `auditor_m3.py` | Auditor propio de M3 con reloj controlado (watchdog, emergencia, rearme, cierre) |
| `calculo_metricas.py` | Matching propio a IoU 0.50, sin importar `p5` |
| `detecciones_propias.jsonl` | Detecciones de la corrida propia, entrada de `calculo_metricas.py` |
| `muestra.png` | Cuatro cuadros con la verdad de referencia (verde) y las predicciones (rojo) |

Desde `Proyecto5/`:

```bash
python docs/evidencia/autoevaluacion/calculo_metricas.py datos/anotaciones.json \
    docs/evidencia/autoevaluacion/detecciones_propias.jsonl
PYTHONPATH=src python docs/evidencia/autoevaluacion/auditor_m3.py
```

Los 10.5 puntos que faltan: 8.5 por el recall del detector (C2, C3 y C7 y el F1 de 0.656) y 2 por
documentación (mapeo de actuación desactualizado, `config_sha256` que solo cubre la política y el
ritmo de cuadros que asume `watchdog.yaml`). Es una autoevaluación del equipo; no sustituye la
calificación del docente.
