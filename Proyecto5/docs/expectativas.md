# Expectativas C1–C7 (P5-15)

Las expectativas salen de la **geometría de las anotaciones**, no de lo que ya hace el programa. El detector y la política nunca leen estos archivos; solo el runner de casos (P5-13) los usa para comparar.

| Archivo | Qué es |
|---|---|
| `casos/C01.yaml` … `C07.yaml` | Entrada de cada caso: tipo (`real` o `sintetico`), estado inicial, secuencia o eventos, y la ruta de su expectativa |
| `casos/expectativas/C01.yaml` … `C07.yaml` | Expectativa: estados de vía que debe contener la secuencia, plazo, requisitos y justificación |
| `casos/expectativas/cuadros.csv` | Acciones permitidas por cuadro, generadas desde el COCO y el manifiesto (pendiente de las anotaciones de P5-06) |
| `src/p5/expectativas.py` | Script que genera `cuadros.csv` |
| `tests/test_expectativas.py` | Prueba el script con 3 cuadros anotados a mano (`tests/datos_expectativas/`) y la forma de los casos |

## Acciones permitidas por cuadro

Para cada cuadro del manifiesto, el script busca su imagen en el COCO, convierte cada caja de `xywh` a `xyxy` y usa `zonas_ocupadas()` y `en_riesgo()` de `p5/contrato.py`. Solo cuentan las cajas de `clases_obstaculo` (`config/politica.yaml`) que están en riesgo. Las demás quedan en la justificación como «lejos» o «ignorada».

| Estado de la vía | Zonas ocupadas en riesgo | Acciones permitidas |
|---|---|---|
| `libre` | ninguna | FORWARD, STEER_LEFT, STEER_RIGHT, STOP |
| `izq` | solo izquierda | FORWARD, STEER_RIGHT, STOP |
| `der` | solo derecha | FORWARD, STEER_LEFT, STOP |
| `laterales` | izquierda y derecha, centro libre | FORWARD, STOP |
| `centro` | centro (con o sin un lateral) | STOP |
| `bloqueado` | las tres | STOP |

STOP nunca es inseguro. Para que detenerse siempre no apruebe, C1, C3, C4, C6 y C7 exigen además movimiento (requisito `movimiento_minimo`). Nunca se permite girar hacia la zona ocupada.

Una imagen del COCO sin anotaciones es un cuadro **vacío explícito**. Un cuadro del manifiesto que no aparece en el COCO es un cuadro **sin anotar**, y el script lo marca como error.

## Casos

| Caso | Tipo | Secuencia | Qué se exige |
|---|---|---|---|
| C01 | real | seq01 | Acciones por cuadro y al menos un movimiento |
| C02 | real | seq02 | STOP en todo cuadro con el centro ocupado, en el mismo cuadro (`plazo_reaccion_cuadros: 0`) |
| C03 | real | seq03 | No girar a la izquierda; al menos un movimiento |
| C04 | real | seq04 | No girar a la derecha; al menos un movimiento |
| C05 | real | seq05 | STOP con las tres zonas ocupadas |
| C06 | sintético | eventos en el YAML | 0.20 se ignora, 0.40–0.45 avance lento (≤ 0.2), 0.60 STOP, 0.40 tras el bloqueo sigue en STOP |
| C07 | real | seq06 | Movimiento antes, sin movimiento entre el primer y el último cuadro con el centro ocupado, y reanuda a más tardar en 5 cuadros despejados (histéresis de 3 + 2 de margen) |

C06 sigue la política de confianza **declarada** en `config/politica.yaml` (umbral 0.50, incierto desde 0.30, velocidad de precaución 0.2). Si cambian esos valores, se actualiza C06 con justificación.

## Cuando lleguen las anotaciones (P5-06)

```
cd Proyecto5
PYTHONPATH=src python -m p5.expectativas --coco datos/anotaciones.json \
    --manifiesto datos/manifiesto.csv --config config/politica.yaml \
    --salida casos/expectativas/cuadros.csv
```

1. Si sale con código 1, revisar con Emilio cada error: cuadro sin anotar, caja fuera del cuadro o `estado_esperado_via` distinto del calculado.
2. Revisar que cada secuencia tenga los `estados_requeridos` de su caso.
3. Hacer commit de `cuadros.csv` y `cuadros_origen.json` (hashes del COCO, el manifiesto y la configuración) **antes** de la primera corrida de P5-14. Ese commit es el congelado.

## Pendiente de confirmar

- Ids de secuencia `seq01`–`seq06` y su orden S1–S6 (Bryan, #57; Emilio, #58).
- El estado `laterales` (obstáculos a ambos lados con el centro libre) no está en la lista de `estado_esperado_via` de #58 (libre / izq / der / centro / bloqueado).
- `plazo_reaccion_ms: 500` es tentativo hasta conocer el ritmo de captura (#57) y el watchdog (#64).
- El formato de los casos lo consume el runner de Uriel (#65).
