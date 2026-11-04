# Mensajes preparados — P5-05b / issue #57

Mensajes preparados para compartir tras publicar el PR. Consentimiento completo:
firma real 2026-11-03 y alcance GitHub confirmado; documento firmado privado.

## Para Sebastián

Integré localmente la selección aprobada P5-05b: 78 JPEG, S1/S2/S3/S4/S5/S6 =
12/17/13/12/12/12; 20 despejadas, 58 obstáculos y seis fuera de riesgo, más siete
de ajuste independientes. Quedaron registradas tus aprobaciones de encuadres,
seis sustituciones, S2 normalizada/interrumpida, gatos y peluche dog=16.
Los seis adicionales están al final y los originales/históricos permanecen intactos.
--issue57, 287 pruebas y 53 subpruebas, Ruff e integridad de 85 hashes aprobaron.
No ejecuté el detector ni seleccioné por sus resultados. Las cuatro eliminaciones
manuales conservan motivo individual desconocido, sin inventarlo. El consentimiento está completo (firma 2026-11-03); falta coordinar cortes/IDs con P5-06/P5-14. Preparé el commit
local y la descripción con Parte de #57; no se cerrará el issue ni se hará merge.

## Para Emilio

La selección definitiva P5-05b ya está integrada localmente y validada: 78 JPEG
de evaluación y siete de ajuste. Usa ese conjunto, no las versiones históricas
de 84/78 previas. S2 incluye seis fuera de riesgo al final; las sesiones, tiempos,
hashes y correspondencias están documentados. Gatos reales están aceptados;
dog=16 incluye el perro de peluche autorizado, declarado como peluche.
Anota directamente los JPEG sin ver detecciones, confianzas ni resultados previos.
Antes de congelar COCO/manifiesto coordinemos IDs con P5-14 usando ruta/SHA e
ID de origen. Después de terminar la anotación se congelará la configuración
del detector y se ejecutarán inferencia y #59 sobre los mismos datos. El paquete
privado está preparado, sin predicciones; la publicación GitHub está autorizada con firma del 2026-11-03.
Confirma recepción cuando efectivamente se entregue; no se presupone aquí.

## Para responsables de P5-06 y P5-14

La selección aprobada usa IDs de captura trazables y cuatro sesiones en S2.
En las referencias locales consultadas, P5-06 renumera por posición y P5-14
conserva prefijados: hay 38 diferencias en la tabla adjunta. Además, el
reproductor reduce los tres cortes S2 a 100 ms. Propongo acordar IDs canónicos
conservando los originales y reconocer el sidecar de cortes, sin cambiar el
schema v1. En particular, S2_f0017 → S2_f0018 debe conservar el corte de
1817039 ms del CSV (fracción 978600 ns en auditoría), no continuidad de 100 ms.
Se adjuntan tablas y casos; ¿podéis confirmar el comportamiento de vuestras
versiones actuales y coordinar el cambio antes de congelar COCO/predicciones?
No modifiqué vuestros módulos ni ejecuté el detector.
