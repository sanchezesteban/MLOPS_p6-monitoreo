# Borrador de actualización del issue #57 — no enviado

El PR #79 ya está fusionado en main. La corrección solicitada por el PM se hará
en un PR nuevo, «P5-05b: Recaptura real S2, S3, S4 y S6», rama p5-05b-recaptura
creada desde origin/main b6317b5. El historial de #79 queda intacto.

Motivo: el detector identificaba el teléfono usado como estímulo como tv.
Se sustituyen esos estímulos por una persona real, sin seleccionar cuadros por
confianza ni repetir tomas para optimizar métricas. Se requieren 54 capturas:
17 S2, 13 S3, 12 S4 y 12 S6; S6 conserva 4 libres → 4 persona → 4 libres.
S1=12 y S5=12 permanecen, salvo instrucción posterior. Resultado esperado: 78.

La preparación local conserva el archivo verificable de 84 fotografías del
protocolo v1 y los 78 cuadros previos. No se retiraron ni reemplazaron imágenes
activas ni se publicaron capturas nuevas. La recaptura, el consentimiento y la
integración siguen pendientes. Se solicita al PM decidir la distribución de
objetos fuera de riesgo en los nuevos cuadros antes de completar el protocolo.

Emilio debe usar la nueva selección congelada para COCO/manifiesto definitivos;
las métricas reales de #59 usarán únicamente predicciones del mismo conjunto.
Mantener «Parte de #57» mientras falten criterios o la entrega a Emilio; no
cerrar automáticamente el issue solo por aprobar las pruebas de software.
