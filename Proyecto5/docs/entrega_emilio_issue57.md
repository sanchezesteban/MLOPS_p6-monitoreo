# Entrega histórica PR #79 — issue #57

**Informe histórico; no usar sus cinco outside_risk como conteo vigente.**
La [entrega P5-05b](entrega_emilio_p5_05b.md) describe las recapturas ya integradas
localmente: 78/20 despejados/58 obstáculos/seis fuera de riesgo y siete de ajuste.
Las aprobaciones finales están [registradas](autorizaciones_finales_p5_05b.md).
El consentimiento está completo, firmado el 2026-11-03 y con publicación GitHub autorizada. Usar Parte de #57,
no cierre automático, mientras falten dependencias o recepción de Emilio.
El contenido siguiente conserva la historia de #79, sin alterar sus evidencias.

## Selección anterior conservada: 78 cuadros de PR #79

| Secuencia | JPEG de evaluación | Despejados | Obstáculos | Fuera de riesgo |
|---|---:|---:|---:|---:|
| S1 | 12 | 12 | 0 | 0 |
| S2 | 17 | 0 | 17 | 4 |
| S3 | 13 | 0 | 13 | 1 |
| S4 | 12 | 0 | 12 | 0 |
| S5 | 12 | 0 | 12 | 0 |
| S6 | 12 | 8 | 4 | 0 |
| Total | 78 | 20 | 58 | 5 |

Evaluación: [JPEG](../datos/archivo/seleccion_78_pre_recaptura/) y [CSV](../datos/archivo/seleccion_78_pre_recaptura/capturas.csv). Ajuste: [7 JPEG S1 despejados](../datos/ajuste/S1/) y [CSV](../datos/ajuste/capturas.csv). **Quedamos exactamente en el mínimo de 20 despejados**: no retirar ni reclasificar otro negativo sin verificar de nuevo los requisitos. En aquella preparación se conservó el conjunto entonces activo; el snapshot enlazado es el respaldo previo a P5-05b.

