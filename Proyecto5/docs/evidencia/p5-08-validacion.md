# P5-08 — preparación y validación simulada, 2026-11-04

Rama `p5-08-benchmark`, base `d862050`. No se incorporan los commits de la rama
de métricas #59. Los archivos anteriores del repositorio se conservan intactos;
se agregan solamente el benchmark, recálculo, pruebas y documentación propios.

## Método revisado

- [Referencia P4](../../../Proyecto4/recursos/medir_recursos.py): calentamientos,
  cronómetro y percentiles lineales. Se documenta por qué no se puede importar
  directamente su clasificador/`resource` en el nuevo runtime P5 de Windows.
- P5-04: se reutilizan letterbox y posprocesamiento; la sesión futura se prueba
  con `SesionFalsa`, sin ejecutar ONNX ni descargar pesos.
- P5-12/P5-14: política/watchdog/adaptador virtual existentes, sin sleeps de
  reproducción, y contraste contra los plazos configurados de 100/300/250 ms.
  No se cambian configuraciones ni IDs de otros integrantes.

## Pruebas y evidencia

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

## Cierre pendiente

Este avance cubre el programa y su verificación con simulación. Faltan permiso
del PM para inferencia, entrada/protocolo representativos acordados, pesos y
configuración congelados, corrida real 10/100 en el equipo documentado,
recálculo y revisión de Sebastián del contraste de plazos. Las métricas de
calidad y las anotaciones de Emilio son trabajo aparte y no se ejecutan aquí.

Ver [comandos y alcance](../benchmark.md) y [estructura de mediciones](../../mediciones/README.md).
