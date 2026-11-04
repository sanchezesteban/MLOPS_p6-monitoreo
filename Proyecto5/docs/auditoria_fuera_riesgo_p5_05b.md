# Revisión de adicionales fuera de riesgo — P5-05b / issue #57

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

**No integrar definitivamente.** El origen, los CSV, la evaluación activa y
los archivos históricos permanecen intactos. Sin inferencia, push, merge ni PR.
**Autorización posterior:** Sebastián permite el perro de peluche como dog=16.
La revisión física sigue siendo válida, pero el rechazo anterior por no ser
persona/perro real queda sustituido por esta convención explícita.
Ver [autorización y resultado actual](autorizacion_estimulo_dog_p5_05b.md).

## Archivos encontrados

En `%LOCALAPPDATA%/P5-57/fuera_riesgo_extra/`:

- 20261103_225154: CSV vacío, sin fotografías.
- 20261103_225218: seis JPEG y CSV de seis filas, una sesión auténtica
  3ecf440718884a7bb6eeb59e841e1cd0, S2_f0001 a S2_f0006.

Se respaldaron los ocho archivos de ambas carpetas y se verificaron sus SHA.
Seis JPEG completos, decodificables, 400×296, hashes correctos y distintos,
sin huérfanos; tiempos 0, 5844, 13297, 22563, 24875 y 38781 ms crecientes.
CSV: obstaculo y outside_risk=1 en las seis filas, sin modificación.

**Las seis muestran el perro de peluche autorizado, no un animal real.** La
revisión visual respalda que esté completo por encima de Y=148, con poco margen
en algunas vistas; no se inventaron cajas COCO medidas. Hay **seis ejemplos
fuera de riesgo utilizables como estímulo dog=16 bajo la nueva autorización**.
Emilio debe comprobar el límite al dibujar las cajas reales para el congelado.

## Obstáculos de integración de metadatos

Los seis frame_id ya existen en la selección principal. Incluso la ruta
S2/S2_0000000000_S2_f0001.jpg coincide con otro JPEG de bytes distintos.
No copiar a ciegas: sobrescribiría evidencia.

- Origen temporal principal S2: 1793763347573381600 ns.
- Origen adicional: 1793767996073360200 ns; nuevo t_capture_ms=0.
- Diferencia de orígenes: 4648499978600 ns, sin alterar registros.

Conservar filas de ambos orígenes dentro de la misma S2 viola el origen único
del validador. No se renombraron IDs/rutas, cambiaron sesiones ni normalizaron
tiempos. Una sustitución parcial tampoco resuelve automáticamente los relojes.

## Alternativas para el PM — ninguna aplicada

Los conteos D/B son las etiquetas existentes, no certificación de clases.

| Alternativa | S1/S2/S3/S4/S5/S6 | Total | D/B | Evaluación |
|---|---|---:|---|---|
| Mantener candidato principal | 12/17/13/12/12/12 | 78 | 20/58 | Sin fuera de riesgo válido; otros incumplimientos pendientes |
| Añadir las seis a S2 | 12/23/13/12/12/12 | 84 hipotéticos | 20/64 | Estímulo ya autorizado; cambia cuota y tiene IDs/ruta/origen conflictivos |
| Sustituir seis S2 por las seis | 12/17/13/12/12/12 | 78 | 20/58 | Candidato privado por coincidencia de ID, sin duplicados; bloqueado por dos orígenes y reinicio temporal |
| Conservar seis como anexo privado | 12/17/13/12/12/12 + anexo 6 | 78 + 6 | 20/58 en evaluación | Preserva origen; no satisface fuera de riesgo de evaluación |
| Capturar estímulos autorizados fuera de riesgo como continuación y sustituir S2 autorizadas | 12/17/13/12/12/12 | 78 previstos | 20/58 previstos | Potencial; requiere otras fotos, CSV coherente y aprobación de varias sesiones/selección |
| Nueva S2 completa conforme, con ejemplos fuera de riesgo aprobados | 12/17/13/12/12/12 | 78 previstos | 20/58 previstos | Potencial; requiere fotografías reales, decisiones PM y resolver S3/S4/S6 |

Los 84 hipotéticos no son el archivo histórico de 84. No se reutilizan capturas
históricas. Una futura S2 completa de 17 permitiría conservar su propio reloj,
pero el número y posición de ejemplos fuera de riesgo deben autorizarse antes.
Otra posibilidad futura es continuar una copia coherente del CSV principal
ya depurado y autorizado: el capturador sigue tras el máximo ID y registra
tiempo real desde el origen existente, con nuevo session_id auténtico. No
modifica los metadatos anteriores. Solo serviría si el PM permite esa continuidad
entre sesiones y aprueba cuáles se sustituyen; no reutiliza los seis peluches.
No apuntar automáticamente al CSV fuente de 58 filas con cuatro ausentes.
Seis es un ejemplo para comparar conteos, no un mínimo nuevo del issue:
el número y la distribución de ejemplos genuinos los debe fijar el PM.
No se eligen fotos por resultados del detector ni se presenta una selección
posterior como toma única sin exclusiones.

## Estado de pendientes anteriores

Principal: 54 JPEG, CSV de 58 filas, cuatro exclusiones documentadas y propuesta
de 54 idéntica en sus registros conservados; originales/resguardos verificados.
S6 mantiene D×4–B×4–D×4 y sus cuatro B son ahora estímulos dog autorizados,
documentados como peluche. No se exige otra autorización por ese motivo.
Los gatos reales ya fueron aceptados; quedan recortes/márgenes S3/S4 y justificación de selección.

En esta fase inicial faltaban fecha y alcance de publicación. Ambos quedaron
confirmados después: [consentimiento completo](consentimiento_recaptura_issue57.md),
firmado el 2026-11-03. El documento permanece privado y sin datos personales en Git.

El informe, imágenes de revisión y manifiestos privados se localizan mediante
`Proyecto5/resultados/auditoria_fuera_riesgo/ubicacion.json`, ignorado por Git.
Se generó un candidato privado de 78 por sustitución exacta de IDs, sin aplicar
al dataset activo. Tiene seis outside_risk y metadatos originales, pero no
aprueba por dos orígenes/reinicio de tiempo en S2. No se cambió el validador.

## Verificaciones ejecutadas en esta revisión

- Seis adicionales: `--solo-integridad` aprobado; no certifica sujeto/protocolo.
- Candidato anterior de 78, sin añadir extras: `--issue57` rechazado con
  «Faltan cuadros marcados con objetos fuera de riesgo».
- Candidato nuevo con sustituciones: seis filas temporales rechazadas y seis
  avisos derivados de JPEG sin CSV, pese a tener 78 pares reales. El validador
  no cuenta los seis outside_risk rechazados; no es ausencia visual de ejemplos.
- Evaluación activa histórica, sin cambios: `--issue57` aprobado; no equivale
  a aprobar las recapturas ni los seis adicionales.
- Pytest: 276 pruebas y 53 subpruebas aprobadas; Ruff check y format aprobados.
- Python 3.10.8, sin cámara, motores ni modelo de detección; no se afirma corrida 3.12.
