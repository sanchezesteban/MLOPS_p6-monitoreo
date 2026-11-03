# Evidencia local P5-07 — 2026-11-03

Rama `p5-07-metricas` creada directamente de `origin/main`:
`7b6a88b1754d906d6376d089c2d8b9bf8f32c292`, tras `git fetch origin`.
La rama no existía localmente ni en remoto. Árbol limpio antes de cambiar.
No incluye los cuatro commits propios de capturas de `p5-05-capturas`.

Entorno existente: **Python 3.10.8**. `py --list-paths` solo encontró 3.10;
**no se ejecutó Python 3.12 local ni CI remoto**. Ruff usa target-version py312
del proyecto; esto no sustituye ejecutar el CI. Sin nuevas dependencias;
`pip check`: `No broken requirements found.`

## Comprobaciones ejecutadas

Desde Proyecto5, con `.venv/Scripts/python.exe -B`:

| Comando | Resultado real |
|---|---|
| `-m pytest -p no:cacheprovider tests/test_metricas.py` | 96 passed in 0.87s |
| `-m pytest -p no:cacheprovider` | 260 passed in 1.41s |
| `-m ruff check --no-cache .` | All checks passed! |
| `-m ruff format --check --no-cache .` | 20 files already formatted |

La base sin cambios tenía 164 pruebas aprobadas; se añadieron 96 casos de métricas.
Las pruebas no cargan pesos, conectan con el vehículo ni requieren internet.
Incluyen un subprocess real de `python -m p5.metricas`, dos ejecuciones con
salidas byte a byte idénticas y protección contra sobrescritura.

La aclaración de clases añadió once regresiones: cada clase con GT 0/15/16 y
1/17/18 (seis casos), las tres simultáneas con cada esquema (dos casos, TP=3,
FP=0, FN=0) y rechazo de las tres combinaciones nombre/índice de detector
incoherentes. Son casos SINTÉTICOS en memoria; no se crean anotaciones reales.
La identidad GT se obtiene de categories[].name, independientemente del orden
del arreglo y sin comparar category_id con class_id.

## Corrida CLI SINTÉTICA

```powershell
$env:PYTHONPATH=(Resolve-Path .\src).Path
& .\.venv\Scripts\python.exe -B -m p5.metricas --gt tests/fixtures/metricas/gt.coco.json --pred tests/fixtures/metricas/predicciones.jsonl --iou 0.5 --cuadros-esperados 6 --salida resultados/sintetico_issue59_final
```

Código 0. Escribe el informe en `resultados/sintetico_issue59_final/metricas.json`,
ignorado por Git. No se generó la salida real `resultados/metricas.json`.

```json
{
  "evidence": "SINTETICA",
  "frames": {
    "expected": 6,
    "evaluated": 6,
    "ok": 4,
    "negative": 1,
    "missing": 1,
    "error": 1,
    "stale": 0,
    "invalid": 0,
    "duplicate": 0
  },
  "micro": {
    "tp": 1,
    "fp": 3,
    "fn": 4,
    "support": 5,
    "precision": 0.25,
    "recall": 0.2,
    "f1": 0.22222222222222224
  }
}
```

Es un extracto del informe sintético, no una medición del detector.
[Cálculo manual](../../tests/fixtures/metricas/README.md): P=1/4, R=1/5,
F1=2/9 (diferencia final de representación binaria de float).
Por clase: person=(1,1,1), cat=(0,2,1), dog=(0,0,2), en orden TP/FP/FN.
Una negativa con predicción aporta FP; error y omisión conservan sus FN.

## Límites y cierre pendiente

#53 cerrado. #56/#58 y PR #80/#81 abiertos sin fusionar al consultar GitHub.
No hay COCO/manifiesto congelados en main ni entradas disponibles suficientes
para evaluar los 78 cuadros definitivos de #57. Los cuatro ejemplos reales de
#81 no se utilizan para inventar una corrida completa. Solo hay evidencia sintética.

Faltan COCO/manifiesto/HASHES.sha256/commit de Emilio, JSONL completo y referencias
de modelo/config de Edith, ejecución real y recálculo por Sebastián. Los siete
cuadros de ajuste y los descartes quedan fuera de la evaluación.
Emilio confirmó que accede a las 78 fotografías y está comenzando las anotaciones,
según la comunicación del operador; esto aún no constituye el congelado definitivo.

Los datos locales previos de #57 que aparecen no versionados tras cambiar de rama
se conservan fuera del staging. Solo se seleccionan las rutas de métricas y esta
documentación; no se cambia el contrato, CI, dependencias ni código de compañeros.
No se hace push, se abre PR ni se integra main durante esta preparación.
