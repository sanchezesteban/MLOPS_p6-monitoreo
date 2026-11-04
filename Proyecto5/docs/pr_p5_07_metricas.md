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
- Suite P5 desde Proyecto5: 484 aprobadas, 10 omitidas y un fallo de IDs en
  test_recorrer (espera S2_f0001; captura vigente S2_f0007). Requiere coordinación
  P5-06/P5-14; no se modifican sus pruebas ni datos para forzar aprobación.
- CLI sintética con seis cuadros: **TP=1, FP=3, FN=4; P=0.25, R=0.20, F1=2/9**.
- Salidas sintéticas separadas e ignoradas por Git; no son resultados reales.
- [Evidencia local](evidencia/p5-07-validacion.md) y [reproducción](metricas.md).
- Entorno Python 3.12.16 separado con dependencias base/captura/datos; pip check
  aprobado. El entorno anterior Python 3.10 se conserva intacto. Nueve pruebas
  de inferencia real se omiten por pesos ausentes y una por congelado pendiente.

## Pendiente de integración real

#53 cerrado, contrato integrado. #56 y #58 cerrados; descriptor y runtime ya
integrados. El descriptor confirma person=0, cat=15, dog=16. El cierre de esos
issues no completa automáticamente las anotaciones de las recapturas del PR #84.

El COCO integrado es [datos/anotaciones.json](../datos/anotaciones.json), con
[manifiesto](../datos/manifiesto.csv): ambos contienen 24 imágenes S1/S5.
Emilio debe completar las 54 recapturas S2/S3/S4/S6 y congelar los **78 cuadros
vigentes** (20 despejados, 58 obstáculos y seis fuera de riesgo según captura),
con COCO, manifiesto, HASHES.sha256 y commit. El soporte mide objetos anotados,
no imágenes positivas. No usar los siete cuadros de ajuste ni los 84 históricos.

Antes de inferencia, coordinar los 38 IDs distintos de P5-06/P5-14 y los cortes
S2 mediante las [correspondencias existentes](compatibilidad_ids_consumidores_p5_05b.csv).
No se modifican IDs de otros módulos. Edith deberá entregar un JSONL nuevo con
modelo/configuración congelados después de terminar las anotaciones. El JSONL
histórico solo comparte 24 hashes con la selección vigente; no es la corrida final.

La comparación de clases usa nombres canónicos: los category_id del export
(por ejemplo 1/17/18) se traducen con categories; las predicciones conservan
los índices del descriptor 0/15/16. Ambos esquemas tienen pruebas de regresión.

La corrida real producirá `resultados/metricas.json` y el PM deberá recalcular
las cifras antes de cerrar #59. Mantener «Parte de #59» mientras falte esa
evidencia; agregar una referencia de cierre automático únicamente al completar
y aprobar todos los criterios.

La rama se creó desde origin/main, no desde p5-05-capturas. Los cambios propios
de P5-07 no alteran fotografías, CSV ni módulos de compañeros; las entregas de
otros issues llegaron mediante la actualización desde main. No conecta con
vehículo ni motores.
