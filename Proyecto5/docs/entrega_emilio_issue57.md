# Datos propuestos para Emilio — P5-05 / issue #57

Título previsto del PR: **P5-05: Capturas reales ESP32-CAM, secuencias y ficha del vehículo**. Referencia prevista: Closes #57, solo al completar criterios y aprobar revisión. No se creó PR ni se confirmó entrega/recepción.

| Secuencia | JPEG de evaluación | Despejados | Obstáculos | Fuera de riesgo |
|---|---:|---:|---:|---:|
| S1 | 18 | 18 | 0 | 0 |
| S2 | 17 | 0 | 17 | 4 |
| S3 | 13 | 0 | 13 | 1 |
| S4 | 12 | 0 | 12 | 0 |
| S5 | 12 | 0 | 12 | 0 |
| S6 | 12 | 8 | 4 | 0 |
| Total | 84 | 26 | 58 | 5 |

Evaluación: [JPEG](../datos/evaluacion/) y [CSV](../datos/evaluacion/capturas.csv). Ajuste: [7 JPEG S1 negativos](../datos/ajuste/S1/) y [CSV](../datos/ajuste/capturas.csv), sesiones/hashes distintos de evaluación. Sin reutilizar cuadros. Los seis positivos antiguos de ajuste S2 eran cajas y se retiraron; el contrato permite una sola secuencia de ajuste. Confirmar independencia real del episodio: el entorno doméstico se parece y solo disponer de otra session_id no certifica independencia estadística.

El ajuste contiene **siete negativos S1 y ninguna imagen positiva**. Cumple el número permitido de secuencias, pero no permite comprobar ni ajustar el comportamiento ante obstáculos positivos; no se reutilizan imágenes de evaluación para compensarlo.

Se conservaron 18 S1 originales y se reemplazaron completamente los 53 S2–S6 históricos por 66 recapturas. Hay 5 objetos fuera de riesgo. Un registro S2 pasó pendiente→obstaculo por perro inequívoco en pantalla; outside_risk siguió 1. Fuentes originales y material descartado respaldados externamente, excluidos del PR. [Trazabilidad](procedencia_capturas.json).

Inspección visual humana de todos los cuadros seleccionados: nuevos sujetos person/dog/cat representados en teléfono, procedimiento autorizado por el PM según el operador. Las guías de revisión se dibujaron en copias externas, no en los JPEG. No se certificaron detecciones, confianzas ni cajas anotadas. S3/S4 se revisaron respecto al sujeto, no el marco del teléfono; S5 muestra varios sujetos simultáneos, con ocupación visual de los tres tercios. Emilio debe confirmar cajas y escenarios con anotaciones; el detector real corresponde a P5-03.

S6 conserva D–D–D–D–B–B–B–B–D–D–D–D por tiempo real en una sesión. S1 conserva cuatro sesiones y pausas de su normalización previa; S2/S3 también incluyen reanudaciones con origen conservado. No se fingió continuidad ni se modificaron timestamps, sesiones, hashes o nombres. [Detalle temporal](normalizacion_temporal_S1.md).

## Ejemplos fuera de riesgo conservados

La etiqueta principal permanece obstaculo; outside_risk=1 es un campo independiente. La revisión es visual del sujeto en pantalla, sin inferencia ni modificación automática de etiquetas.

| Fotografía (orden por t_capture_ms) | frame_id | outside_risk |
|---|---|---:|
| [S2-14](../datos/evaluacion/S2/S2_0003452297_S2_7be3ff1ce01c41f3b29038093c363da1.jpg) | S2_7be3ff1ce01c41f3b29038093c363da1 | 1 |
| [S2-15](../datos/evaluacion/S2/S2_0003498734_S2_feded6baa90b4d3e95cc01ca623bc200.jpg) | S2_feded6baa90b4d3e95cc01ca623bc200 | 1 |
| [S2-16](../datos/evaluacion/S2/S2_0003510437_S2_a256771fc9fd49988bebafc788e7d57d.jpg) | S2_a256771fc9fd49988bebafc788e7d57d | 1 |
| [S2-17](../datos/evaluacion/S2/S2_0003541250_S2_36602891e66d4e878a5ac5eb275276ea.jpg) | S2_36602891e66d4e878a5ac5eb275276ea | 1 |
| [S3-13](../datos/evaluacion/S3/S3_0002969243_S3_ab81a14f8ab7413b8a0b77a3914a2391.jpg) | S3_ab81a14f8ab7413b8a0b77a3914a2391 | 1 |

