# P5-07: Script de métricas TP/FP/FN, Precision, Recall y F1

Parte de #59. Responsable: @BryanRomoG. Revisor: @sebastian0023.

COCO y las predicciones JSONL necesitan una comparación reproducible sobre todos
los cuadros, incluidas negativas y fallos. Se añade `python -m p5.metricas`
para validar esas entradas y calcular TP/FP/FN, Precision/Recall/F1 y soporte por
clase (person/cat/dog) y micro, con IoU configurable (0.50 predeterminado).

## Comportamiento

- Greedy por cuadro/clase, confianza descendente y mejor anotación libre; cada
  objeto se reserva una vez. Duplicados son FP; clase equivocada, FP + FN.
- Error, stale, omisión, evento inválido o repetido no se omiten: sus objetos
  reales cuentan como FN y sus incidencias quedan en el JSON.
- Asociación por frame_id explícito o ruta relativa exacta; manifiesto opcional
  para cotejar identidad, dimensiones y SHA-256. Compatible con IDs cli_* del
  detector sin cambiar IDs originales. Detecta contradicciones y desconocidos.
- Informe determinista con hashes de entradas e implementación, parámetros,
  parejas y detalle por cuadro. Clases sin soporte y divisiones por cero visibles.
- No se añaden dependencias ni se cambian otros módulos, CI o contrato.

## Validación

- Python 3.12.16: 96 pruebas del módulo aprobadas; Ruff check y format aprobados.
- Suite P5 desde Proyecto5, tras integrar #88: **554 aprobadas, ninguna omitida**.
  La discrepancia de IDs anterior quedó resuelta por los
  cambios oficiales integrados; no se modificaron sus pruebas ni datos.
- CLI sintética con seis cuadros: **TP=1, FP=3, FN=4; P=0.25, R=0.20, F1=2/9**.
- Salidas sintéticas separadas e ignoradas por Git; no son resultados reales.
- [Evidencia local](evidencia/p5-07-validacion.md) y [reproducción](metricas.md).
- Entorno Python 3.12.16 separado con dependencias base/captura/datos; pip check
  aprobado. El entorno anterior Python 3.10 se conserva intacto. Las pruebas
  reales con pesos disponibles y el congelado integrado pasan.
- Ensayo autorizado de S1/S5: 24 inferencias nuevas y correspondencia de
  IDs/rutas/SHA-256 verificada. Artefactos privados externos, **ENSAYO / NO
  EVIDENCIA FINAL**; no se incorporan como evaluación definitiva de los 78.

## Corrida definitiva autorizada

#53 cerrado, contrato integrado. #56 y #58 cerrados; descriptor y runtime ya
integrados. El descriptor confirma person=0, cat=15, dog=16. El PR #87 integrado
aporta las anotaciones de las recapturas del PR #84. #88 ya está fusionado en
main 5a38de8; se integró mediante merge e5a1d50 y se verificaron los cinco cortes.

El COCO integrado es [datos/anotaciones.json](../datos/anotaciones.json), con
[manifiesto](../datos/manifiesto.csv): ambos contienen los **78 cuadros vigentes**
(20 despejados, 58 obstáculos y seis fuera de riesgo según captura). Se verificó
el [HASHES.sha256](../datos/HASHES.sha256) integrado: 91 entradas sin diferencias.
El soporte mide objetos anotados, no imágenes positivas. No usar los siete
cuadros de ajuste ni los 84 históricos.

Se generaron **78 eventos nuevos** con p5.recorrer, detector real, CPUExecutionProvider,
cadencia interna de 100 ms y --reproducir-cortes. Sus 78 asociaciones de ID/ruta/hash
coinciden con COCO/manifiesto y las [correspondencias](compatibilidad_ids_consumidores_p5_05b.csv).
78 cuadros ok, 20 negativos; cero omisiones, errores, stale, inválidos, duplicados
o predicciones desconocidas. No se cambiaron IDs, anotaciones, política, umbral o NMS.

Modelo SHA-256 c789161ed43c8269fcd4e67c67eeeb4e80c622da2eb296a20bc6007bd18a0b7d;
Python 3.12.16, ONNX Runtime 1.30.0 y configuración de main sin modificaciones.
IoU de evaluación 0.50 y --cuadros-esperados 78.

| Clase | TP | FP | FN | Soporte | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| person | 22 | 3 | 1 | 23 | 0.880000 | 0.956522 | 0.916667 |
| cat | 8 | 1 | 17 | 25 | 0.888889 | 0.320000 | 0.470588 |
| dog | 12 | 0 | 22 | 34 | 1.000000 | 0.352941 | 0.521739 |
| **Micro** | **42** | **4** | **40** | **82** | **0.913043** | **0.512195** | **0.656250** |

Los conteos coinciden con la referencia de Sebastián. La fracción exacta de F1
es 21/32; el JSON conserva el float calculado 0.6562499999999999, sin edición
manual. Un emparejamiento independiente confirmó los conteos y el recálculo
del evaluador generó un informe idéntico byte por byte.

La comparación de clases usa nombres canónicos: los category_id del export
(por ejemplo 1/17/18) se traducen con categories; las predicciones conservan
los índices del descriptor 0/15/16. Ambos esquemas tienen pruebas de regresión.

Solo se versiona el [informe definitivo](../resultados/metricas/metricas.json)
como salida generada. El recorrido nuevo y sus JSONL siguen locales e ignorados;
los comandos y hashes para reproducirlos están documentados. El ensayo S1/S5 y
las simulaciones no se publican como evidencia definitiva. El evaluador conserva
su etiqueta NO_CERTIFICADA_COMO_CORRIDA_REAL: la procedencia real se comprueba
con comandos, synthetic=false, modelo/configuración y hashes, sin alterar el JSON.

Listo para revisión final de Sebastián/Esteban. Mantener «Parte de #59»; no hacer
merge ni cerrar manualmente la issue desde esta actualización.

La rama se creó desde origin/main, no desde p5-05-capturas. Los cambios propios
de P5-07 no alteran fotografías, CSV ni módulos de compañeros; las entregas de
otros issues llegaron mediante la actualización desde main. No conecta con
vehículo ni motores.
