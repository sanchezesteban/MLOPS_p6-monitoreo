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
un informe anterior. Las salidas quedan ignoradas por Git según las reglas existentes.

El siguiente comando es únicamente para la corrida definitiva futura: confirmar
el congelado del COCO/manifiesto y del detector; el JSONL es una ruta propuesta.

```powershell
& .\.venv\Scripts\python.exe -m p5.metricas --gt .\datos\anotaciones.json --pred .\resultados\detector_congelado\detecciones.jsonl --manifiesto .\datos\manifiesto.csv --cuadros-esperados 78 --iou 0.5 --salida .\resultados
```

La ruta integrada del COCO es [datos/anotaciones.json](../datos/anotaciones.json),
con [datos/manifiesto.csv](../datos/manifiesto.csv). El
[PR #87](https://github.com/sebastian0023/Proyecto-3-Clasificador-de-imagenes/pull/87)
integrado en main aporta los **78 cuadros de evaluación**, sus anotaciones y
[HASHES.sha256](../datos/HASHES.sha256). **No ejecutar el comando anterior hasta
integrar y verificar los cortes de sesión del PR #88 y confirmar la configuración
congelada del detector**. El JSONL indicado es una salida futura, no una corrida
definitiva recibida.

El informe real irá en `resultados/metricas.json`, sin fabricarlo con ejemplos.
`--cuadros-esperados 78` rechaza otra cantidad, incluidos los 84 antiguos. No
prueba por sí solo que sean los 78 correctos: cotejar manifiesto, hashes y commit.

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

## Pruebas e integración pendiente

Desde Proyecto5:

```powershell
& .\.venv\Scripts\python.exe -B -m pytest tests/test_metricas.py
& .\.venv\Scripts\python.exe -B -m pytest
& .\.venv\Scripts\python.exe -B -m ruff check .
& .\.venv\Scripts\python.exe -B -m ruff format --check .
```

Validación local con Python 3.12.16 tras integrar main: 96 pruebas de métricas
aprobadas; suite completa con 532 aprobadas y nueve omitidas por pesos ausentes;
Ruff check y format aprobados (86 archivos). La prueba de IDs y la comprobación
del congelado ya pasan con los cambios oficiales de main. No se modificaron
pruebas ni datos de otros módulos para lograrlo.
[Detalle y entorno](evidencia/p5-07-validacion.md).

Estado actualizado el 2026-11-04:

| Dependencia | Estado comprobado | Falta para corrida real |
|---|---|---|
| [#53](https://github.com/sebastian0023/Proyecto-3-Clasificador-de-imagenes/issues/53) | Cerrado; v1 integrado | Nada para pruebas de software |
| [#56](https://github.com/sebastian0023/Proyecto-3-Clasificador-de-imagenes/issues/56) | Cerrado; runtime y CLI integrados | JSONL nuevo de los 78 cuadros vigentes, generado después de anotar, con modelo/configuración congelados |
| [Descriptor](../modelo/descriptor.yaml) | Integrado; person=0, cat=15, dog=16 | Registrar hashes y configuración efectivos de la corrida futura |
| [#58](https://github.com/sebastian0023/Proyecto-3-Clasificador-de-imagenes/issues/58) | Cerrado; PR #87 integrado con COCO/manifiesto de 78 y HASHES.sha256 | Conservar este congelado y confirmar su referencia para la corrida definitiva |
| [#57 / PR #84](https://github.com/sebastian0023/Proyecto-3-Clasificador-de-imagenes/pull/84) | Recaptura integrada: 78 evaluación y 7 ajuste; seis fuera de riesgo | Usar exactamente esta selección y generar predicciones nuevas para la corrida definitiva |
| [PR #88](https://github.com/sebastian0023/Proyecto-3-Clasificador-de-imagenes/pull/88) | Pendiente de integración; cortes de sesión de P5-14 | Integrar y comprobar recorrido, IDs y cortes antes de evaluar los 78 |

La evidencia de cuatro imágenes de #81 no sustituye la evaluación completa.
Los 78 cuadros son 20 negativos y 58 positivos, con seis ejemplos fuera de
riesgo según las etiquetas de captura; el soporte de objetos se obtendrá del COCO,
no de esas cifras. No usar ajuste, descartes, pruebas ni los 84 antiguos.

El congelado integrado [HASHES.sha256](../datos/HASHES.sha256) contiene 91
entradas, incluidos JPEG de evaluación/ajuste y sus COCO/manifiestos. Se verificó
su integridad. El [congelado de captura](../datos/HASHES_p5_05b.sha256) se conserva
como procedencia adicional. Las predicciones históricas integradas no sustituyen
una corrida definitiva nueva con la configuración aprobada.

El PR #87 resolvió la discrepancia de IDs observada antes de esta integración;
el ensayo autorizado de S1/S5 comprobó 24 asociaciones de ID/ruta/hash sin
contradicciones. Conservar la [correspondencia](compatibilidad_ids_consumidores_p5_05b.csv)
y coordinar los [cortes de sesión](propuesta_reproductor_cortes_p5_05b.md) con
P5-06/P5-14 al integrar #88. No modificar IDs fuente ni relajar validaciones.

Se ejecutó únicamente el ensayo autorizado de **S1/S5: 24 inferencias nuevas**.
Sus entradas, predicciones, informe y hashes permanecen fuera del repositorio y
de resultados, rotulados **ENSAYO / NO EVIDENCIA FINAL**. No forman parte de la
evidencia definitiva ni se usan para ajustar umbral, NMS o pesos.

Listo ahora: algoritmo, validación, pruebas, corrida sintética y ensayo acotado.
Para cerrar #59 faltan #88, confirmar la configuración congelada, ejecutar los
78 cuadros en [resultados/](../resultados/) y el recálculo/aprobación de cifras
por el PM A. No se declara completo con el ensayo ni con resultados sintéticos.
