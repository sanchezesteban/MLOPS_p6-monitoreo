# Conteo de la verdad de referencia (P5-06)

Generado por `scripts/contar_datos.py` con todas las secuencias. No editar a mano: se regenera.
Positivo = cuadro con al menos una caja de `clases_obstaculo` (incluidas laterales y
fuera de riesgo); negativo = cuadro sin cajas (vacio explicito).

## Metas de E3 / #58 (evaluacion)

| Meta | Valor | Minimo | Cumple |
|---|---:|---:|---|
| unicos_sha256 | 78 | 60 | si |
| secuencias | 6 | 6 | si |
| positivos | 58 | 20 | si |
| negativos | 20 | 20 | si |

## evaluacion

Cuadros 78, unicos por SHA-256 78 (duplicados exactos 0), positivos 58, negativos 20.

| Secuencia | Cuadros | Positivos | Negativos | Estados esperados |
|---|---:|---:|---:|---|
| S1 | 12 | 0 | 12 | libre 12 |
| S2 | 17 | 17 | 0 | libre 6, centro 11 |
| S3 | 13 | 13 | 0 | izq 9, centro 4 |
| S4 | 12 | 12 | 0 | der 12 |
| S5 | 12 | 12 | 0 | bloqueado 12 |
| S6 | 12 | 4 | 8 | libre 8, izq 1, der 1, centro 2 |

Instancias por clase: cat 25, dog 34, person 23. Cajas: en_riesgo 76, fuera_de_riesgo 6.

## ajuste

Cuadros 7, unicos por SHA-256 7 (duplicados exactos 0), positivos 0, negativos 7.

| Secuencia | Cuadros | Positivos | Negativos | Estados esperados |
|---|---:|---:|---:|---|
| AJ1 | 7 | 0 | 7 | libre 7 |

Instancias por clase: ninguna. Cajas: ninguna.

JPEG con el mismo SHA-256 en ajuste y evaluacion: 0.

## Casi duplicados por pHash (informativo)

Umbral de Hamming <= 5 bits (el de P2). Grupos en evaluacion: 72; grupos formados solo por negativos: 20. Pares entre ajuste y evaluacion: 0.

Grupos con mas de un cuadro:

- AJ1_f0004, AJ1_f0005
- S2_f0007, S2_f0008
- S2_f0021, S2_f0022
- S3_f0001, S3_f0002, S3_f0003, S3_f0006, S3_f0007
