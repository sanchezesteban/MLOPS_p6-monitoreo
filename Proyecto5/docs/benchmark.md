# P5-08: benchmark local por etapas — issue #60

[Implementación](../src/p5/benchmark.py), [pruebas](../tests/test_benchmark.py) y
[recálculo](../scripts/recalcular_benchmark.py). Responsable: Bryan; revisión: Sebastián.

## Estado y alcance

Software validado con simulaciones y actualizado con main tras integrar el PR #88
(`5a38de8`). La corrida real solicitada utiliza una sola imagen autorizada, repetida
con 10 calentamientos y 100 mediciones; no evalúa las 78 fotografías ni su calidad.
La [corrida real del 4 nov 2026](../mediciones/real_cpu_predeterminado_20261104T232545932025Z/)
completó las 100 mediciones válidas sin fallos. Total local: p50=15,868200 ms,
p95=19,195585 ms y máximo=22,058500 ms; p95 y máximo por debajo de 100 y 250 ms.
La evidencia y su estado se documentan en [validación](evidencia/p5-08-validacion.md)
y [mediciones](../mediciones/README.md). Los tiempos simulados **no representan
la latencia del detector real** y se conservan separados.

Se revisaron P5-04 (`detector_onnx`), P5-12 (`watchdog`) y P5-14 (`recorrer`).
Se reutilizan `letterbox`, `decodificar`, el lector/config de P5-04, `Politica`,
`Watchdog` y `AdaptadorVirtual`; no se cambian sus módulos ni configuraciones.
La sesión de ONNX se crea en este módulo para separar `run` del pre/posprocesamiento.
Sin `--hilos`, llama a InferenceSession con CPUExecutionProvider y sin SessionOptions,
exactamente como DetectorONNX. No se fuerza un hilo. El valor efectivo 0 de intra/inter
significa decisión automática de ONNX Runtime, no cero hilos ni un hilo.

`--hilos N` sigue disponible para experimentos separados. Registra modo explícito,
N solicitado y opciones efectivas, y añade una advertencia de que esa sesión es
distinta de DetectorONNX y no es directamente comparable con el recorrido.
Contexto y resumen incluyen los mismos metadatos de hilos y proveedores efectivos.
Coincidir en la sesión no garantiza igualdad de hardware, entrada o carga del sistema.

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
carpeta identificada, separados de las mediciones reales.

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

El modelo del CPU se consulta mediante `sysctl machdep.cpu.brand_string` en macOS;
si no aporta un modelo, se usa `system_profiler SPHardwareDataType -json` para
obtener chip_type/cpu_type, incluidos Apple Silicon. En Windows se usa
ProcessorNameString del registro y en Linux model name/Hardware de /proc/cpuinfo.
Se conserva una alternativa de platform.processor cuando identifica un modelo.
Una cadena como arm, arm64 o x86_64 no se acepta como modelo: se registra null con
advertencia si el sistema no permite obtenerlo. Se guarda también la fuente.

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

## Protocolo real autorizado para PR #90

La imagen acordada es [S2_f0008](../datos/evaluacion/S2/S2_0000058828_S2_f0008.jpg),
SHA-256 `98c6d6431d0bd1a44ca6c69790344f4f21b3cc8c647b2b6f0495fbf9f8e5e8b7`.
Pesos SHA-256 `c789161ed43c8269fcd4e67c67eeeb4e80c622da2eb296a20bc6007bd18a0b7d`.
Usar CPUExecutionProvider sin --hilos y los tres YAML de main sin cambios.
No ajustar umbral, NMS o pesos; no elegir tiempos favorables ni repetir la corrida
para mejorar cifras. Registrar todos los fallos y reintentos.

Antes del ensayo corto y de la corrida definitiva, comprobar alimentación de red
y ausencia de tareas pesadas. Con batería, alimentación desconocida o carga no
verificable, detener la medición y solicitar confirmación al operador. Conservar
la comprobación del equipo en la auditoría; no afirmar reposo durante toda la
corrida basándose únicamente en una muestra anterior.

Desde Proyecto5, con Python 3.12 y src en PYTHONPATH:

```powershell
# Ensayo de funcionamiento: carpeta externa nueva; no evidencia definitiva.
python -m p5.benchmark --modo real --imagen datos/evaluacion/S2/S2_0000058828_S2_f0008.jpg --calentamientos 3 --ejecuciones 10 --salida <ensayo_externo_nuevo>
python scripts/recalcular_benchmark.py --mediciones <ensayo_externo_nuevo>
# Solo tras comprobar ensayo, alimentación y carga: carpeta definitiva nueva.
python -m p5.benchmark --modo real --imagen datos/evaluacion/S2/S2_0000058828_S2_f0008.jpg --calentamientos 10 --ejecuciones 100 --salida mediciones/<carpeta_real_nueva>
python scripts/recalcular_benchmark.py --mediciones mediciones/<carpeta_real_nueva>
```

Conservar CSV, contexto, resumen y comandos junto con comandos de ejecución,
auditoría de alimentación/carga, hashes de código/configuraciones/entrada/pesos,
estado del merge sin commit y verificación independiente. Comparar p95 y máximo
del total local con 100 y 250 ms; el informe incluye además max_edad_ms=300.
El recálculo debe ser idéntico. Estos tiempos no incluyen red, cámara o frenado.

Comando ejecutado para la evidencia conservada (no repetir sobre esa carpeta):

```powershell
$env:PYTHONPATH = "src"
python -B -m p5.benchmark --modo real --imagen datos/evaluacion/S2/S2_0000058828_S2_f0008.jpg --calentamientos 10 --ejecuciones 100 --salida mediciones/real_cpu_predeterminado_20261104T232545932025Z
```

Verificar sin inferencia ni sobrescritura:

```powershell
python -B scripts/recalcular_benchmark.py --mediciones mediciones/real_cpu_predeterminado_20261104T232545932025Z
```

Las [condiciones completas](../mediciones/real_cpu_predeterminado_20261104T232545932025Z/contexto.json)
y la [auditoría](../mediciones/real_cpu_predeterminado_20261104T232545932025Z/ejecucion.json)
registran CPU, versiones, proveedor, hilos, hashes y código sin commit. No se
reinterpretan los tiempos de otro equipo como mediciones locales.
El estado sin commit describe el momento de medir: el merge se completó después
en a4f25aa. Los archivos originales de esa auditoría se conservan íntegros.

## Criterios de entrega

1. Conservar la autorización específica del PM para la imagen y el benchmark;
   no extenderla a la evaluación completa de calidad.
2. Acordar una entrada representativa y un protocolo antes de medir; registrar
   ruta/hash, pesos/descriptor, umbral, NMS, CPU, hilos y commit congelados.
3. Ejecutar el modo explícito `--modo real --imagen <entrada aprobada>` en otra
   carpeta de mediciones, con pesos cuyo hash coincida exactamente con el descriptor.
   Nunca hay activación automática del modo real ni búsqueda de fotografías.
4. Conseguir 10/100 válidas con todos los fallos visibles, recalcular, comparar
   presupuestos con P5-12 y revisar las cifras con Sebastián. Documentar entrada
   fija en memoria y alcance local; no atribuir resultados al carrito completo.

El PR #88 ya está integrado y las pruebas de IDs/cortes pasan con main. El benchmark
no renumera capturas ni consume sus anotaciones. No cierra #60 solo con simulación;
requiere la evidencia real, recálculo y revisión de Sebastián.
