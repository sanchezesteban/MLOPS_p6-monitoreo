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

- Pruebas del módulo y suite completa P5, Ruff check y Ruff format --check.
- CLI sintética con seis cuadros: **TP=1, FP=3, FN=4; P=0.25, R=0.20, F1=2/9**.
- Salidas sintéticas separadas e ignoradas por Git; no son resultados reales.
- [Evidencia local](evidencia/p5-07-validacion.md) y [reproducción](metricas.md).
- Python 3.10.8 local; Python 3.12 requerido por CI, no instalado localmente.

## Pendiente de integración real

#53 cerrado, contrato integrado. #56 y #58 abiertos; #80 y #81 abiertos sin
fusionar al revisar. El descriptor de #80 confirma person=0, cat=15, dog=16;
no se copia código de esos PR. La CLI de #81 se une por ruta exacta al COCO.

Falta recibir de Emilio el COCO, manifiesto y HASHES.sha256 congelados por commit
para los **78 cuadros definitivos** de evaluación de #57 (20 negativos, 58
positivos, cinco fuera de riesgo), y de Edith el JSONL real y referencia de
modelo/config. El soporte mide objetos anotados, no imágenes positivas.
No usar siete cuadros de ajuste ni la selección antigua de 84.

Emilio confirmó acceso a las 78 fotografías y está comenzando las anotaciones.
La comparación de clases usa nombres canónicos: los category_id del export
(por ejemplo 1/17/18) se traducen con categories; las predicciones conservan
los índices del descriptor 0/15/16. Ambos esquemas tienen pruebas de regresión.

La corrida real producirá `resultados/metricas.json` y el PM deberá recalcular
las cifras antes de cerrar #59. Mantener «Parte de #59» mientras falte esa
evidencia; agregar una referencia de cierre automático únicamente al completar
y aprobar todos los criterios.

Este trabajo parte de origin/main, no de p5-05-capturas. No incluye fotografías,
CSV ni commits propios de #57. No conecta con vehículo, motores o servicios externos.
