# Mediciones P5-08

La [guía del benchmark](../docs/benchmark.md) explica los comandos y el alcance.

Usar carpetas nuevas e identificar el modo:

- `sintetico_p5_08/`: pruebas simuladas, no evidencia de latencia del detector.
- `real_cpu_predeterminado_<fecha_UTC>/`: evidencia real autorizada; se crea
  únicamente después de verificar alimentación de red, carga y ensayo corto.

Cada corrida escribe `tiempos.csv`, `fallos.csv`, `contexto.json`, `resumen.json`
y `comandos.jsonl`. No se sobrescriben corridas anteriores. Para entregar evidencia
real hay que identificar explícitamente la carpeta y conservar todos esos archivos;
no mezclar registros de máquinas, entradas o configuraciones distintas.

Las correcciones de hilos y CPU, la integración de main y la medición real
autorizada están verificadas. La [corrida definitiva del 4 nov 2026](real_cpu_predeterminado_20261104T232545932025Z/)
contiene 10 calentamientos excluidos y 100 mediciones válidas, cero fallos.
Total local: p50=15,868200 ms, p95=19,195585 ms y máximo=22,058500 ms.
El recálculo es idéntico byte por byte. Ver
[condiciones, límites y validaciones](../docs/evidencia/p5-08-validacion.md).

El estado de Git «sin commit» y los pendientes de publicación del README/auditoría
de la corrida describen el instante de medición, anterior a esta actualización.
El merge se concluyó en a4f25aa; se conservan los 13 archivos hasheados originales
sin editar sus bytes ni recalcular tiempos para atribuirlos a otro commit.

El ensayo corto real 3/10 se conserva fuera del repositorio, rotulado ENSAYO /
NO EVIDENCIA FINAL. La corrida definitiva incluye auditoría de alimentación/carga,
comando, referencias de código/configuraciones, hashes y recálculo. Se confirmó
corriente antes y después de medir. Sin --hilos se usaron los valores predeterminados
de ONNX como en DetectorONNX; las opciones explícitas son otro experimento.

Las salidas de pruebas no deben presentarse como resultado definitivo. No se
copian las cifras del PM como mediciones locales ni se altera una corrida anterior.
