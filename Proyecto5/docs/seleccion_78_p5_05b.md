# Selección auditable de 78 fotografías — P5-05b

**Selección integrada localmente, aprobada por el PM y validada; no publicada.** La autorización
de Sebastián, comunicada por el operador, acepta S2 interrumpida y normalizada
como S1, con sus seis adicionales al final; acepta gatos reales y el perro de
peluche como dog=16, aclarando su naturaleza. Los encuadres S3/S4 y las seis sustituciones S2 fueron aprobados expresamente después;
[registro de autorizaciones](autorizaciones_finales_p5_05b.md).
No se inventan fecha ni enlace de la aprobación.

## Reconstrucción de la selección

| Paso | Conservados/incorporados | No seleccionados en esta fase |
|---|---:|---:|
| Evaluación anterior de 78: conservar S1=12 y S5=12 por instrucción PM | 24 | 54 antiguos de S2/S3/S4/S6 que serán sustituidos |
| CSV principal de recaptura: 58 registros auténticos | 54 con JPEG presentes | 4 eliminados manualmente por el operador antes de esta auditoría |
| Mantener cuota S2=17 e incorporar seis fuera de riesgo | 48 de los 54 principales | 6 principales S2 de la propuesta anterior |
| Incorporar los seis adicionales fuera de riesgo autorizados | 6 | 0 adicionales |
| **Selección candidata: 24 + 48 + 6** | **78** | **64 del universo de 142 registros de esta fase** |

No sumar los archivos históricos de 84/78 como nuevas capturas. Sus copias
verificables siguen intactas. El universo de esta tabla es evaluación anterior
78 + principal 58 + adicionales 6. Los cuatro ausentes de la carpeta principal
siguen verificables en el ZIP original. No se borró, movió o recuperó sobre las
fuentes ninguna fotografía durante esta preparación.

La [lista de las 78](seleccion_78_p5_05b.csv) incluye todos los campos finales y
su fuente, ID/ruta/tiempos originales. La
[lista de 64 exclusiones y sustituciones](exclusiones_sustituciones_p5_05b.csv)
identifica cada registro, hash, sesión, motivo conocido y lugar lógico de resguardo.
Las seis sustituciones tienen además [correspondencia temporal](correspondencia_normalizacion_S2_p5_05b.csv).
Un ID derivado no es una captura nueva ni una sesión reasignada.

## Motivos documentados y límites de la evidencia

1. **54 anteriores S2/S3/S4/S6:** cambio de protocolo dispuesto por el PM porque
   el estímulo en teléfono representaba la pantalla, identificada como tv.
   Esa observación global motivó la recaptura; no se usó para puntuar o seleccionar
   individualmente los nuevos cuadros. S1/S5 se conservan por instrucción expresa.
2. **Cuatro exclusiones manuales:** S3_f0004 (20891 ms), S3_f0005 (22922 ms),
   S4_f0002 (13750 ms) y S4_f0008 (208203 ms). El único motivo histórico comunicado
   es «eliminación de sobrantes». **No se conoce el motivo individual** y no se
   inventa que fueran borrosas, duplicadas, mal encuadradas o mal detectadas.
   Queda solicitada al operador confirmación del criterio y de que no consultó
   predicciones para eliminarlas. Una revisión visual posterior no reemplaza ese dato.
3. **Seis sustituciones S2:** se mantiene exactamente la propuesta ya construida:
   principales f0001–f0006, primeros seis por t_capture_ms, sustituidos por los seis
   adicionales revisados fuera de riesgo. La regla es explícita y determinista,
   conserva S2=17 y proporciona ejemplos fuera de riesgo. No implica que los seis
   principales fueran inválidos ni que el detector hubiera fallado en ellos.
   No se buscaron combinaciones alternativas para mejorar métricas.

La auditoría/construcción de este candidato **no utilizó predicciones, confianza,
aciertos ni errores del detector**: no se ejecutó inferencia ni se consultaron
salidas para elegir cuadros. Se revisaron JPEG, CSV, hashes, geometría, sesiones
y autorizaciones. **No se puede certificar retrospectivamente el criterio de las
cuatro eliminaciones manuales sin la confirmación del operador.** Esta limitación
es parte de la trazabilidad, no una autorización para rehacer la selección.

## Criterios visuales y decisiones del PM

- S2: estímulo central en riesgo y seis ejemplos fuera de riesgo; estos últimos
  muestran peluche autorizado como dog, con y2 visualmente por encima de 148.
  Emilio verificará el contorno al anotar; no se fabricaron cajas COCO.
- S3/S4: cuerpo completo dentro del tercio lateral, con margen; ninguna caja
  puede tocar el centro. [Revisión individual, posteriormente aprobada](revision_encuadres_S3_S4_p5_05b.md)
  de 13 S3 y 12 S4. No se retiró ningún cuadro por esta revisión.
- S6: D×4–B×4–D×4, cuatro B con perro de peluche autorizado, sin modificar orden.
- Gatos reales: aceptados por el PM; la aceptación de clase no aprueba por sí sola
  recortes, visibilidad ni invasión de zonas.
- Dog=16 incluye exclusivamente el estímulo de perro de peluche autorizado,
  documentado como tal; no se afirma que sea un perro real.

Resultado conservado: S1=12, S2=17, S3=13, S4=12, S5=12, S6=12;
20 despejadas, 58 obstáculos según CSV y seis fuera de riesgo. Ajuste: siete
negativos S1, sin positivos. No hay inferencia que certifique las clases de todos
los cuadros. La aprobación de encuadres se registra como decisión del PM, no como predicción ni nueva medición de cajas.

## Anotación ciega y validaciones

Emilio debe recibir JPEG y correspondencias del congelado aprobado, **sin
predicciones ni confianzas**. Las hojas con flechas son evidencia para el PM,
no cajas sugeridas para el COCO. Primero anotar y congelar COCO/manifiesto y
selección; después congelar configuración del detector y ejecutar inferencia.
Registrar hashes de pesos, descriptor/configuración efectiva (incluidos umbrales
y NMS), runtime, commit y datos. #59 evaluará esas entradas coincidentes.

El dataset integrado es idéntico al candidato privado validado. Se ejecutaron de nuevo
--issue57 (aprobado), pytest (287 pruebas y 53 subpruebas), Ruff check y format
(aprobados, 44 archivos examinados por format), sobre la integración definitiva.
Los 85 hashes coinciden, no hay huérfanos ni duplicados, y se conserva orden temporal.
Ver [resumen final](estado_final_p5_05b.json).

Las seis sustituciones S2 y los encuadres S3/S4 ya están aprobados. El motivo
individual de las cuatro eliminaciones manuales sigue sin documentarse; se conserva
esa limitación sin inventar causas ni atribuirlas al detector. Los dos CSV fuente
íntegros están en [metadatos históricos](../datos/archivo/recaptura_v2_metadatos/README.md).
No se ejecutó inferencia para seleccionar, descartar o validar etiquetas.

Pendientes externos: [compatibilidad del reproductor/IDs](propuesta_reproductor_cortes_p5_05b.md),
COCO/manifiesto, congelado del detector y recepción de Emilio. El
[consentimiento](consentimiento_recaptura_issue57.md) está completo, firmado el 2026-11-03.
