# P5-08: benchmark local por etapas — issue #60

[Implementación](../src/p5/benchmark.py), [pruebas](../tests/test_benchmark.py) y
[recálculo](../scripts/recalcular_benchmark.py). Responsable: Bryan; revisión: Sebastián.

## Estado y alcance

Preparación de software, con **inferencia simulada**. No se ejecutó el detector
ONNX ni se midió el conjunto definitivo. Los tiempos del modo simulado son tiempos
observados de una cadena de prueba; **no representan la latencia del detector real**.
Se mantienen pendientes la autorización del PM y la corrida real reproducible.

Se revisaron P5-04 (`detector_onnx`), P5-12 (`watchdog`) y P5-14 (`recorrer`).
Se reutilizan `letterbox`, `decodificar`, el lector/config de P5-04, `Politica`,
`Watchdog` y `AdaptadorVirtual`; no se cambian sus módulos ni configuraciones.
La sesión futura de ONNX se crea en este módulo para configurar explícitamente
los hilos de CPU y separar la llamada `run` del pre/posprocesamiento.

De [medir_recursos.py de P4](../../Proyecto4/recursos/medir_recursos.py) se adapta
la metodología: `perf_counter`, calentamientos separados, registro individual,
hashes/condiciones y `numpy.percentile(method="linear")`. El informe registra
el hash de esa referencia. No se importa/ejecuta ese programa: usa `resource`
(Unix), preprocesamiento ImageNet 224×224 y clases del clasificador P4, distintos
de YOLOX 416×416 BGR y sus índices COCO. No se modifica Proyecto4.

## Ejecución de pruebas simuladas

Python 3.12 y las dependencias existentes de `requirements.txt`; la suite completa
también usa `requirements-capturas.txt` y `requirements-datos.txt`. No se añade
ninguna dependencia. Usar un entorno separado si el entorno de trabajo es 3.10.

Desde Proyecto5, con ese entorno activado, en PowerShell:

```powershell
$env:PYTHONPATH = (Resolve-Path .\src).Path
python -m p5.benchmark --modo simulado --salida .\mediciones\sintetico_p5_08
python .\scripts\recalcular_benchmark.py --mediciones .\mediciones\sintetico_p5_08
python .\scripts\recalcular_benchmark.py --mediciones .\mediciones\sintetico_p5_08 --salida .\mediciones\resumen_recalculado_sintetico.json
python -B -m pytest tests/test_benchmark.py
python -B -m ruff check .
python -B -m ruff format --check .
```

El destino debe ser nuevo o vacío (se permiten `.gitkeep` y `README.md`). No se sobrescriben
corridas ni JSON recalculados. Los ejemplos sintéticos deben permanecer en su
carpeta identificada, separados de las futuras mediciones reales.

## Intentos, fallos y estadística

- Predeterminados: **10 calentamientos válidos + 100 ejecuciones válidas**.
  Un fallo no consume una ejecución válida: se conserva y se realiza otro intento.
  No se seleccionan tiempos favorables ni se descartan ejecuciones lentas.
- `--calentamientos`, `--ejecuciones` y `--max-intentos` permiten pruebas pequeñas.
  Para la entrega se usan 10/100. El límite predeterminado es 1000 intentos totales;
  al alcanzarlo se conserva un reporte **incompleto**, sin afirmar que hubo 100 válidas.
- `tiempos.csv` registra **todos** los intentos, incluidos calentamientos y fallos,
  en orden consecutivo. `fallos.csv` conserva aparte exactamente el subconjunto
  de errores, su fase, etapa, mensaje y duración parcial; las etapas posteriores
  al fallo van vacías, nunca con tiempos inventados. La respuesta STOP a un fallo
  se registra fuera de las estadísticas de ejecuciones válidas.
- `resumen.json` informa intentos totales/por fase, fallos y tamaño de las muestras.
  Solo entran en los percentiles filas `fase=medicion, estado=ok`.
- Sobre valores ordenados, índice `(n−1)·q`, interpolación lineal entre sus vecinos:
  p50 usa q=0.50, p95 q=0.95 y máximo el mayor valor. No se redondean los tiempos
  antes de calcular ni de comparar. Sin válidas, métricas `null` y reporte incompleto.

## Límites del cronómetro

