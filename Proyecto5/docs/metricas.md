# P5-07: métricas de detección — issue #59

[Módulo](../src/p5/metricas.py), [pruebas](../tests/test_metricas.py) y
[casos sintéticos calculados a mano](../tests/fixtures/metricas/README.md).
Responsable: Bryan (@BryanRomoG); revisión: Sebastián (@sebastian0023).

## Ejecución

Python 3.12 es la referencia del proyecto y CI. Usa las dependencias existentes
de [requirements.txt](../requirements.txt); no se agrega ninguna. El evaluador usa
la biblioteca estándar y el validador del [contrato v1](../config/contrato_v1.md)
(jsonschema). No importa ONNX, OpenCV, política ni control; no necesita imágenes,
red, pesos o vehículo. Se comprobó con Python 3.12.16 en un entorno separado
y se conservó intacto el entorno anterior de Python 3.10; ver
[evidencia de validación](evidencia/p5-07-validacion.md).

Desde la raíz del repositorio, en PowerShell:

```powershell
Set-Location .\Proyecto5
$env:PYTHONPATH = (Resolve-Path .\src).Path
& .\.venv\Scripts\python.exe -m p5.metricas --gt .\tests\fixtures\metricas\gt.coco.json --pred .\tests\fixtures\metricas\predicciones.jsonl --iou 0.5 --salida .\resultados\sintetico_issue59
```

En POSIX, desde Proyecto5:

```bash
PYTHONPATH=src python -m p5.metricas --gt <coco> --pred <jsonl> --iou 0.5 --salida <dir>
```

Usa una carpeta nueva o que aún no contenga `metricas.json`: jamás se sobrescribe
un informe anterior. Las salidas quedan ignoradas por Git según las reglas existentes,
salvo el informe definitivo añadido expresamente en este PR.

La corrida definitiva autorizada se ejecutó con el recorrido nuevo del
2026-11-05 UTC (4 de noviembre en México), sin reutilizar el JSONL histórico:

```powershell
python -B -m p5.metricas --gt datos/anotaciones.json --pred resultados/recorrido_metricas_78_20261105T002327358258Z/detecciones.jsonl --manifiesto datos/manifiesto.csv --cuadros-esperados 78 --iou 0.50 --salida resultados/metricas
```

