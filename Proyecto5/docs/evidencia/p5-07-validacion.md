# Evidencia local P5-07 — actualización 2026-11-04

## Estado tras integrar PR #87 y guardar el ensayo autorizado

Merge de main `e2b544b4c4aa6c418d86baae34f564cf6211d454` en
`p5-07-metricas`, commit `136b75409b03e23a17fb1193493168052cd9e251`.
Los 53 archivos recibidos coinciden exactamente con los blobs de main. Las
actualizaciones de COCO/manifiesto y de módulos de compañeros son aportaciones
oficiales de ese merge, sin ediciones manuales de P5-07. Los 247 JPEG anteriores
(incluidos los archivos históricos) conservan sus bytes; las configuraciones
del detector, política y watchdog no cambiaron durante el ensayo ni al guardarlo.

El COCO/manifiesto integrado cubre **78 imágenes**. Se verificaron las 91
entradas de [HASHES.sha256](../../datos/HASHES.sha256), los 328 archivos fuente
inventariados tras el merge y los 21 archivos del manifiesto del ensayo. Este
último permanece intacto, fuera del repositorio y de resultados, identificado
como **ENSAYO / NO EVIDENCIA FINAL**. No se publican sus predicciones ni sus
resultados como evidencia definitiva. No se ejecutaron nuevas inferencias al
completar el merge y actualizar estos documentos.

Ensayo ya ejecutado con autorización: 24 cuadros exclusivamente de S1/S5,
modelo SHA-256 `c789161ed43c8269fcd4e67c67eeeb4e80c622da2eb296a20bc6007bd18a0b7d`,
CPUExecutionProvider y configuraciones de main sin cambios. Se comprobaron
eventos, IDs, rutas y hashes sin contradicciones. No equivale a la evaluación
definitiva de los 78 y no se utilizó para optimizar el detector.

Validación con Python 3.12.16 y dependencias base/captura/datos en un entorno
separado; el entorno anterior Python 3.10 se conserva intacto:

| Verificación | Resultado tras integrar main |
|---|---|
| Pruebas de métricas | **96 aprobadas** |
| Suite completa desde Proyecto5 | **532 aprobadas, nueve omitidas** |
| Ruff check | **All checks passed!** |
| Ruff format --check | **86 files already formatted** |
| Dependencias | **pip check aprobado** |

Las nueve omisiones corresponden a pruebas con pesos ausentes en el repositorio;
el modelo del ensayo permanece privado y externo. La discrepancia de IDs y la
ausencia del congelado descritas más abajo quedaron resueltas con los cambios
oficiales de main. Falta integrar y verificar los cortes de sesión del PR #88,
confirmar la configuración congelada y ejecutar/aprobar la corrida definitiva.
Se mantiene «Parte de #59».

## Registro previo al PR #87 (histórico; no describe el estado actual)

Rama `p5-07-metricas`, HEAD `6eb42d1fc4898caff95366c6f20e343e43488b0a`.
Solo se actualiza documentación de P5-07: no se cambia el algoritmo, los IDs,
las pruebas de otros módulos, los JPEG, COCO, CSV ni los contratos.

## Entorno separado Python 3.12

Se descargó CPython **3.12.16** mediante uv **0.13.7** a un directorio temporal
fuera del repositorio (`--no-bin --no-registry`); se creó otro entorno virtual
sin activar ni modificar `.venv/`, PATH, el registro de Python o el lanzador.
Se instalaron juntos, sin cambiar sus restricciones:

- [requirements.txt](../../requirements.txt).
- [requirements-capturas.txt](../../requirements-capturas.txt).
- [requirements-datos.txt](../../requirements-datos.txt).

Versiones relevantes: pytest 8.3.3, Ruff 0.16.8, jsonschema 4.23.0,
NumPy 2.5.3, Pillow 12.3.0, OpenCV 4.14.0.94, PyYAML 6.0.3,
certifi 2026.10.23, onnxruntime 1.30.0, ImageHash 4.3.2.
`pip check`: **No broken requirements found.** Instalar onnxruntime no ejecutó
el detector; no se descargaron pesos ni se realizó inferencia real.

Desde Proyecto5, `$python312` identifica el ejecutable del entorno separado:

```powershell
& $python312 -B -m pytest -p no:cacheprovider tests/test_metricas.py
& $python312 -B -m pytest -p no:cacheprovider -rs
& $python312 -B -m ruff check --no-cache .
& $python312 -B -m ruff format --check --no-cache .
& $python312 -m pip check
```

## Resultados actuales

| Verificación | Resultado ejecutado |
|---|---|
| Métricas | **96 aprobadas** |
| Suite completa desde Proyecto5 (directorio de CI) | **484 aprobadas, 1 fallida, 10 omitidas** |
| Ruff check | **All checks passed!** |
| Ruff format --check | **83 files already formatted** |
| Dependencias | **pip check aprobado** |

La única falla restante es
`tests/test_recorrer.py::test_manifiesto_79_genera_frame_id_con_prefijo_y_tiempos_monotonos`,
línea 288: espera `S2_f0001`, pero el lector conserva `S2_f0007`, primer ID de la
selección actual. El código y los datos que provocan esa discrepancia no cambiaron
en esta revisión documental. No se renumeró ni se debilitó la prueba: requiere
coordinar P5-06/P5-14 junto con las
[38 diferencias de IDs](../compatibilidad_ids_consumidores_p5_05b.csv) y
[cortes de sesión S2](../propuesta_reproductor_cortes_p5_05b.md).

Nueve pruebas se omitieron por ausencia de pesos (ocho del detector real y una
del recorrido real), respetando la prohibición de inferencia. Otra se omitió por
no existir el congelado final `datos/HASHES.sha256`.

Una primera ejecución desde la raíz del repositorio también falló en
`test_casos_sinteticos_con_politica_y_adaptador_reales` por la ruta relativa
`config/watchdog.yaml`. Repetir desde Proyecto5, como hace CI, resolvió ese fallo
sin cambiar código. Las cifras vigentes de la tabla corresponden a esa ejecución.

## Estado de las entradas; ninguna evaluación real

Los issues #56 y #58 están cerrados y sus módulos integrados. El COCO y manifiesto
actuales contienen **24 imágenes S1/S5**; faltan las **54 recapturas S2/S3/S4/S6**
para los 78 cuadros autorizados. La ruta existente es
[datos/anotaciones.json](../../datos/anotaciones.json), no un export definitivo
inventado. Las etiquetas de captura suman 20 despejados, 58 obstáculos y **seis**
fuera de riesgo; no son TP/FP/FN ni soporte de objetos anotados.

Emilio debe completar COCO/manifiesto, coordinar los IDs y congelar por commit con
`datos/HASHES.sha256`. El manifiesto de captura `HASHES_p5_05b.sha256` no sustituye
ese congelado de anotaciones. El JSONL histórico de 78 eventos solo comparte 24
hashes con las imágenes vigentes; faltan predicciones nuevas posteriores a la
anotación y con configuración congelada. No se usaron anotaciones antiguas para
calcular métricas definitivas ni se generó `resultados/metricas.json`.

## Evidencia histórica del 2026-11-03

Lo siguiente conserva los comandos y resultados de la revisión anterior; sus
260 pruebas, entorno 3.10 y estados entonces abiertos de #56/#58 no describen
la validación actual. Las cifras vigentes están arriba.

### Registro original del 2026-11-03

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
