# Entrega para Emilio — selección P5-05b / issue #57

**Dataset definitivo de fotografías integrado localmente y aprobado por el PM.**
No se confirma recepción de Emilio. [Consentimiento completo](consentimiento_recaptura_issue57.md):
firma real 2026-11-03 y autorización expresa para publicar en GitHub.
Usar **Parte de #57**, no cierre automático: siguen dependencias y recepción.

| Secuencia | JPEG | Despejado | Obstáculo (etiqueta CSV) | outside_risk |
|---|---:|---:|---:|---:|
| S1 | 12 | 12 | 0 | 0 |
| S2 | 17 | 0 | 17 | 6 |
| S3 | 13 | 0 | 13 | 0 |
| S4 | 12 | 0 | 12 | 0 |
| S5 | 12 | 0 | 12 | 0 |
| S6 | 12 | 8 | 4 | 0 |
| Total | 78 | 20 | 58 | 6 |

Entradas: [evaluación y JPEG](../datos/evaluacion/),
[CSV evaluación](../datos/evaluacion/capturas.csv),
[ajuste independiente](../datos/ajuste/) y [CSV ajuste](../datos/ajuste/capturas.csv).
Ajuste conserva siete negativos S1, dos sesiones, ningún positivo; no se trasladó
ninguna imagen entre conjuntos. [SHA de 85 JPEG y dos CSV](../datos/HASHES_p5_05b.sha256).
Este manifiesto identifica imágenes/CSV; aún no es el congelado COCO del #58.

## Anotar sin ver detecciones

Emilio debe anotar los 78 JPEG directamente, **sin consultar predicciones,
confianzas, aciertos ni errores del detector**. No se ejecutó inferencia en esta tarea.
El paquete privado preparado contiene imágenes/CSV/correspondencias de captura;
no incluye detecciones ni cajas sugeridas. Las hojas con flechas del PM son
historia de revisión, no GT ni instrucciones de cajas. No se fabricaron COCO o cajas.

Clases acordadas: **person=0, cat=15, dog=16**, declaradas en categories del COCO.
Dog incluye el **perro de peluche autorizado**, identificado como peluche, no perro real.
Gatos reales y encuadres S3/S4 están aprobados por el PM; ver
[autorizaciones](autorizaciones_finales_p5_05b.md) y [guía de estímulos](correspondencia_estimulos_dog_p5_05b.csv).
La etiqueta scene_label/outside_risk no es una predicción ni reemplaza el dibujo humano
completo de todas las cajas, incluidos sujetos fuera de riesgo.

## Procedencia e IDs

[78 seleccionadas](seleccion_78_p5_05b.csv),
[exclusiones/sustituciones](exclusiones_sustituciones_p5_05b.csv),
[justificación](seleccion_78_p5_05b.md),
[fuentes CSV originales](../datos/archivo/recaptura_v2_metadatos/README.md),
[correspondencia S2](correspondencia_normalizacion_S2_p5_05b.csv).
S1/S5 se conservaron; 48 nuevas de la fuente principal más seis adicionales
sustituyeron las 54 anteriores S2/S3/S4/S6. Los cuatro descartes manuales históricos
siguen documentados con motivo individual desconocido, sin inventar causas.
El PM aprobó las seis sustituciones, sin seleccionar cuadros por rendimiento.

La normalización S2 está aprobada: diferencia de orígenes 77:28.4999786,
pausa desde el último principal 30:17.0399786. Cuatro sesiones auténticas,
seis adicionales al final (alias f0018–f0023). El CSV es fuente temporal de verdad,
no el nombre histórico del JPEG. No se cambiaron bytes ni metadatos de origen.

Antes de congelar COCO/manifiesto, coordinar la
[correspondencia entre consumidores](compatibilidad_ids_consumidores_p5_05b.csv):
P5-06 consultado renumera por posición y P5-14 conserva los IDs prefijados;
38 diferencias. Unir por fuente/sesión/ruta/SHA y conservar frame_id de origen.
[Propuesta y mensaje a responsables](propuesta_reproductor_cortes_p5_05b.md).

## Orden de integración

1. Consentimiento de publicación completo, firmado el 2026-11-03; conservar el documento privado.
2. Coordinar IDs y cortes sin renumerar la captura fuente ni modificar algoritmos ajenos.
3. Emilio anota a ciegas y congela COCO/manifiesto y sus hashes sobre esta selección.
4. Registrar configuración efectiva congelada del detector: pesos, descriptor,
   umbral, NMS, runtime y commit. Solo entonces ejecutar inferencia.
5. #59 consume anotaciones y predicciones del mismo congelado. Confirmar recepción.

## Validación final ejecutada

--issue57 aprobado sin errores; pytest **287 pruebas y 53 subpruebas**;
Ruff check y format --check aprobados (44 archivos). Python 3.10.8, sin cámara,
motores ni detector. SHA 85/85 correctos; CSV/JPEG emparejados, IDs/hashes únicos,
tiempos crecientes, cero huérfanos y sin hashes/IDs/sesiones compartidos con ajuste.
[Resumen verificable](estado_final_p5_05b.json). No se afirma prueba local Python 3.12.