## Metadatos e instrucciones para Emilio

Los dos CSV tienen el esquema: sequence_id, frame_id, t_capture_ms, path, sha256, sequence_start_unix_ns, session_id, scene_label, outside_risk, image_width e image_height. Cada path es relativo a la carpeta de su conjunto, no a la raíz del repositorio. Ordenar cada secuencia por t_capture_ms; no deducir orden del nombre JPEG. Validar SHA-256 sobre bytes originales, sin recodificar, renombrar ni reasignar sesiones. Las guías del visor no forman parte de las imágenes.

Desde la raíz ejecutar `python Proyecto5/scripts/validar_capturas.py --issue57` con el entorno del proyecto. La validación repetida el 2026-11-03 aprobó 84+7 JPEG, sin huérfanos, duplicados, errores de hashes ni IDs repetidos. Las salidas nuevas de esta preparación se adjuntan al ZIP de revisión; no se cambian reglas del validador. La inferencia real y las cajas/clases anotadas corresponden a P5-03/P5-06: no convertir etiquetas humanas en predicciones ni porcentajes de confianza. Revisar los cinco casos outside_risk anotando al sujeto representado, no al teléfono ni al reflejo.

La [ficha](ficha_auto.md) documenta L298N por manual, pendiente de corroboración física; 0.545 m/s y giros aproximados 90°/0.35 s por lado son mediciones manuales iniciales. La web tiene un solo nivel de actuación y carece de selector de velocidad; no se inventa un rango. El registro de FPS sí respalda 48.97 JPEG distintos recibidos/s. Los tiempos 1.80/1.83/1.84 s y el texto 0.55 eran ejemplos de software. No se pide grabar ni repetir giros para aumentar precisión.

## Condiciones: evidencia, declaraciones y preguntas pendientes

| Condición | Clasificación | Evidencia o pregunta concreta |
|---|---|---|
| Archivos, CSV, resolución, hashes, IDs y tiempos | Verificada mediante archivos | 91 JPEG con registro y SHA-256; se preservan timestamps y sesiones. No acredita exposición del sensor |
| Sesiones/hashes distintos entre evaluación y ajuste | Verificada mediante registros | IDs de sesión disjuntos y ningún JPEG compartido; no se fabricó independencia |
| Episodios independientes y sin dividir cuadros contiguos | Pendiente de confirmar | ¿Las siete S1 de ajuste se capturaron en episodios diferentes, sin repartir cuadros contiguos con evaluación? |
| Motores apagados durante las capturas | Cumplido por declaración confirmada del operador (2026-11-03) | El operador confirmó personalmente motores apagados, vehículo inmóvil y cámara funcionando en todas las capturas definitivas S1–S6, incluidas recapturas y fuera de riesgo. No se atribuye comprobación a sensores ni al programa |
| S1 histórica con cuatro sesiones y pausas | Verificada mediante trazabilidad | [Normalización previa](normalizacion_temporal_S1.md); no se normalizó de nuevo ni se simuló continuidad |
| Procedimiento de estímulos 2D autorizado por Sebastián/PM | Declarada por el operador | El usuario confirmó autorización del procedimiento de pantalla para person/dog/cat; no se afirma una confirmación remota adicional |
| Procedencia y publicación pública de los estímulos | Pendiente de confirmar | ¿De dónde proceden las imágenes y qué permiso/licencia permite publicarlas en estas capturas? La autorización del método no documenta derechos de distribución |
| Prestaciones del mando y medidas manuales | Declaradas por el operador | Interfaz sin selector, motores funcionales y giros sobre su eje; medidas aproximadas sin repetibilidad inventada |