`time.perf_counter` delimita una cadena síncrona, sin sleeps ni pausas de reproducción:

| Campo CSV | Incluye |
|---|---|
| `preprocesamiento_ms` | Letterbox y tensor del cuadro RGB completo en memoria |
| `inferencia_ms` | `session.run` y conversión de salida; en simulación, fabricación explícita de una salida cruda |
| `posprocesamiento_ms` | Decodificación, confianza, NMS y cajas en píxeles originales de P5-04 |
| `politica_adaptador_ms` | Evento v1/validación, watchdog, política y adaptador virtual con JSONL/flush |
| `total_local_ms` | Intervalo completo desde antes del preprocesamiento hasta terminar política/adaptador |

Carga de pesos/sesión y lectura/decodificación inicial de la imagen están fuera del
cronómetro; se repite la misma entrada explícita, sin leer COCO. La escritura de
CSV/resumen y el cierre final STOP también quedan fuera. Los tiempos no incluyen
red, transmisión ESP32, captura de cámara, accionamiento o frenado físico.
La política conserva estado durante calentamientos y mediciones. Watchdog y
adaptador comparten un único reloj monotónico real; no se usa el reloj virtual
ni la normalización a 100 ms de P5-14. No se accede a motores.

## Archivos, condiciones y recálculo

Cada carpeta de corrida contiene `tiempos.csv`, `fallos.csv`, `contexto.json`,
`resumen.json` y `comandos.jsonl`. El contexto conserva CPU/arquitectura, SO,
Python, NumPy, versión instalada de ONNX Runtime, hilos ONNX y variables de hilos,
commit, hashes de código y configuración, origen/dimensiones/hash de entrada y
tamaño/hash de pesos realmente cargados. En simulación, pesos e hilos ONNX son
`null`/no aplicables; instalar el runtime no equivale a ejecutarlo. Entrada RGB
seed=42 y detecciones fabricadas están identificadas como sintéticas.

El recálculo verifica SHA-256 de CSV/contexto, integridad de columnas, secuencia de
intentos/fases, tiempos finitos, suma de etapas y correspondencia de fallos.
Vuelve a calcular todo sin confiar en los percentiles del resumen, y compara
el resultado con el original. No abre imágenes, modelos ni configuraciones actuales.
Los hashes detectan alteraciones respecto al reporte, no sustituyen una firma digital.

El contraste usa los tres plazos efectivamente leídos de `config/watchdog.yaml`:
reacción=100 ms, edad=300 ms, vencimiento=250 ms en la configuración inspeccionada.
Para p95 y máximo del total local informa valor, margen `plazo−tiempo` y si cabe
(comparación inclusiva). El informe **no ajusta los plazos ni certifica seguridad**:
una latencia local corta no garantiza cumplir el tiempo físico de reacción y
los resultados simulados no permiten aceptar el presupuesto del detector real.

Códigos CLI: 0 muestra completa, 1 corrida incompleta, 2 entrada/IO/config inválida.
Una interrupción durante una etapa conserva la fila fallida, cierra el adaptador
y produce reporte incompleto. Fallos de escritura pueden impedir finalizar un
reporte; se conservan los registros ya escritos, sin sobrescribirlos al reintentar.

## Para completar el benchmark real

1. Obtener autorización expresa del PM para ejecutar inferencia. Esta preparación
   no modifica el veto actual al conjunto definitivo.
2. Acordar una entrada representativa y un protocolo antes de medir; registrar
   ruta/hash, pesos/descriptor, umbral, NMS, CPU, hilos y commit congelados.
3. Ejecutar el modo explícito `--modo real --imagen <entrada aprobada>` en otra
   carpeta de mediciones, con pesos cuyo hash coincida exactamente con el descriptor.
   Nunca hay activación automática del modo real ni búsqueda de fotografías.
4. Conseguir 10/100 válidas con todos los fallos visibles, recalcular, comparar
   presupuestos con P5-12 y revisar las cifras con Sebastián. Documentar entrada
   fija en memoria y alcance local; no atribuir resultados al carrito completo.

La integración del recorrido conserva pendientes sus IDs/cortes con P5-06/P5-14.
El benchmark no renumera capturas, no consume sus anotaciones y no resuelve esos
pendientes modificando el trabajo de sus responsables. No cierra #60 solo con simulación.
