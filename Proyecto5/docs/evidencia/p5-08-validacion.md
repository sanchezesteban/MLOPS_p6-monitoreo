# P5-08 — validación y preparación de medición real, 2026-11-04

## Correcciones del PR #90

Se integró main `5a38de810cf2760cd6b1f28921fbf453ea029a33`, que incluye el
[PR #88](https://github.com/sebastian0023/Proyecto-3-Clasificador-de-imagenes/pull/88).
Al medir, el merge local estaba sin commit por instrucción del operador. Se
completó para publicar en **a4f25aa1630d7657d6180526b5195508be9f89ba**, sin
conflictos. Los cambios de COCO, manifiesto, recorrido y otros módulos
proceden de main; no se editaron manualmente para esta corrección del benchmark.

Tres observaciones atendidas:

1. Base actualizada: la suite ya no presenta el fallo antiguo S2_f0001/S2_f0007.
2. Hilos: sin --hilos se crea exactamente la sesión de DetectorONNX, con
   CPUExecutionProvider y sin SessionOptions. Se registran modo, opciones efectivas
   y proveedor en contexto/resumen. --hilos N queda como experimento distinto con
   advertencia de que no es directamente comparable con el recorrido.
3. CPU: modelo real y fuente de consulta; sysctl y alternativa de hardware Apple
   Silicon en macOS, registro de Windows y /proc/cpuinfo en Linux. No se acepta
   una arquitectura como modelo. El equipo local informa
   **13th Gen Intel(R) Core(TM) i7-13650HX**, mediante ProcessorNameString.

Validación con Python 3.12.16, en un entorno externo sin modificar el entorno
anterior. No se modificaron dependencias, detector_onnx.py ni YAML congelados.

| Comprobación | Resultado ejecutado |
|---|---|
| Suite completa después de integrar main, antes de las correcciones | 484 aprobadas, nueve omitidas |
| Pruebas propias después de corregir | **58 aprobadas** (35 originales y 23 regresiones) |
| Suite completa con las correcciones | **507 aprobadas, nueve omitidas** |
| Suite completa posterior a la medición, con pesos disponibles | **516 aprobadas, ninguna omitida** |
| Ruff check | **Aprobado** |
| Ruff format --check | **89 archivos conformes** |

Las nueve omisiones de la comprobación inicial eran pruebas del detector/recorrido
con pesos ausentes; las nueve pasaron después de disponer del modelo verificado.
Las 58 pruebas del benchmark se repitieron tras medir: todas pasaron. Sus nuevas
regresiones usan sesiones falsas y cubren hilos, CLI, persistencia en ambos JSON,
recálculo, CPU de tres sistemas y fallos/timeouts de las consultas.

## Corridas reales autorizadas: completadas

La imagen autorizada coincide con SHA-256
`98c6d6431d0bd1a44ca6c69790344f4f21b3cc8c647b2b6f0495fbf9f8e5e8b7`;
los pesos disponibles fuera del repositorio coinciden con
`c789161ed43c8269fcd4e67c67eeeb4e80c622da2eb296a20bc6007bd18a0b7d`.

Se reanudó después de conectar el equipo. Windows confirmó ACLineStatus=1 antes
y después de ambas corridas. La carga previa del ensayo fue 3,69 %; la de la corrida
definitiva, 4,61 %, sin procesos que superaran el criterio registrado. Son muestras
previas de carga, no una certificación de reposo absoluto durante toda la medición.
La comprobación anterior en batería detuvo el trabajo: no se midió en batería.

- **Ensayo privado / NO EVIDENCIA FINAL**, 23:25:04 UTC: tres calentamientos y diez
  mediciones válidas, 13 intentos y cero fallos. Total local p50=15,281450 ms,
  p95=17,233920 ms, máximo=17,676900 ms. Carpeta externa separada de simulaciones
  y del resultado definitivo. Su recálculo coincide byte por byte.
- **Definitiva**, inicio 2026-11-04 23:25:45,933 UTC, fin 23:25:49,496 UTC:
  **10 calentamientos excluidos + 100 mediciones válidas; 110 intentos, cero
  fallos y cero reintentos**. No se descartaron mediciones lentas ni se repitió
  la corrida para mejorar cifras.

Evidencia: [real_cpu_predeterminado_20261104T232545932025Z](../../mediciones/real_cpu_predeterminado_20261104T232545932025Z/).
CPU Intel Core i7-13650HX, 20 procesadores lógicos; Windows 11 10.0.26300;
Python 3.12.16, ONNX Runtime 1.30.0 y NumPy 2.5.3. CPUExecutionProvider con sesión
predeterminada, sin --hilos ni variables OMP/MKL/OPENBLAS. Intra/inter=0 son
valores automáticos de ORT; no indican un número fijo de hilos trabajadores.

Resultados en ms, redondeados solo para lectura; CSV y JSON conservan los valores:

| Etapa | p50 | p95 | Máximo |
|---|---:|---:|---:|
| Preprocesamiento | 2,565 | 3,015 | 3,170 |
| Inferencia | 8,828 | 10,445 | 14,623 |
| Posprocesamiento | 3,444 | 4,663 | 5,224 |
| Política + adaptador | 0,918 | 1,375 | 4,827 |
| **Total local** | **15,868** | **19,196** | **22,058** |

| Plazo | p95 total | Margen p95 | Máximo total | Margen máximo |
|---|---:|---:|---:|---:|
| 100 ms | 19,196 | 80,804 | 22,058 | 77,942 |
| 250 ms | 19,196 | 230,804 | 22,058 | 227,942 |

Ambas medidas caben en ambos plazos; también se registra el contraste con 300 ms.
Esto no certifica seguridad física: el total excluye red, cámara y frenado, lectura
inicial de imagen, carga del modelo y escritura de los informes. La etapa política
incluye validación, watchdog y adaptador virtual con JSONL/flush; no acciona motores.
No se midió calidad sobre las 78 fotografías ni se alteraron umbral, NMS o pesos.

El [resumen](../../mediciones/real_cpu_predeterminado_20261104T232545932025Z/resumen.json)
y su recálculo son **idénticos byte por byte**. Una comprobación adicional con
biblioteca estándar recalcula los percentiles desde las 100 filas válidas del CSV
sin importar el módulo del benchmark; coincide con tolerancia absoluta 1e-12 ms.
Los cinco archivos de salida se acompañan de comando, auditoría del equipo,
verificación independiente, parche exacto del código no confirmado y hashes.

El contexto conserva HEAD=e3530d6 porque se solicitó no crear commits. La auditoría
registra main integrado=5a38de8, merge pendiente y SHA-256 del código realmente
ejecutado; el parche permite reconstruir sus cambios. No atribuir estas mediciones
al árbol limpio de e3530d6. Estos metadatos describen el instante de medición y
se conservan sin reescribirlos al publicar. El PR #90 se mantiene en Draft y
usa «Parte de #60», sin cierre automático.

## Verificación de publicación sin inferencia adicional

Con autorización del operador se concluyó el merge y se preparó un commit separado
de correcciones/evidencia. Se repitieron **58 pruebas del benchmark** y la suite
de software: **507 aprobadas, nueve excluidas**. Las nueve son el módulo
test_detectar_real.py y test_recorrido_real_una_imagen_de_s1, que podrían crear
sesiones reales; se excluyeron expresamente para no ejecutar nueva inferencia.
Además se bloqueó la creación de sesiones ONNX reales durante las pruebas de
publicación; las pruebas propias conservan sus sesiones falsas. No se modificaron
pruebas de otros módulos ni resultados esperados para lograr la aprobación.

Ruff check y format --check aprobados (90 archivos). El script de recálculo
volvió a coincidir, sin inferencia ni escritura de nuevas mediciones. Los 13
hashes del archivo de evidencia y los 91 del congelado de datos se verificaron.
La suite completa de **516 aprobadas** de la tabla corresponde a la ejecución
anterior con pesos disponibles, no a una repetición durante esta publicación.

## Registro de la preparación inicial (histórico)

Las cifras y el fallo indicados a continuación describen el commit e3530d6 y su
base anterior; no son el estado de la suite después de integrar main.

Rama `p5-08-benchmark`, base `d862050`. No se incorporan los commits de la rama
de métricas #59. Los archivos anteriores del repositorio se conservan intactos;
se agregan solamente el benchmark, recálculo, pruebas y documentación propios.

### Método revisado

- [Referencia P4](../../../Proyecto4/recursos/medir_recursos.py): calentamientos,
  cronómetro y percentiles lineales. Se documenta por qué no se puede importar
  directamente su clasificador/`resource` en el nuevo runtime P5 de Windows.
- P5-04: se reutilizan letterbox y posprocesamiento; la sesión futura se prueba
  con `SesionFalsa`, sin ejecutar ONNX ni descargar pesos.
- P5-12/P5-14: política/watchdog/adaptador virtual existentes, sin sleeps de
  reproducción, y contraste contra los plazos configurados de 100/300/250 ms.
  No se cambian configuraciones ni IDs de otros integrantes.

### Pruebas y evidencia

Entorno externo **Python 3.12.16**, con dependencias base/captura/datos existentes;
el entorno original no se modifica. Ruff check/format aprobados (83 archivos).
Pruebas del módulo: **35 aprobadas**. Suite completa desde Proyecto5:
**423 aprobadas, 1 fallida y 10 omitidas**; el fallo previo se detalla abajo.

Las pruebas nuevas cubren exclusión de calentamientos, 100 éxitos, fallos por
etapa/calientamiento, límite de intentos, interrupción y cierre, no sobrescritura,
integridad de CSV/contexto, recálculo, plazos, pesos/hilos mediante sesión falsa
y uso de las interfaces reales de política y adaptador virtual.

Casos de percentiles calculados a mano: `[0,10]` → p50=5, p95=9.5, máximo=10;
`1..100` → p50=50.5, p95=95.05, máximo=100. Los valores de estos casos son
**datos sintéticos de prueba**, no latencias del detector.

La primera ejecución de integración reveló un error del código nuevo: cajas
`tuple` no serializadas como arrays antes de validar el evento. Quedó corregido
y cubierto por una regresión que exige cero fallos y comandos para el obstáculo.
No se ocultan los registros previos privados ni se reutilizan como resultado final.

La CLI simulada corregida completa **110 intentos: 10 calentamientos válidos y
100 mediciones válidas, cero fallos**. El script reconstruye exactamente el
JSON desde los CSV y el contexto. CSV, contexto y resumen están identificados
como `SINTETICA_NO_MIDE_DETECTOR_REAL`, en una carpeta temporal externa.
No se publican sus percentiles como evidencia de desempeño del detector.

La suite P5 conserva un fallo previo de P5-14:
`tests/test_recorrer.py:288` espera S2_f0001, pero el CSV vigente empieza con
S2_f0007. Se deja visible, sin modificar la prueba o las capturas. Diez pruebas
se omiten: nueve por pesos ausentes (sin inferencia real) y una por falta de
congelado COCO. Se verificaron por hash los 1117 archivos anteriores del
repositorio: ninguno cambió. La rama de #59 permanece en `5ad4982`.

### Cierre pendiente al preparar la simulación (histórico)

Este avance cubre el programa y su verificación con simulación. Faltan permiso
del PM para inferencia, entrada/protocolo representativos acordados, pesos y
configuración congelados, corrida real 10/100 en el equipo documentado,
recálculo y revisión de Sebastián del contraste de plazos. Las métricas de
calidad y las anotaciones de Emilio son trabajo aparte y no se ejecutan aquí.

Ver [comandos y alcance](../benchmark.md) y [estructura de mediciones](../../mediciones/README.md).
