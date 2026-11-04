# Propuesta al responsable de P5-14: cortes de sesión e IDs

**Solo inspección y propuesta; ningún archivo de otros integrantes modificado.**
Se consultaron referencias locales, sin fetch, merge ni ejecución de inferencia.
El reproductor no está en el HEAD de esta rama. Se inspeccionó
`Proyecto5/src/p5/recorrer.py` en `origin/p5-14-recorrido-integral`, y
`Proyecto5/src/p5/datos.py` en el `origin/main` disponible localmente.
Referencias consultadas: P5-14 dd7997791722a9649d6cd86738034772bf2efdc1; origin/main 118b67f87af78ddaeba35e628a091ad13ed6f09e.
Los hashes y copias de consulta se conservan en la auditoría
privada localizada por `Proyecto5/resultados/revision_PM_p5_05b/ubicacion.json`.
No se afirma haber verificado el estado remoto más reciente ni PR fusionados.

## Hallazgo temporal concreto

`leer_manifiesto()` de P5-14 no conserva session_id en Frame.
`normalizar_tiempos()` asigna el mismo `replay_dt_ms` entre todos los cuadros
de una misma sequence_id: 100 ms por defecto. Solo deja hueco al cambiar de
secuencia. Con S2_f0017 → S2_f0018 usaría **100 ms**, aunque el CSV conserva
1817039 ms y la auditoría reconstruye 1817039978600 ns. Guardar el dato en
t_capture_origen_ms no hace que el reloj de reproducción reconozca el corte.
Se comprobó ejecutando aisladamente solo esa función, extraída por AST, con los
17 tiempos S2 y sin importar el detector ni el recorrido: los tres cortes quedan
en 100 ms. Esta prueba aislada no repite ni sustituye la suite del candidato.

Los seis adicionales están comprobados en las últimas seis posiciones de S2
(f0018–f0023). Esto satisface esa disposición pedida por Sebastián, pero el
reproductor consultado no cumple por sí solo el reconocimiento temporal del corte.
No describir la corrida resultante como reproducción de la pausa real.

S2 conserva cuatro sesiones y tres cortes, todos documentados:

| Transición | Pausa CSV, ms | Pausa reconstruida, ns |
|---|---:|---:|
| f0008 → f0009 | 241906 | 241906000000 |
| f0016 → f0017 | 1992758 | 1992758000000 |
| f0017 → f0018 | 1817039 | 1817039978600 |

## Propuesta, sin aplicar

El responsable de P5-14 debe decidir y probar un modo explícito que lea las
sesiones del CSV o un sidecar de cortes. Mantener secuencia, IDs, orden, timestamps
de origen y sesión auténtica. Al cambiar de sesión, conservar el delta temporal
registrado (sin sleep físico: puede avanzar el reloj controlado) y evaluar
watchdog antes del siguiente cuadro. No interpolar imágenes ni asumir vía libre
durante la ausencia de evidencia. Conservar el residuo submilisegundo en auditoría.

El modo de cadencia virtual de 100 ms puede seguir existiendo con su propósito
documentado; debe reconocer cortes explícitos o identificarse como simulación de
cadencia, sin presentarlo como continuidad de captura. Registrar el modo usado.
No añadir campos de percepción fuera del schema v1 sin revisión de los equipos;
los cortes pueden ser metadatos internos/sidecar, no un cambio automático del contrato.

Pruebas propuestas para el responsable: corte final S2 y los dos anteriores,
orden estricto global con desfases por secuencia, watchdog ante huecos, ningún
cuadro inventado y ningún cambio de IDs/hashes/metadatos de captura.

## Diferencia adicional de IDs para Emilio

La función leer_capturas() de P5-06 consultada asigna siempre IDs consecutivos
por posición, conservando el recibido en frame_id_origen. P5-14 respeta IDs
prefijados ya numéricos. Ejemplos del candidato:

- Dataset S2_f0007 (primero de S2): P5-06 produciría S2_f0001, P5-14 S2_f0007.
- Dataset S2_f0018 (posición 12): P5-06 produciría S2_f0012, P5-14 S2_f0018.
- Los huecos manuales de S3/S4 también desplazan las numeraciones.

La [tabla de compatibilidad](compatibilidad_ids_consumidores_p5_05b.csv) contiene las 78 rutas,
hashes y ambas previsiones; hay 38 diferencias con esas versiones de código.
No son nuevos IDs de captura ni anotaciones. Los responsables deben acordar un
identificador canónico para COCO/predicciones y conservar la correspondencia
fuente/sesión/ruta/SHA. No renumerar el CSV original para acomodarlo a un consumidor
ni anotar bajo una correspondencia implícita. Este acuerdo precede al congelado
y no exige modificar el algoritmo de métricas del #59.

## Interfaz disponible y propuesta mínima para coordinar

La selección está integrada, aprobada por el PM y validada. El consentimiento
está completo, firmado el 2026-11-03, con publicación GitHub autorizada. Se
entregan sin cambiar el CSV fuente:

- [Tres cortes S2](cortes_sesion_S2_p5_05b.csv), con las dos sesiones, IDs y tiempos
  de cada transición y pausa reconstruida.
- [Correspondencia original/derivada S2](correspondencia_normalizacion_S2_p5_05b.csv).
- [Previsión de IDs de los consumidores](compatibilidad_ids_consumidores_p5_05b.csv),
  ligada a las referencias consultadas, no un nuevo ID de captura.

Propuesta al responsable P5-06: conservar los IDs numéricos prefijados que ya
trae el CSV y mantener correspondencia explícita para los UUID históricos,
de acuerdo con P5-14. Alternativamente, acordar una numeración común por posición
y que ambos consumidores lean la misma tabla. No aplicar uno de esos cambios
por separado: se debe congelar una única correspondencia COCO/predicciones.

Propuesta al responsable P5-14: conservar cadencia virtual donde proceda, pero
leer el sidecar/sesiones y reconocer los tres cortes S2; al cruzarlos, avanzar
el reloj controlado por el delta de captura y comprobar watchdog. No inventar
eventos de imagen ni considerar vía libre el intervalo sin cuadros. Conservar
t_capture_origen_ms y el residuo en auditoría. Registrar explícitamente el modo.
No se añadió un campo al schema ni se modificaron sus módulos en esta rama.

Prueba concreta a acordar: f0017 → f0018 conserva 1817039 ms de delta CSV,
residuo 978600 ns documentado, sesión original distinta y no se convierte en
100 ms de continuidad. Las otras dos transiciones tampoco pueden perder su corte.
El [mensaje preparado](mensajes_revision_p5_05b.md) no se ha enviado automáticamente.
