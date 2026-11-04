# Discrepancias de la verdad de referencia (P5-06)

Generado por `scripts/construir_manifiesto.py`. No editar a mano: se regenera.

Las discrepancias se revisan con quien anota. Si la caja es correcta, la discrepancia
se queda y se explica en `docs/datos.md`; nunca se mueven cajas para que cuadre.

## evaluacion

- COCO: `datos/anotaciones.json` (SHA-256 `2afc9ec45ee5…`), cuadros en el manifiesto: 78
- Errores de integridad: 0
- Discrepancias a revisar: 6

### Discrepancias

- S3_f0002: estado centro (izquierda+centro) != intencion izq (scene_label=obstaculo, outside_risk=0)
- S3_f0003: estado centro (izquierda+centro) != intencion izq (scene_label=obstaculo, outside_risk=0)
- S3_f0010: estado centro (izquierda+centro) != intencion izq (scene_label=obstaculo, outside_risk=0)
- S3_f0013: estado centro (izquierda+centro) != intencion izq (scene_label=obstaculo, outside_risk=0)
- S6_f0005: estado izq (izquierda) != intencion centro (scene_label=obstaculo, outside_risk=0)
- S6_f0007: estado der (derecha) != intencion centro (scene_label=obstaculo, outside_risk=0)

## ajuste

- COCO: `datos/anotaciones_ajuste.json` (SHA-256 `6a657e7145df…`), cuadros en el manifiesto: 7
- Errores de integridad: 0
- Discrepancias a revisar: 0
