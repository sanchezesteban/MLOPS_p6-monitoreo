# Auditoría previa a integrar P5-05b — issue #57

**Estado final posterior:** las aprobaciones S3/S4, seis sustituciones S2,
normalización/interrupción, gatos y peluche dog=16 están comunicadas por el operador.
La selección de 78 se integró localmente y validó de nuevo; ver [entrega vigente](entrega_emilio_p5_05b.md).
El contenido anterior se conserva como historial/protocolo; sus pendientes de
aprobación ya resueltos no describen el estado actual. Consentimiento completo: firma 2026-11-03 y alcance GitHub confirmados.

**Autorizaciones vigentes comunicadas por el operador:** S2 interrumpida/normalizada
y gatos reales aceptados; peluche dog=16 aceptado. Los seis adicionales están
al final. Los encuadres y sustituciones ya están aprobados; el consentimiento
está completo, firmado el 2026-11-03. Quedan coordinación de cortes/IDs, entrega
a Emilio y la limitación sobre motivos históricos individuales no documentados.
Ver [selección actual](seleccion_78_p5_05b.md).
Las observaciones/rechazos anteriores de esta auditoría se conservan como historial.

**Actualización temporal posterior:** el candidato privado normalizado aprueba
--issue57 con 78/20D/58B y seis fuera de riesgo; [evidencia y pendientes PM](normalizacion_temporal_S2_p5_05b.md).
Los rechazos temporales indicados abajo describen la propuesta anterior sin normalizar.
La evaluación activa y las fuentes no se modificaron.

**NO APROBADO para integración definitiva ni publicación.** Ver también
[revisión de las capturas adicionales](auditoria_fuera_riesgo_p5_05b.md).
**Actualización:** el PM autorizó el perro de peluche como dog=16. El tipo de
estímulo debe declararse y no implica animal real; ver [convención vigente](autorizacion_estimulo_dog_p5_05b.md).
Sin nuevas capturas realizadas por el agente,
inferencias del detector, cambios de etiquetas, commit, push ni PR durante la auditoría.

Fuente privada: `%LOCALAPPDATA%/P5-57/recaptura_persona_v2/20261103_212659/`.
Se respaldaron íntegros los 54 JPEG, CSV de 58 filas y ZIP disponible de 57 JPEG.
El informe privado, manifiestos, comparaciones y candidato se localizan mediante
`Proyecto5/resultados/auditoria_recaptura/ubicacion.json` (ignorado por Git).
No publicar ese resguardo ni las hojas de contacto con personas sin autorización.

## Cantidades y contenido observado manualmente

| Secuencia | JPEG | CSV | Personas | Gatos | Peluches | Despejados |
|---|---:|---:|---:|---:|---:|---:|
| S2 | 17 | 17 | 9 | 4 | 4 | 0 |
| S3 | 13 | 15 | 4 | 5 | 4 | 0 |
| S4 | 12 | 14 | 4 | 4 | 4 | 0 |
| S6 | 12 | 12 | 0 | 0 | 4 | 8 |
| Total | 54 | 58 | 17 | 13 | 16 | 8 |

Conteos visuales orientativos; no son anotaciones COCO ni inferencia automática.
Los animales oscuros/parciales se revisan con su contexto y declaración del operador.

## CSV y trazabilidad

Faltan S3_f0004 (20891 ms), S3_f0005 (22922 ms), S4_f0002 (13750 ms) y
S4_f0008 (208203 ms). Los cuatro JPEG siguen dentro del ZIP y sus SHA-256
coinciden con el CSV. El estado actual más el ZIP conservan las 58 capturas
registradas; S2_f0017 no está en el ZIP de 57, sí en la carpeta/CSV actuales.

