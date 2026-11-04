# Estímulo autorizado: perro de peluche como dog — P5-05b / issue #57

**Estado final posterior:** las aprobaciones S3/S4, seis sustituciones S2,
normalización/interrupción, gatos y peluche dog=16 están comunicadas por el operador.
La selección de 78 se integró localmente y validó de nuevo; ver [entrega vigente](entrega_emilio_p5_05b.md).
El contenido anterior se conserva como historial/protocolo; sus pendientes de
aprobación ya resueltos no describen el estado actual. Consentimiento completo: firma 2026-11-03 y alcance GitHub confirmados.

El operador comunicó expresamente la autorización de Sebastián para usar el
perro de peluche como estímulo y anotarlo como **dog, class_id=16**. Esta decisión
sustituye el criterio anterior que bloqueaba esas imágenes por no ser animales reales.
No se inventa una fecha de autorización ni un comentario de GitHub no consultado.

La convención del dataset es explícita: **representa un perro de peluche, no un
perro real**. No se cambian píxeles ni metadatos de captura. El CSV fuente de once
campos no contiene clases de objetos y no se amplió su esquema; Emilio hará las
anotaciones COCO con dog=16 y su entrada correspondiente en categories.

La [correspondencia de estímulos](correspondencia_estimulos_dog_p5_05b.csv) identifica
22 imágenes: 16 de la selección principal y seis adicionales. Es una guía de
anotación, no un COCO anotado ni resultados de detección. Identificar siempre por
dataset fuente + session_id + frame_id + SHA, porque los IDs se repiten entre fuentes.
No inventar cajas ni confianzas. La [entrega preparada para Emilio](entrega_emilio_p5_05b.md)
todavía no representa entrega recibida ni un conjunto congelado.

## Fuera de riesgo

Los seis adicionales S2_f0001–S2_f0006 de la sesión 3ecf440718884a7bb6eeb59e841e1cd0
muestran el mismo estímulo completo por encima de Y=148 en imágenes 400×296.
La revisión visual respalda outside_risk=1 con la nueva convención dog; algunas
tienen poco margen. Emilio debe dibujar las cajas reales y comprobar y2<148
antes de congelarlas. No se da por válida una marca únicamente por estar en CSV.

## Estado de S6

La secuencia conserva D×4–B×4–D×4. Los cuatro B son el perro de peluche autorizado:
su uso como dog ya no requiere otra aprobación por no ser persona/animal real.
Se conservan tiempos, sesión y las ocho imágenes despejadas distintas. La condición
de estímulo queda documentada; no se afirma que el detector lo haya reconocido.

## Antecedente: candidato sin normalizar (rechazado)

Una propuesta privada sustituye S2_f0001–S2_f0006 principales por sus homónimos
adicionales y mantiene S2=17, total=78, 20 D, 58 B y seis outside_risk. No duplica
IDs, rutas ni hashes y conserva cada campo original; todas las fuentes siguen intactas.
Es un ejemplo técnico de sustitución por ID, no una selección por aciertos del detector.

Sin embargo, los seis adicionales empiezan en t_capture_ms=0 con otro origen:

| Origen S2 | sequence_start_unix_ns |
|---|---:|
| Principal | 1793763347573381600 |
| Adicional | 1793767996073360200 |

La diferencia es 4648499978600 ns. Su recepción registrada se reconstruye como
origen + t_capture_ms×1000000, con el redondeo original a milisegundos.
Cambiar el origen sin cambiar el tiempo relativo desplazaría la recepción registrada;
recalcular el tiempo relativo infringiría la instrucción de conservarlo.
**En esa propuesta anterior no se hizo ninguna de esas modificaciones.** Ordenar/renombrar tampoco resuelve
dos relojes originales dentro de una S2 con origen único exigido por el validador.

El candidato contiene 78 registros y 78 JPEG emparejados. El validador rechaza
seis filas por reinicio temporal; después las reporta como JPEG sin CSV y no cuenta
sus outside_risk. Son efectos del rechazo temporal: no hay seis huérfanos reales.
No se modificó el validador para forzar aprobación. No se integró el candidato en
la evaluación activa ni se hicieron push, merge o PR.

## Actualización: candidato normalizado privado

El operador autorizó investigar y preparar una escala común con auditoría. El
[cálculo temporal](normalizacion_temporal_S2_p5_05b.md) conserva los tiempos/orígenes
originales, las sesiones y el residuo submilisegundo; la pausa no se comprime.
Los seis adicionales usan alias derivados S2_f0018–S2_f0023 con
[correspondencia explícita](correspondencia_normalizacion_S2_p5_05b.csv).
El candidato de 78 aprueba --issue57: 20 despejados, 58 obstáculos y seis fuera
de riesgo. Ninguna foto ni CSV fuente, evaluación activa o ajuste fue modificado.

## Estado actualizado de decisiones

- PM: S2 interrumpida/normalizada y gatos reales ya aceptados; seis adicionales al final.
- PM: encuadres S3/S4 y selección aprobados; ver [justificación](seleccion_78_p5_05b.md),
  sin inventar motivos de las cuatro eliminaciones previas.
- Coordinar cortes/IDs con el responsable del [reproductor](propuesta_reproductor_cortes_p5_05b.md).
- [Consentimiento completo](consentimiento_recaptura_issue57.md), firmado el
  2026-11-03 y publicación GitHub confirmada. El firmado permanece privado.
- Confirmar entrega a Emilio y congelar COCO/manifiesto e IDs coordinados.
  #59 usará ese mismo conjunto congelado, sin alterar su algoritmo.

No hacen falta otras once capturas para resolver la aritmética del CSV si el PM
acepta esta cronología interrumpida. Si exige una sola sesión, la normalización
no la crea: planificar 17 cuadros nuevos conforme al protocolo aprobado.
