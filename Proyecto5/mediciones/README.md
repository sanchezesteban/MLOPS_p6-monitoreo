# Mediciones P5-08

La [guía del benchmark](../docs/benchmark.md) explica los comandos y el alcance.

Usar carpetas nuevas e identificar el modo:

- `sintetico_p5_08/`: pruebas simuladas, no evidencia de latencia del detector.
- Una corrida real futura, autorizada y congelada, debe guardarse aparte.

Cada corrida escribe `tiempos.csv`, `fallos.csv`, `contexto.json`, `resumen.json`
y `comandos.jsonl`. No se sobrescriben corridas anteriores. Para entregar evidencia
real hay que identificar explícitamente la carpeta y conservar todos esos archivos;
no mezclar registros de máquinas, entradas o configuraciones distintas.

No existe todavía una medición real de P5-08. Las salidas de pruebas no deben
presentarse como mediciones ONNX ni publicarse como resultado definitivo.