Según [autorización expresa de Sebastián](https://github.com/sebastian0023/Proyecto-3-Clasificador-de-imagenes/pull/79#issuecomment-6610598090), se retiraron seis S1 con escena compartida con ajuste y dos con posible persona (t=3855616 y 3870350). Se recuperaron las originales de t=59719 y 66562 ms, aceptadas como C1 pese a mostrar principalmente pared. Esa solución resolvió la selección S1 del PR #79; no exime de las 54 recapturas reales ahora solicitadas para P5-05b. No se inventaron imágenes ni se duplicaron cuadros del conjunto activo.

Las ocho copias excluidas están preservadas fuera del repositorio; los originales, ZIP y respaldos previos siguen intactos. Los registros completos anteriores/nuevos, hashes, sesiones, motivos y autorización están en [procedencia](procedencia_capturas.json) y [normalización S1](normalizacion_temporal_S1.md). La selección anterior se conserva allí como historia, no como conteo vigente.

## Independencia de ajuste y alcance visual

Se conservaron sin cambios las siete imágenes de ajuste y su CSV. La escena coincidente (palo, mueble café y puerta) se eliminó de evaluación mediante las seis exclusiones identificadas visualmente por el PM; también se retiraron las dos posibles personas, sin reetiquetarlas automáticamente como fuera de riesgo. Evaluación y ajuste no comparten JPEG, hashes, frame_id ni session_id. Esta solución está autorizada por revisión visual del PM; no se presenta como prueba automática de independencia estadística total.

Ajuste usa dos sesiones originales: 7f1d45e0e669436985dc74f5443476ea (1 cuadro) y fd4c17f067da4280b15ee5657160f8d5 (6), dentro de una S1. **Solo contiene siete negativos y ningún positivo**: no permite caracterizar el ajuste de respuestas ante obstáculos positivos. No se usa evaluación para compensarlo ni se inventa una cuota adicional que #57 no exige.

S6 conserva D–D–D–D–B–B–B–B–D–D–D–D, en la misma sesión y con los mismos tiempos. No se repartieron cuadros de S6 entre conjuntos. S1 vigente conserva dos sesiones (9 y 3 cuadros) y la pausa real registrada; no se fingió continuidad. S2/S3 conservan sus reanudaciones y relojes anteriores.

Las imágenes se revisaron visualmente; no son resultados de inferencia. La metodología de estímulos 2D person/dog/cat en teléfono fue [confirmada por Sebastián](https://github.com/sebastian0023/Proyecto-3-Clasificador-de-imagenes/pull/79#issuecomment-6609398193). No son animales/personas físicamente presentes en las recapturas. Emilio debe revisar/anotar cajas y escenarios, incluidos S5 y los casos fuera de riesgo, sin convertir etiquetas humanas en detecciones ni confianzas del modelo.

## Clases acordadas y descriptor disponible en PR #80

La configuración existente [politica.yaml](../config/politica.yaml), campo clases_obstaculo, define exactamente **person, dog y cat** como clases de obstáculo, con nombres COCO y comentario de acuerdo de los PM. [Política documentada](politica.md). Se verificó esa configuración sin modificarla. El descriptor de P5-03 está disponible en el [PR #80](https://github.com/sebastian0023/Proyecto-3-Clasificador-de-imagenes/pull/80), en [Proyecto5/modelo/descriptor.yaml](https://github.com/sebastian0023/Proyecto-3-Clasificador-de-imagenes/blob/9aec7d86d172c51327bc4cd3f9633b3d4b9aca49/Proyecto5/modelo/descriptor.yaml), con las clases COCO **person=0, cat=15 y dog=16**, coincidentes con la política. **Todavía no está integrado en main**. Comprobar el descriptor no acredita la salida del detector real sobre estas fotografías.

## Metadatos y fuente de verdad

Los dos CSV mantienen once campos: sequence_id, frame_id, t_capture_ms, path, sha256, sequence_start_unix_ns, session_id, scene_label, outside_risk, image_width e image_height. path es relativo a la carpeta de su conjunto. **capturas.csv es la fuente de verdad para t_capture_ms, no los números incluidos en el nombre del JPEG.** Ordenar por sequence_id y t_capture_ms; no deducir orden por filename.

Tres S1 vigentes mantienen nombres históricos con el tiempo fuente, distinto del normalizado. Ejemplo: S1_0000032187_8e76f0bf9ada44dca0ac9ef5a47dfb82.jpg corresponde a t_capture_ms=3813428. No se renombraron JPEG ni se alteraron tiempos para igualarlos. La fórmula, residuos y registros fuente permanecen auditables. Las dos recuperadas conservan íntegros IDs, origen, tiempos originales, sesiones, etiquetas y hashes.

Verificar SHA-256 sobre bytes originales; no recodificar imágenes. Las guías del visor nunca forman parte de los JPEG. Para eventos que exijan frame_id prefijado, P5-06/P5-07 deben usar una correspondencia trazable para los UUID históricos, sin cambiar el CSV fuente. Preservar huecos de captura durante reproducción.

## Cinco ejemplos fuera de riesgo del conjunto anterior

outside_risk es independiente de la etiqueta principal. Estos cinco todavía mantienen obstaculo y outside_risk=1 en el conjunto anterior; se perderán al sustituir S2/S3. El PM debe decidir los casos reales nuevos: no heredar estas marcas. La revisión anterior usó la caja del sujeto en pantalla, no el teléfono ni reflejos.

| Fotografía | frame_id | outside_risk |
|---|---|---:|
| [S2-14](../datos/archivo/seleccion_78_pre_recaptura/S2/S2_0003452297_S2_7be3ff1ce01c41f3b29038093c363da1.jpg) | S2_7be3ff1ce01c41f3b29038093c363da1 | 1 |
| [S2-15](../datos/archivo/seleccion_78_pre_recaptura/S2/S2_0003498734_S2_feded6baa90b4d3e95cc01ca623bc200.jpg) | S2_feded6baa90b4d3e95cc01ca623bc200 | 1 |
| [S2-16](../datos/archivo/seleccion_78_pre_recaptura/S2/S2_0003510437_S2_a256771fc9fd49988bebafc788e7d57d.jpg) | S2_a256771fc9fd49988bebafc788e7d57d | 1 |
| [S2-17](../datos/archivo/seleccion_78_pre_recaptura/S2/S2_0003541250_S2_36602891e66d4e878a5ac5eb275276ea.jpg) | S2_36602891e66d4e878a5ac5eb275276ea | 1 |
| [S3-13](../datos/archivo/seleccion_78_pre_recaptura/S3/S3_0002969243_S3_ab81a14f8ab7413b8a0b77a3914a2391.jpg) | S3_ab81a14f8ab7413b8a0b77a3914a2391 | 1 |

## Vehículo, condiciones y validación histórica del PR #79

[Ficha del vehículo](ficha_auto.md): TSCINBUNY ZYC0024, ESP32-CAM, 400 × 296 y rotación 180°. Motores apagados y vehículo inmóvil en todas las capturas S1–S6, declaración confirmada personalmente por el operador; no sensores. El manual señala L298N y reductora 48:1, pendientes de corroboración de la unidad física. Velocidad inicial manual 0.545 m/s, giro aproximado 90°/0.35 s por lado; la web ofrece un único nivel sin selector, no un rango físico completo. No se solicitan videos ni nuevos giros. Los registros de ejemplo 1.80/1.83/1.84 s y 0.55 no son mediciones nuevas ni consignas reales.

El JSON original de [FPS](medicion_fps_issue57.json) conserva 48.9, 49.4 y 48.6 JPEG distintos recibidos/s en tres ventanas de 10 s, media 48.97; no FPS nominales del sensor. No se repitió contra la cámara durante esta corrección.

El [validador](../scripts/validar_capturas.py) con --issue57 **aprobó** la selección de **78 evaluación + 7 ajuste**, 20 D/58 B/5 fuera de riesgo. La revisión de integridad confirmó correspondencia exacta entre JPEG y CSV, hashes correctos, IDs únicos y conservación de los campos de los registros originales. Ruff aprobó y pytest obtuvo **258 pruebas y 53 subpruebas aprobadas** en el entorno del proyecto con Python 3.10.8; Python 3.12 no está instalado localmente y no se afirma haber ejecutado esa versión. Las pruebas no accedieron al vehículo ni abrieron ventanas reales. Las salidas y el diff se entregan para revisión. No se cambiaron reglas para forzar aprobación. El validador comprueba sesiones/hashes distintos, pero la independencia de escena se apoya en la revisión y autorización visual del PM.

## Cambios ya fusionados con PR #79; no nuevos en P5-05b

- [.github/workflows/ci.yml](../../.github/workflows/ci.yml): solo el job smoke de Proyecto2 se fijó a ubuntu-24.04, porque Playwright 1.56.1 del lockfile no admitía Ubuntu 26.04 al que pasó ubuntu-latest. Conserva pruebas, pasos y funcionalidades; no oculta fallos.
- [.gitignore global](../../.gitignore): la regla *.[zZ][iI][pP], equivalente a excluir ZIP sin distinguir mayúsculas, evita preparar paquetes temporales. No borra archivos ni reemplaza exclusiones de Proyecto5. Se debe mencionar este cambio y el anterior en la descripción del PR, como pidió el PM; no se revirtieron automáticamente.

## Estado de la selección anterior y pendientes

| Criterio | Estado/evidencia |
|---|---|
| Seis secuencias, >=60 distintos y >=10 por secuencia | Selección 12/17/13/12/12/12, 78 JPEG |
| >=20 D y >=20 B, fuera de riesgo | Exactamente 20 D, 58 B, 5 casos existentes; no perder otro D |
| Clases | person/dog/cat verificadas en politica.yaml; descriptor P5-03 disponible en PR #80 (person=0, cat=15, dog=16), aún no integrado en main |
| CSV, hashes, IDs y tiempos | --issue57 aprobado; campos originales conservados y auditables |
| Ajuste separado | Siete S1 intactas, exclusión de escena compartida autorizada por PM; cero positivos |
| Motores apagados | Cumplido por declaración confirmada del operador |
| Ficha física | Medidas aproximadas y limitaciones conservadas; L298N documental, no inspección del chip |
| Entrega a Emilio | Preparada; falta confirmación de recepción en #58 |
| Publicación de estímulos | Falta documentar procedencia/permiso de imágenes de terceros, incluido rostro señalado por PM; autorización del método no demuestra licencia |
| Revisión final | El PM revisará este nuevo diff; la aprobación anterior sobre otros conteos no sustituye comprobar la selección corregida |

La orden actual no solicita recapturar ajuste: sus siete cuadros se conservan. Sí exige las 54 fotografías reales de evaluación S2/S3/S4/S6. No cerrar #57 hasta integrar y validar la nueva selección y confirmar su entrega; usar Parte de #57 mientras tanto. No se publicaron comentarios, material ni esta preparación.

## Mensaje breve para Emilio, no publicado

> Emilio: el PM pidió recapturar S2/S3/S4/S6 con persona real en P5-05b, un PR nuevo tras el merge de #79. La selección anterior de 78 todavía se conserva, pero no es el nuevo congelado para #58/#59. Compartiremos los 78 definitivos (54 nuevos más S1/S5 conservados), CSV, hashes y procedencia tras verificar capturas, consentimiento y fuera de riesgo. Conserva tus anotaciones anteriores sin sobrescribirlas automáticamente; el COCO/manifiesto definitivo y las predicciones de #59 deberán corresponder al nuevo conjunto.