El operador declaró eliminación manual de sobrantes; falta el criterio individual
y confirmar si hubo selección por detector. No se inventó fecha ni motivo específico.
Se preparó un CSV privado de 54 filas retirando solo las cuatro ausentes, sin
modificar los bytes de las filas conservadas. **No se aplicó al original.**
Se mantienen los huecos en numeración; no renombrar ni renumerar para ocultarlos.
S2 conserva tres sesiones y S3 dos; los tiempos reales y pausas permanecen.
No describirlo como captura única de exactamente 54 cuadros sin exclusiones.

## Hallazgos pendientes de PM y consentimiento

- El PM autorizó el perro de peluche como dog=16 para el dataset, sin presentarlo
  como animal real. No se cambió la etiqueta principal ni el esquema del CSV.
  Los gatos reales fueron aceptados posteriormente por el PM; sus encuadres siguen pendientes.
- S3/S4 muestran sujetos cortados por bordes. PM/anotador deben resolver si
  cumplen «completo» y revisar que ninguna parte de la caja toque el centro.
  S3_f0013 parece llegar/cruzar W/3 con torso/brazo; margen pendiente de medir.
- S6 conserva D×4–B×4–D×4. Los cuatro B son el perro de peluche ahora autorizado
  como dog=16; esa variación ya no es un bloqueo. No se retiraron ni reordenaron.
- Los ocho D de S6 tienen hashes distintos y diferencias de encuadre visibles;
  SSIM exploratorio entre sus pares: 0.516498–0.812190. No se detectó casi
  duplicado con el criterio exploratorio privado; no se afirma independencia estadística.
- Once pares similares del conjunto se señalan para revisión, principalmente
  S2/S3. No se borró nada ni se añadió un umbral nuevo al contrato.
- Cero outside_risk; todos los sujetos observados alcanzan la mitad inferior.
  Este dato corresponde al principal de 54: los seis adicionales sí están fuera
  de riesgo y autorizados, y su unión normalizada ya fue aceptada por el PM; el candidato se conserva.
- Bandas horizontales y escenas oscuras visibles; JPEG decodificables, origen
  del defecto no determinado. No se corrigieron píxeles.
- En esta revisión inicial faltaban fecha y alcance del consentimiento. Después
  el operador confirmó firma el 2026-11-03 y publicación GitHub; ver
  [constancia completa](consentimiento_recaptura_issue57.md). El firmado permanece privado.

## Candidato privado y validaciones

Se preparó una copia privada de 78 para simular la sustitución: S1/S5 intactos,
54 nuevos conservados y siete de ajuste. No se cambió el conjunto activo ni el
archivo histórico de 84/78. Las etiquetas originales suman 20 D y 58 B; esto no
certifica 58 obstáculos reales de las clases acordadas.

- 54/54 JPEG de 400×296 con SHA correcto; 58 IDs CSV únicos y patrón prefijado válido.
- Tiempos estrictamente crecientes y origen estable por secuencia; sin retoques.
- Cero duplicados exactos, cero JPEG huérfanos; cuatro referencias ausentes en fuente.
- Candidato: integridad aprobada; `--issue57` **rechazado por cero fuera de riesgo**.
  El validador no certifica clases, encuadre, consentimiento ni aprobación del PM.
- Evaluación/ajuste candidato sin hashes, IDs ni sesiones compartidos; escenas
  nuevas de cama/puerta visualmente distintas del ajuste de baldosas/mueble.
- Conjunto activo anterior: `--issue57` aprobado, sin alterar sus JPEG/CSV.
- Pytest: **276 pruebas y 53 subpruebas aprobadas**; Ruff check/format aprobados.
  Python 3.10.8, sin vehículo; no se afirma ejecución de Python 3.12.

Antes de integrar: resolver encuadres, integración temporal, selección y
consentimiento; luego actualizar CSV/procedencia/documentación, congelar hashes
y entregar a Emilio. #59 debe usar el nuevo conjunto congelado y predicciones
correspondientes. No se modificaron archivos de Emilio/Edith ni métricas.
