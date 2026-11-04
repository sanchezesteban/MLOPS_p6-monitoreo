# P5-05b: Recaptura real S2, S3, S4 y S6

Parte de #57.

El protocolo anterior usaba estímulos mostrados en un teléfono, que podía ser
identificado como tv. Se sustituyen S2/S3/S4/S6 por 54 fotografías seleccionadas
de persona, gatos reales y perro de peluche autorizado como dog=16. S1/S5 mantienen
24 JPEG anteriores. El PR #79 ya fusionado conserva su historial.

## Selección y autorizaciones

78 JPEG de evaluación: S1=12, S2=17, S3=13, S4=12, S5=12, S6=12;
20 despejadas, 58 obstáculos según CSV y seis outside_risk. Ajuste independiente:
siete negativos S1, sin positivos. No hay resultados de detección en estos conteos.

Sebastián aprobó encuadres S3/S4, seis sustituciones S2, normalización/interrupción
documentada, gatos reales y peluche dog=16, explicitando que es peluche. Las
autorizaciones fueron comunicadas por el operador; no se inventan enlaces ni fechas.

- [Selección y motivos](seleccion_78_p5_05b.md), cuatro eliminaciones manuales con
  motivo individual no documentado y seis sustituciones S2 trazables.
- [Normalización S2](normalizacion_temporal_S2_p5_05b.md): origen a origen
  77:28.4999786, pausa entre cuadros 30:17.0399786; originales/sesiones/residuos
  conservados. Seis adicionales al final, alias derivados únicos f0018–f0023.
- [Fuentes/histórico](../datos/archivo/README.md): 84 de 021550e, 78 de bd1ff9e,
  CSV originales de recaptura y SHA, sin reconstrucción por aproximación.
- Capturador con IDs consecutivos y prueba OpenCV con importorskip;
  herramienta de normalización auditable y pruebas de regresión.

## Validación sobre el dataset integrado

Python 3.10.8: --issue57 aprobado; pytest 287 pruebas y 53 subpruebas;
Ruff check y format --check aprobados. 85 hashes correctos, cero huérfanos,
IDs y hashes únicos, tiempos crecientes y ajuste separado. No se ejecutó detector
ni se alteraron las reglas del validador. Python 3.12 no ejecutado localmente.

## Dependencias y publicación

**Consentimiento completo: firmado el 2026-11-03 y publicación GitHub autorizada.**
La autorización expresa de publicación GitHub está confirmada por el operador,
quien declara ser la persona fotografiada y mayor de edad. El firmado permanece
privado fuera de Git; no se publica información personal.

P5-06/P5-14 deben coordinar IDs y reconocimiento de cortes; se aporta tabla de 78
correspondencias y sidecar de tres cortes S2, sin modificar sus módulos.
Emilio anotará sin detecciones. Después se congelarán COCO/manifiesto y configuración
del detector antes de inferencia. Entrega/recepción aún no confirmadas; #59 intacto.
Las limitaciones físicas ya documentadas del controlador/rangos no se dan por medidas.
[Entrega y pendientes](entrega_emilio_p5_05b.md). No configurar el cierre automático del issue.
