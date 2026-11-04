# Conteo de la verdad de referencia (P5-06)

Generado por `scripts/contar_datos.py` con `--secuencias S1 S5 AJ1`. No editar a mano: se regenera.
Positivo = cuadro con al menos una caja de `clases_obstaculo` (incluidas laterales y
fuera de riesgo); negativo = cuadro sin cajas (vacio explicito).

## Metas de E3 / #58 (evaluacion)

| Meta | Valor | Minimo | Cumple |
|---|---:|---:|---|
| unicos_sha256 | 24 | 60 | **no** |
| secuencias | 2 | 6 | **no** |
| positivos | 12 | 20 | **no** |
| negativos | 12 | 20 | **no** |

## evaluacion

Cuadros 24, unicos por SHA-256 24 (duplicados exactos 0), positivos 12, negativos 12.

| Secuencia | Cuadros | Positivos | Negativos | Estados esperados |
|---|---:|---:|---:|---|
| S1 | 12 | 0 | 12 | libre 12 |
| S5 | 12 | 12 | 0 | bloqueado 12 |

Instancias por clase: cat 12, dog 12, person 12. Cajas: en_riesgo 36.

## ajuste

Cuadros 7, unicos por SHA-256 7 (duplicados exactos 0), positivos 0, negativos 7.

| Secuencia | Cuadros | Positivos | Negativos | Estados esperados |
|---|---:|---:|---:|---|
| AJ1 | 7 | 0 | 7 | libre 7 |

Instancias por clase: ninguna. Cajas: ninguna.

JPEG con el mismo SHA-256 en ajuste y evaluacion: 0.

## Casi duplicados por pHash (informativo)

Umbral de Hamming <= 5 bits (el de P2). Grupos en evaluacion: 24; grupos formados solo por negativos: 12. Pares entre ajuste y evaluacion: 0.

Grupos con mas de un cuadro:

- AJ1_f0004, AJ1_f0005