## Independencia del ajuste: comprobación temporal

Se revisaron los siete registros S1 de ajuste, ordenados por t_capture_ms. No hay session_id, frame_id, rutas ni SHA-256 compartidos con evaluación; los 91 JPEG tienen su registro y hash correcto. La independencia de sesión queda comprobada en los metadatos. El ajuste contiene siete negativos y cero positivos.

| session_id de ajuste | Cuadros | t_capture_ms conservados |
|---|---:|---|
| 7f1d45e0e669436985dc74f5443476ea | 1 | 0 |
| fd4c17f067da4280b15ee5657160f8d5 | 6 | 120107, 186669, 247028, 249091, 250107, 251935 |

Ambas sesiones usan el origen de secuencia registrado 1793497775705148900 ns. Para comparar con evaluación se calculó, sin editar CSV, `A_ns = sequence_start_unix_ns + t_capture_ms * 1000000`. El menor desfase entre conjuntos es **186744308000 ns = 186.744308 s**, entre el último cuadro de la sesión de evaluación e2b4a168ded24ec38bc6db62dd7dfead (frame_id 39364f4da4954767895eab0aa90268e9) y el primero de ajuste (2ecfe78a3f1e434fbf72a4d967029fb9). La evaluación S1 siguiente aparece después de terminar el intervalo registrado del ajuste. No se aprecia alternancia ni reparto de cuadros contiguos en los registros disponibles.

Son tiempos de captura registrados; la reconstrucción histórica de S1 conserva residuos menores de 1 ms en la auditoría. No certifican sincronización física entre ejecuciones, continuidad del stream ni independencia total de escena. La separación temporal y los IDs no sustituyen la confirmación de que ajuste fue otro episodio/escena sin repartir cuadros contiguos; ese punto sigue pendiente del operador. No se exige recapturar ni se cambian imágenes para aparentar independencia.

## Tabla de criterios de #57

