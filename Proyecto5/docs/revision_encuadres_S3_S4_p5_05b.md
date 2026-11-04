# Evidencia para Sebastián: encuadres S3/S4 — P5-05b

La auditoría previa dejó **los 13 S3 y los 12 S4** observados inicialmente por no acreditar
el sujeto completo. Se conservan todos en el dataset integrado localmente: **Sebastián aprobó los encuadres**
según comunicación final del operador; [constancia](autorizaciones_finales_p5_05b.md). Esta revisión
no cambia JPEG, CSV, etiquetas ni selección. Gatos reales y perro de peluche
dog=16 ya están autorizados; solo se revisa su geometría y visibilidad.

La [tabla de 25 cuadros](revision_encuadres_S3_S4_p5_05b.csv) incluye ID, ruta,
sesión, tiempo, SHA, sujeto señalado, motivo por cuadro, invasión del centro y
decisión PM aprobada por comunicación del operador. Se generaron cinco páginas de contacto PNG y un PDF:
tres páginas S3 y dos S4, con las imágenes completas (no recortadas), tercios,
mitad horizontal y flecha manual al sujeto. Hay un detalle ampliado S3_f0013.

Se encuentran fuera de Git, localizados mediante
`Proyecto5/resultados/revision_PM_p5_05b/ubicacion.json`, ignorado por Git.
Son evidencias derivadas para revisión privada. El consentimiento de publicación
está completo, firmado el 2026-11-03; no se publica el documento firmado. Los originales siguen intactos.
Las flechas no son cajas delimitadoras ni predicciones y no sustituyen COCO.

| Grupo | Cuadros concretos | Motivo | Centro |
|---|---|---|---|
| S3 gato | f0001, f0002, f0003, f0006, f0007 | Cuerpo parcialmente cortado y escena oscura | f0002/f0003/f0007 indeterminados por contorno/cola; en f0001/f0006 no es evidente en la parte visible |
| S3 peluche | f0008–f0011 | Cuerpo cortado por borde inferior/lateral | No evidente en parte visible; no acredita sujeto completo |
| S3 persona | f0012, f0014, f0015 | Torso/cuerpo cortado por borde inferior/lateral | No evidente en parte visible; no acredita sujeto completo |
| S3 persona | **f0013**, t=790941 ms | Cuerpo cortado; hombro/torso derecho junto a W/3 | **Probable invasión**, pendiente de confirmar contorno |
| S4 gato | f0001, f0003, f0004, f0005 | Cuerpo cortado por borde inferior/derecho | No evidente en parte visible; no acredita sujeto completo |
| S4 persona | f0006, f0007, f0009, f0010 | Cuerpo cortado por borde inferior/derecho | No evidente en parte visible; no acredita sujeto completo |
| S4 peluche | f0011–f0014 | Cuerpo llega al borde inferior; no se acredita sujeto completo | No evidente en parte visible; no acredita sujeto completo |

Límites para 400×296: X=133⅓, X=266⅔, Y=148. Las guías rasterizadas son
orientativas; una caja que toca el centro ya ocupa esa zona según el contrato.
«No evidente en parte visible» no significa aprobación: no permite inferir
qué queda fuera de imagen. «Indeterminado» no es una etiqueta de clase nueva.
Bandas horizontales y oscuridad limitan la lectura; no se corrigieron los píxeles.

La revisión ya fue respondida: **los 25 encuadres están aprobados por el PM**.
La tabla conserva motivos observados y registra esa decisión; no convierte las
flechas en COCO ni afirma que los contornos fueran medidos. No se excluyó ningún
cuadro ni se reetiquetó por el detector. Las hojas originales de revisión permanecen
privadas e históricas; su texto pendiente corresponde al momento anterior a la aprobación.