La ruta integrada del COCO es [datos/anotaciones.json](../datos/anotaciones.json),
con [datos/manifiesto.csv](../datos/manifiesto.csv). El
[PR #87](https://github.com/sebastian0023/Proyecto-3-Clasificador-de-imagenes/pull/87)
integrado en main aporta los **78 cuadros de evaluación**, sus anotaciones y
[HASHES.sha256](../datos/HASHES.sha256). El PR #88 también está integrado;
se verificaron sus cinco cortes de sesión y la cadencia de 100 ms dentro de cada
sesión. Los comandos exactos del recorrido y del evaluador están en el
[README](../README.md#métricas-de-detección-p5-07).

El [informe definitivo](../resultados/metricas/metricas.json) está en
`resultados/metricas/metricas.json`, calculado desde las predicciones nuevas.
`--cuadros-esperados 78` rechaza otra cantidad, incluidos los 84 antiguos. No
prueba por sí solo que sean los 78 correctos: cotejar manifiesto, hashes y commit.

Al reproducir, usar carpetas nuevas: el informe versionado ya existe y el CLI
rechaza sobrescribirlo. Por ejemplo, mantener --gt/--pred/--manifiesto y cambiar
--salida a resultados/metricas_reproduccion. Con los mismos bytes de entrada y
el mismo entorno se obtuvo un segundo informe idéntico byte por byte.

## Resultados definitivos

| Clase | TP | FP | FN | Soporte | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| person | 22 | 3 | 1 | 23 | 0.880000 | 0.956522 | 0.916667 |
| cat | 8 | 1 | 17 | 25 | 0.888889 | 0.320000 | 0.470588 |
| dog | 12 | 0 | 22 | 34 | 1.000000 | 0.352941 | 0.521739 |
| **Micro** | **42** | **4** | **40** | **82** | **0.913043** | **0.512195** | **0.656250** |

Los conteos coinciden con la referencia de los PM y con un emparejamiento
independiente. F1 exacto es 21/32; el JSON conserva 0.6562499999999999, una unidad
de precisión binaria por debajo de 0.65625 al aplicar la fórmula con float.
No se editaron las cifras ni el algoritmo para forzar la coincidencia.

78 cuadros esperados/evaluados/ok, 20 negativos; cero missing/error/stale/invalid/
duplicate y ninguna predicción desconocida. Se incluyeron todas las anotaciones
person/cat/dog, también fuera de riesgo; 37 detecciones de otras clases quedaron
fuera del alcance y están advertidas. No significa que se detectaran todos los
obstáculos: hubo 40 FN. No se calculó accuracy ni se ajustó el detector.

Modelo YOLOX-Nano SHA-256
`c789161ed43c8269fcd4e67c67eeeb4e80c622da2eb296a20bc6007bd18a0b7d`,
CPUExecutionProvider y sesión predeterminada de DetectorONNX; Python 3.12.16,
ONNX Runtime 1.30.0, Windows 11. Configuraciones de main sin cambios: umbral
0.30 y NMS 0.45 del detector, política y watchdog congelados. IoU de evaluación
0.50 es independiente del NMS. [Hashes, cortes y validación](evidencia/p5-07-validacion.md).

## Entradas e identidad

- COCO requiere `images`, `annotations`, `categories`. `images` incluye también
  negativas, con id único, file_name relativo con `/` y dimensiones enteras
  positivas. IDs enteros o strings; no se infiere orden temporal.
- Anotaciones: id único, image_id/category_id existentes y bbox `xywh` finita con
  área positiva dentro de la imagen; se convierte a `xyxy`. Categorías por nombre,
  no por número del export. Se evalúan todas las cajas person/cat/dog, incluidas
  laterales y fuera de riesgo; otras clases se contabilizan fuera del alcance.
  crowd/ignore se rechazan: no se implementan COCO AP ni sus regiones ignoradas.
- Las numeraciones GT `0=person, 15=cat, 16=dog` y `1=person, 17=cat, 18=dog`
  producen los mismos emparejamientos al traducir por `categories[].name`.
  Los IDs GT nunca se comparan con los índices del detector. Las pruebas cubren
  ambas numeraciones por clase y con las tres clases simultáneas.
- JSONL: un evento v1 por imagen validado con `validar_evento`; índices COCO
  person=0, cat=15, dog=16. Se verifica clase/índice para estas clases y se cuentan
  aparte las demás detecciones válidas. No se añade filtro de confianza ni NMS.
- Asociación por `images[].frame_id` explícito o coincidencia **exacta** de
  `image_path` con `file_name`. No usar basename, números del JPEG, cercanía temporal,
  orden de filas ni conversión implícita de id COCO a frame_id. ID y ruta
  contradictorios invalidan las imágenes afectadas.
- `--manifiesto` opcional usa los campos de #58: sequence_id, frame_id,
  t_capture_ms, ruta, ancho, alto, sha256; admite estado_esperado_via sin usarlo
  para predecir ni puntuar. Exige las mismas rutas que COCO, IDs únicos,
  dimensiones y hashes hex64. Añade la identidad/hash originales a la evaluación
  sin modificar el COCO y rechaza metadatos contradictorios.
- Se coteja el hash del evento con COCO/manifiesto cuando existe; con error
  puede ser null. **No se leen bytes JPEG**: comprobar físicamente HASHES.sha256
  al congelar los datos, antes de la corrida real.
- Una sola corrida/modelo/config/synthetic por JSONL; prefijo frame_id de su
  secuencia y reloj de ejecución estrictamente creciente en orden de líneas.
  No se compara el tiempo del manifiesto con el evento: v1 permite desfases por
  secuencia. No se reescriben tiempos, IDs o archivos fuente.

La CLI del [PR #81](https://github.com/sebastian0023/Proyecto-3-Clasificador-de-imagenes/pull/81)
usa sequence_id=cli, frame_id=cli_00000… y tiempo de orden de procesamiento. Se
admite por ruta exacta, conservando ID original y de predicción. Invocarla con
una sola carpeta raíz que produzca las mismas rutas relativas de COCO/manifiesto;
archivos aislados pueden perder el prefijo S1/S2. No inventar correspondencias.

## Algoritmo y fórmulas

Por cuadro/clase, ordenar detecciones por confianza descendente. Cada una busca
la anotación **libre** de mayor IoU (área de intersección/unión de cajas continuas,
sin sumar 1). Si IoU >= umbral, TP y reserva la anotación; sin pareja, FP.
Las anotaciones restantes son FN. Un duplicado no reutiliza anotaciones; clase
equivocada produce FP en la predicha y FN en la real. No hay optimización global.
Desempates: índice original de predicción y tipo/id de anotación lexicográfico.
Predeterminado 0.50, configurable en `0 < --iou <= 1`.

```text
soporte = TP + FN (objetos reales, no imágenes positivas)
Precision = TP / (TP + FP)
Recall = TP / (TP + FN)
F1 = 2 * Precision * Recall / (Precision + Recall)
```

Micro suma TP/FP/FN de las tres clases antes de aplicar fórmulas, sin promediar
clases. Cada denominador cero devuelve 0 con aviso de clase/métrica. Se conservan
clases sin soporte. No se calcula accuracy ni mAP.

## Fallos y reporte

Todos los cuadros COCO contribuyen. Error, stale, omisión, evento inválido o
duplicado rechazan detecciones y cuentan **todos sus objetos GT como FN**.
Una negativa fallida conserva el fallo aunque aporte cero TP/FP/FN. Error/stale
no significan vía libre ni detección exitosa.

Duplicados por frame_id o imagen se rechazan sin elegir el resultado favorable.
Desconocidos, JSONL malformado y estados inválidos se listan. Mezclar
run/model/config/synthetic invalida todo el archivo. GT o manifiesto ambiguos
abortan sin puntuar sobre una referencia inválida.

JSON: parámetros, hashes/bytes/nombres de entradas y módulo/contrato/schema,
Python, run/model/config/synthetic, conteos, por clase, micro, avisos y detalle
por imagen (líneas JSONL, parejas, IoU, anotaciones sin pareja). `evaluated`
incluye fallidos que aportan FN; `ok` cuenta cuadros procesados correctamente.
Los estados suman el total esperado. Sin hora actual ni rutas absolutas: mismos
bytes de entrada, implementación y entorno generan los mismos bytes de salida.

`evidence=SINTETICA` si info.synthetic=true en COCO o un evento es sintético;
en otro caso, `NO_CERTIFICADA_COMO_CORRIDA_REAL`. La ausencia de esa marca no
certifica origen físico ni congelado.

Salidas CLI: **0** cálculo válido, incluso con inferencias fallidas/omisiones ya
penalizadas; **1** informe con defectos de entrada (input_integrity_ok=false:
desconocidos, duplicados, eventos inválidos); **2** entrada estructural/IO/config
inválida o informe existente. Código 0 no implica buen desempeño ni cierre del issue.

## Pruebas e integración verificada

Desde Proyecto5:

```powershell
& .\.venv\Scripts\python.exe -B -m pytest tests/test_metricas.py
& .\.venv\Scripts\python.exe -B -m pytest
& .\.venv\Scripts\python.exe -B -m ruff check .
& .\.venv\Scripts\python.exe -B -m ruff format --check .
```

Validación local con Python 3.12.16 tras integrar main: 96 pruebas de métricas
aprobadas; suite completa con **554 aprobadas, ninguna omitida**;
Ruff check y format aprobados (89 archivos). La prueba de IDs y la comprobación
del congelado ya pasan con los cambios oficiales de main. No se modificaron
pruebas ni datos de otros módulos para lograrlo.
[Detalle y entorno](evidencia/p5-07-validacion.md).

Estado de la entrega definitiva (2026-11-05 UTC):

| Dependencia | Estado comprobado | Resultado de integración |
|---|---|---|
| [#53](https://github.com/sebastian0023/Proyecto-3-Clasificador-de-imagenes/issues/53) | Cerrado; v1 integrado | Nada para pruebas de software |
| [#56](https://github.com/sebastian0023/Proyecto-3-Clasificador-de-imagenes/issues/56) | Cerrado; runtime y CLI integrados | JSONL nuevo de los 78 cuadros, posterior al congelado COCO |
| [Descriptor](../modelo/descriptor.yaml) | Integrado; person=0, cat=15, dog=16 | Modelo y configuraciones comprobados por SHA-256 |
| [#58](https://github.com/sebastian0023/Proyecto-3-Clasificador-de-imagenes/issues/58) | Cerrado; PR #87 integrado con COCO/manifiesto de 78 y HASHES.sha256 | Congelado verificado, sin cambios de anotaciones |
| [#57 / PR #84](https://github.com/sebastian0023/Proyecto-3-Clasificador-de-imagenes/pull/84) | Recaptura integrada: 78 evaluación y 7 ajuste; seis fuera de riesgo | Se evaluó exactamente esta selección; ajuste excluido |
| [PR #88](https://github.com/sebastian0023/Proyecto-3-Clasificador-de-imagenes/pull/88) | Fusionado en main 5a38de8 | IDs, rutas, hashes y cinco cortes de sesión verificados |

La evidencia de cuatro imágenes de #81 no sustituye la evaluación completa.
Los 78 cuadros son 20 negativos y 58 positivos, con seis ejemplos fuera de
riesgo según las etiquetas de captura; el soporte de objetos es 82 según COCO,
no de esas cifras. No usar ajuste, descartes, pruebas ni los 84 antiguos.

El congelado integrado [HASHES.sha256](../datos/HASHES.sha256) contiene 91
entradas, incluidos JPEG de evaluación/ajuste y sus COCO/manifiestos. Se verificó
su integridad. El [congelado de captura](../datos/HASHES_p5_05b.sha256) se conserva
como procedencia adicional. Se generaron predicciones nuevas con la configuración
aprobada; las predicciones históricas no se usaron como evidencia de esta corrida.

El PR #87 resolvió la discrepancia de IDs observada antes de esta integración;
la corrida definitiva comprobó las 78 asociaciones de ID/ruta/hash sin
contradicciones. Se conserva la [correspondencia](compatibilidad_ids_consumidores_p5_05b.csv)
y se comprobaron los [cortes de sesión](propuesta_reproductor_cortes_p5_05b.md)
con el código integrado de P5-14. No se modificaron IDs fuente ni validaciones.

El ensayo anterior de **S1/S5: 24 inferencias** sigue separado de la definitiva.
Sus entradas, predicciones, informe y hashes permanecen fuera del repositorio y
de resultados, rotulados **ENSAYO / NO EVIDENCIA FINAL**. No forman parte de la
evidencia definitiva ni se usan para ajustar umbral, NMS o pesos.

La programación, pruebas, corrida definitiva y recálculo están completos; queda
la revisión final del PR #89 por los PM y su merge por Sebastián. Se mantiene
«Parte de #59»: no se cierra manualmente la issue ni se fusiona el PR desde esta tarea.
