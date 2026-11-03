# P5-07: métricas de detección — issue #59

[Módulo](../src/p5/metricas.py), [pruebas](../tests/test_metricas.py) y
[casos sintéticos calculados a mano](../tests/fixtures/metricas/README.md).
Responsable: Bryan (@BryanRomoG); revisión: Sebastián (@sebastian0023).

## Ejecución

Python 3.12 es la referencia del proyecto y CI. Usa las dependencias existentes
de [requirements.txt](../requirements.txt); no se agrega ninguna. El evaluador usa
la biblioteca estándar y el validador del [contrato v1](../config/contrato_v1.md)
(jsonschema). No importa ONNX, OpenCV, política ni control; no necesita imágenes,
red, pesos o vehículo. También se comprueba localmente con el entorno Python 3.10.

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

Para la corrida real futura, una vez verificados los insumos (los nombres
COCO/JSONL siguientes son rutas propuestas, aún no disponibles):

```powershell
& .\.venv\Scripts\python.exe -m p5.metricas --gt .\datos\anotaciones.coco.json --pred .\resultados\detector_congelado\detecciones.jsonl --manifiesto .\datos\manifiesto.csv --cuadros-esperados 78 --iou 0.5 --salida .\resultados
```

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

Estado consultado el 2026-11-03:

| Dependencia | Estado comprobado | Falta para corrida real |
|---|---|---|
| [#53](https://github.com/sebastian0023/Proyecto-3-Clasificador-de-imagenes/issues/53) | Cerrado; v1 integrado | Nada para pruebas de software |
| [#56](https://github.com/sebastian0023/Proyecto-3-Clasificador-de-imagenes/issues/56) | Abierto; [PR #81](https://github.com/sebastian0023/Proyecto-3-Clasificador-de-imagenes/pull/81) abierto sin fusionar | JSONL de los 78 cuadros y configuración/modelo usados |
| [PR #80](https://github.com/sebastian0023/Proyecto-3-Clasificador-de-imagenes/pull/80) | Descriptor disponible, abierto sin fusionar | Integración del detector, sin copiar su código aquí |
| [#58](https://github.com/sebastian0023/Proyecto-3-Clasificador-de-imagenes/issues/58) | Emilio confirmó acceso a las 78 fotografías y está comenzando las anotaciones, según comunicación del operador; aún no se recibieron insumos congelados | COCO definitivo, manifiesto, HASHES.sha256, commit y correspondencia |
| [#57 / PR #79](https://github.com/sebastian0023/Proyecto-3-Clasificador-de-imagenes/pull/79) | Entrega separada, 78 evaluación y 7 ajuste | Anotar exactamente la selección autorizada |

La evidencia de cuatro imágenes de #81 no sustituye la evaluación completa.
Los 78 cuadros son 20 negativos y 58 positivos, con cinco ejemplos fuera de
riesgo; el soporte de objetos se obtendrá del COCO, no de esas cifras. No usar
ajuste, descartes, pruebas ni los 84 antiguos.

Listo ahora: algoritmo, validación, pruebas y corrida sintética auditable. Para
cerrar #59 faltan la corrida real en [resultados/](../resultados/), sus entradas
congeladas y recálculo/aprobación de cifras por el PM A. No se declara completo
con resultados sintéticos.