Estados se refieren a la evidencia disponible. El [issue #57](https://github.com/sebastian0023/Proyecto-3-Clasificador-de-imagenes/issues/57) no exige video de giros, un número de repeticiones, positivos mínimos de ajuste ni precisión instrumental concreta; esas recomendaciones no se convierten en nuevos requisitos.

| Requisito | Evidencia | Estado | Acción necesaria |
|---|---|---|---|
| Seis secuencias de evaluación | S1=18, S2=17, S3=13, S4=12, S5=12, S6=12; revisión visual | Cumplido visualmente | Revisión de escenarios/anotaciones por PM/P5-06; no se afirma detección |
| >=60 distintos y >=10 por secuencia | 84 JPEG distintos | Cumplido | Conservar conjunto válido |
| >=20 obstáculos y >=20 despejados | 58 B y 26 D, sin pendientes | Cumplido | Ninguna recaptura requerida por cantidad |
| Objetos fuera de riesgo | 5 marcas inspeccionadas visualmente | Cumplido visualmente | Mantener evidencia; confirmar cajas al anotar |
| Clases acordadas P5-03 | person/dog/cat en pantalla, autorización declarada; política de main | Cumplido visualmente | No inferir desempeño del detector |
| JPEG y CSV, rutas y hashes | 91 archivos entre ambos conjuntos, dos CSV | Cumplido | Verificar al transferir sin alterar bytes |
| Identificadores y tiempos relativos | IDs únicos; trazabilidad de S1 y sesiones preservadas | Cumplido en archivos | Acordar enlace de UUID históricos a eventos prefijados; aceptar composición de sesiones |
| 1–2 secuencias de ajuste | Una S1 con 7 negativos, ningún positivo | Cumplido por cantidad | Comunicar limitación; no exigir positivos que #57 no pide |
| Ajuste en otro episodio sin cuadros contiguos compartidos | Sesiones/hashes disjuntos; escena doméstica similar | No verificable solo con archivos | Confirmación del operador |
| Modelo, cámara, resolución y FPS | Ficha y JSON original de recepción | Cumplido | Conservar alcance de cada dato |
| Controlador de motores | L298N por manual del modelo | Cumplido documentalmente | Corroboración física pendiente; no afirmar inspección |
| Rango real de velocidad/dirección | Único nivel del mando y medidas manuales aproximadas; sin selector | Pendiente | PM/profesor define aceptación de la limitación o evidencia adicional; no inventar mínimos/máximos |
| Motores apagados/desconectados | Confirmación personal del operador para todas las capturas S1–S6; vehículo inmóvil | Cumplido por declaración confirmada | Conservar la declaración; no requiere repetir fotografías ni se presenta como medición de sensores |
| Sin credenciales | Exclusiones y revisión del contenido seleccionado | Cumplido en selección inspeccionada | Conservar .env, claves y respaldos fuera del PR |
| Entrega a Emilio | Documento y mensaje preparados | Pendiente | Compartir material y confirmar recepción |
| Permiso de publicación de estímulos | No consta procedencia/licencia | No verificable | Aportar fuente y permiso; condición de publicación, sin alterar datos para simularlo |
| Git/CI y revisión del PR | Corrección HighGUI presente; workflow con requisitos base y captura | Pendiente de CI real | Revisar cambio mínimo, integrar base con autorización y ejecutar en Python 3.12 |

## Pendientes que impiden afirmar cierre completo

- Corroborar físicamente L298N documentado y características de batería. PM/profesor debe resolver el alcance del rango físico con una web sin selector; conservar las mediciones manuales aproximadas. No se piden videos ni repeticiones de giro solo para mejorar precisión.
- PM: aceptar composición de sesiones/pausas y confirmar cobertura de escenarios mediante anotaciones. Operador: confirmar independencia del episodio de ajuste. Motores apagados en todas las capturas S1–S6 ya confirmado personalmente; condición cumplida.
- P5-06/P5-07: correspondencia de UUID históricos a frame_id prefijados de eventos y reproducción de huecos. No se modifica el CSV fuente para anticiparlo.
- Actualizar la base de forma autorizada y repetir CI en Python 3.12/lock de main. Tras `git fetch origin` del 2026-11-03, la rama está 24 commits detrás y 0 delante de origin/main (`7b6a88b1754d906d6376d089c2d8b9bf8f32c292`), sin merge/rebase. Se implementó el delta de CI para instalar requirements.txt y requirements-capturas.txt y considerar ambos en caché, sin modificar lint/pytest. El workflow se reconstruyó desde la versión exacta de main porque faltaba en el checkout: al actualizar la base hay que reconciliar Proyecto5/.gitignore y .github/workflows/p5-ci.yml, conservando los cambios del equipo.
- Confirmar independencia del episodio de ajuste y procedencia/permiso de publicación de las imágenes, según la tabla anterior. La confirmación de motores apagados ya está incorporada. No se inventan otras confirmaciones.
- Compartir esta entrega y confirmar recepción de Emilio. Este archivo prepara la entrega; no la envía.

[Ficha y límites de medición](ficha_auto.md); [captura/validación](guia_capturas.md). La aprobación del validador cuantitativo no sustituye estos pendientes físicos y de revisión.

## Mensaje breve preparado, no publicado

> Emilio: tengo preparados los datos de P5-05/#57 para tu revisión: 84 JPEG de evaluación (58 obstáculos, 26 despejados y 5 fuera de riesgo), 7 S1 negativos de ajuste y sus CSV con IDs, tiempos y SHA-256. El validador aprueba y el operador confirmó motores apagados en S1–S6. Son capturas ESP32-CAM de estímulos 2D autorizados; la revisión fue visual, sin inferencia automática confirmada. Ajuste no contiene positivos. Adjunto revision_definitiva_PR57.zip con ficha, trazabilidad, límites y pendientes; los archivos aún no se han subido mediante PR. Revisa las cajas/escenarios y confirmemos recepción antes de congelar las anotaciones de #58.
