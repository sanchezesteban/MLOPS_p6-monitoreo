# Expectativas C1–C7 (P5-15)

Las expectativas salen de la **geometría de las anotaciones**, no de lo que ya hace el programa. El detector y la política nunca leen estos archivos; solo el runner de casos (P5-13) los usa para comparar.

| Archivo | Qué es |
|---|---|
| `casos/C01.yaml` … `C07.yaml` | Entrada de cada caso: tipo (`real` o `sintetico`), estado inicial, secuencia o eventos, y la ruta de su expectativa |
| `casos/expectativas/C01.yaml` … `C07.yaml` | Expectativa: estados de vía que debe contener la secuencia, plazo, requisitos y justificación |
| `casos/expectativas/cuadros_S1.csv` … `cuadros_S6.csv` | Acciones permitidas por cuadro, una por secuencia, generadas desde el COCO y `datos/evaluacion/capturas.csv` (pendientes de las anotaciones de P5-06) |
| `casos/expectativas/cuadros_origen.json` | Hashes del COCO, el manifiesto y la configuración, conteo por estado y errores |
| `src/p5/expectativas.py` | Script que genera los `cuadros_<secuencia>.csv` |
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

Una imagen del COCO sin anotaciones es un cuadro **vacío explícito**. Un cuadro del manifiesto que no aparece en el COCO es un cuadro **sin anotar**, y el script lo marca como error. El COCO se busca por `file_name` igual al `path` de `capturas.csv` (por ejemplo `S1/S1_0000000000_<uuid>.jpg`) o, si no, por el nombre del archivo.

### Identificadores y un CSV por secuencia

- `frame_id` es el mismo que asigna el recorrido (`p5.recorrer`, P5-14): los UUID de #79 pasan a `S1_f0001`, `S1_f0002`, … en el orden del manifiesto. El UUID original queda en `frame_id_origen`.
- Se escribe un `cuadros_<secuencia>.csv` por secuencia porque el runner de P5-13 compara **todas** las filas del CSV de un caso contra lo que observó.

### Verificación cruzada con el manifiesto

`capturas.csv` no trae el estado de la vía, pero sí `scene_label` y `outside_risk`. El script sale con 1 si la geometría anotada los contradice:

| Manifiesto | Se exige |
|---|---|
| `despejado` | estado `libre` |
| `obstaculo`, `outside_risk=1` | estado `libre` y al menos una caja de obstáculo anotada (lejos) |
| `obstaculo`, `outside_risk=0` | algún obstáculo en riesgo (estado distinto de `libre`) |

## Casos

| Caso | Tipo | Secuencia | Qué se exige |
|---|---|---|---|
| C01 | real | S1 | Acciones por cuadro y al menos un movimiento |
| C02 | real | S2 | STOP en todo cuadro con el centro ocupado, en el mismo cuadro (`plazo_reaccion_cuadros: 0`) |
| C03 | real | S3 | No girar a la izquierda; al menos un movimiento |
| C04 | real | S4 | No girar a la derecha; al menos un movimiento |
| C05 | real | S5 | STOP con las tres zonas ocupadas |
| C06 | sintético | eventos en el YAML | 0.20 se ignora, 0.40–0.45 avance lento (≤ 0.2), 0.60 STOP, 0.40 tras el bloqueo sigue en STOP |
| C07 | real | S6 | Movimiento antes, sin movimiento entre el primer y el último cuadro con el centro ocupado, y reanuda a más tardar en 4 cuadros despejados (histéresis de 3 + 1 de margen; S6 solo tiene 4 tras el último centro) |

Las secuencias son las de evaluación de P5-05 (#79, `datos/evaluacion/capturas.csv`). El recorrido las reproduce a **100 ms fijos** por cuadro, así que `plazo_reaccion_ms` es 100 en todos los casos: un cuadro, igual que `plazo_reaccion_ms` de `config/watchdog.yaml`. Con `plazo_reaccion_cuadros: 0` el STOP sale en el mismo cuadro donde la anotación pone el obstáculo. Los eventos sintéticos de C06 van también cada 100 ms.

C06 sigue la política de confianza **declarada** en `config/politica.yaml` (umbral 0.50, incierto desde 0.30, velocidad de precaución 0.2). Si cambian esos valores, se actualiza C06 con justificación.

## Cuando lleguen las anotaciones (P5-06)

Las anotaciones llegan por partes (primero S1 y S5), así que se puede correr solo con las secuencias ya anotadas:

```
cd Proyecto5
PYTHONPATH=src python -m p5.expectativas --coco datos/anotaciones.json     --manifiesto datos/evaluacion/capturas.csv --config config/politica.yaml     --salida casos/expectativas --secuencias S1 S5
```

Sin `--secuencias` se procesan las seis y cualquier cuadro sin anotar es un error.

1. Si sale con código 1, revisar con Emilio cada error: cuadro sin anotar, caja fuera del cuadro o estado que contradice `scene_label`/`outside_risk`.
2. Revisar que cada secuencia tenga los `estados_requeridos` de su caso.
3. Hacer commit de los `cuadros_<secuencia>.csv` y `cuadros_origen.json` **antes** de la primera corrida de P5-14 con esas secuencias. Ese commit es el congelado.

## Pendiente de confirmar

- El estado `laterales` (obstáculos a ambos lados con el centro libre) no está en la lista de `estado_esperado_via` de #58 (libre / izq / der / centro / bloqueado).
- En S6 los cuadros con obstáculo deben quedar en el centro en riesgo para que C07 tenga el estado `centro` que exige.
