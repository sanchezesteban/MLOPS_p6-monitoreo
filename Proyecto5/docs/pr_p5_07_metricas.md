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
- Suite P5 desde Proyecto5, tras integrar main: 532 aprobadas y nueve omitidas
  por pesos ausentes. La discrepancia de IDs anterior quedó resuelta por los
  cambios oficiales integrados; no se modificaron sus pruebas ni datos.
- CLI sintética con seis cuadros: **TP=1, FP=3, FN=4; P=0.25, R=0.20, F1=2/9**.
- Salidas sintéticas separadas e ignoradas por Git; no son resultados reales.
- [Evidencia local](evidencia/p5-07-validacion.md) y [reproducción](metricas.md).
- Entorno Python 3.12.16 separado con dependencias base/captura/datos; pip check
  aprobado. El entorno anterior Python 3.10 se conserva intacto. Nueve pruebas
  de inferencia real se omiten por pesos ausentes; el congelado integrado pasa.
- Ensayo autorizado de S1/S5: 24 inferencias nuevas y correspondencia de
  IDs/rutas/SHA-256 verificada. Artefactos privados externos, **ENSAYO / NO
  EVIDENCIA FINAL**; no se incorporan como evaluación definitiva de los 78.

## Pendiente de integración real

#53 cerrado, contrato integrado. #56 y #58 cerrados; descriptor y runtime ya
integrados. El descriptor confirma person=0, cat=15, dog=16. El PR #87 integrado
aporta las anotaciones de las recapturas del PR #84.

El COCO integrado es [datos/anotaciones.json](../datos/anotaciones.json), con
[manifiesto](../datos/manifiesto.csv): ambos contienen los **78 cuadros vigentes**
(20 despejados, 58 obstáculos y seis fuera de riesgo según captura). Se verificó
el [HASHES.sha256](../datos/HASHES.sha256) integrado: 91 entradas sin diferencias.
El soporte mide objetos anotados, no imágenes positivas. No usar los siete
cuadros de ajuste ni los 84 históricos.

Antes de la corrida definitiva, integrar el PR #88 y comprobar los cortes S2
con P5-06/P5-14 mediante las [correspondencias existentes](compatibilidad_ids_consumidores_p5_05b.csv).
El PR #87 resolvió la discrepancia anterior de IDs; el ensayo S1/S5 verificó sus
24 asociaciones. No se modifican IDs de otros módulos. Confirmar con el equipo
la configuración congelada y generar un JSONL nuevo de los 78 cuadros después
de esa integración. Las predicciones históricas y el ensayo no son la corrida final.

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
