# Ejemplo SINTÉTICO de P5-07

Geometría inventada para pruebas del algoritmo, sin JPEG ni detección real. Los
hashes repetidos `a`, `b` y `c` son marcadores sintéticos del contrato, no evidencia.
Las predicciones están escritas independientemente de las anotaciones. Este COCO
no es el trabajo de Emilio ni el JSONL es una salida del detector de Edith.

| Cuadro | GT | Predicción | TP | FP | FN |
|---|---|---|---:|---:|---:|
| S1_f1 | person `[0,0,10,10]` xywh | Dos person idénticas xyxy, confianzas 0.9/0.8 | 1 | 1 | 0 |
| S1_f2 | dog | Lista vacía, ok | 0 | 0 | 1 |
| S1_f3 | cat en `[0,0,10,10]` xywh | cat en `[50,50,60,60]` xyxy, sin intersección | 0 | 1 | 1 |
| S1_f4 | Negativa explícita | cat | 0 | 1 | 0 |
| S1_f5 | person | status=error | 0 | 0 | 1 |
| S1_f6 | dog | Cuadro omitido en JSONL | 0 | 0 | 1 |
| **Total** | **5 objetos** | | **1** | **3** | **4** |

| Clase | TP | FP | FN | Soporte | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| person | 1 | 1 | 1 | 2 | 1/2 | 1/2 | 1/2 |
| cat | 0 | 2 | 1 | 1 | 0 | 0 | 0 |
| dog | 0 | 0 | 2 | 2 | 0 (aviso) | 0 | 0 (aviso) |
| micro | 1 | 3 | 4 | 5 | 1/4 | 1/5 | 2/9 |

IoU=0.50. El export usa category_id 1/17/18; se resuelve por `categories[].name`,
mientras el detector usa class_id COCO 0/15/16. Las seis imágenes de prueba solo
son entradas `images` del COCO: nunca se crean ni simulan fotografías.

[Comandos y contrato de entrada/salida](../../../docs/metricas.md).
