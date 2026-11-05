# Ensayo desde un clon limpio (P5-17, #69)

Ensayo de la entrega como lo haría el evaluador: copia limpia del `main` final, entorno
virtual nuevo, sin pesos, sin credenciales ni variables de AWS, y **cada comando del README
tal como está escrito**. Lo corrió el PM del grupo B (Esteban) el 4 nov 2026.

| Campo | Valor |
|---|---|
| Commit ensayado | `ba81495` (merge del #91, README final) |
| Entorno | Linux x86_64, Intel Xeon 2.10 GHz (2 CPU lógicas), Python 3.12.3, ONNX Runtime 1.30.0 CPU |
| Modo | CPU, adaptador virtual, motores desconectados |
| Salidas | carpetas nuevas en `resultados/` y `mediciones/` (no versionadas) |

## 1. Bitácora de comandos del README

Detalle completo, con la salida y el código de salida de cada paso: [`bitacora.txt`](bitacora.txt).

| Paso del README | Resultado | Exit |
|---|---|---:|
| `pip install -r requirements.txt -r requirements-capturas.txt` | instalación limpia | 0 |
| `pytest` | 603 passed, 9 skipped | 0 |
| `ruff check .` · `ruff format --check .` | limpios | 0 |
| `python scripts/descargar_modelo.py --destino modelo/` | SHA-256 `c789161e…` coincide con el descriptor | 0 |
| `p5.detectar` sobre `datos/evaluacion/S1` | 12 cuadros `ok`, 0 detecciones (vía libre) | 0 |
| `p5.recorrer --detector real --reproducir-cortes --replay-dt-ms 100` | 78 cuadros, 88 decisiones, 89 comandos | 0 |
| `exportar_eventos.py --salida resultados/eventos` | 6 secuencias | 0 |
| `p5.casos` | 7/10 (C02, C03 y C07 fallan por recall del detector, documentado) | 1 (esperado) |
| `p5.metricas` | TP 42, FP 4, FN 40, F1 0.65625 | 0 |
| `p5.benchmark --modo real` | 10 calentamientos + 100 válidas, 0 fallos | 0 |

El código de salida 1 del runner es el comportamiento correcto: hay casos que no cumplen su
expectativa y el runner no los oculta.

## 2. Imagen renombrada e imagen ilegible (1.2, 3.2)

[`renombrada/`](renombrada/): cinco imágenes de evaluación (una vía libre, un obstáculo
central, uno a la izquierda, uno a la derecha y tres gatos) copiadas con nombres neutros
(`muestra_1.jpg` … `muestra_5.jpg`), más un JPEG truncado a 2000 bytes.

- Las cinco renombradas dan **exactamente** el mismo `status`, hash de imagen, clases,
  confianzas y cajas que las originales: el detector no usa el nombre del archivo.
- `truncada.jpg` sale con `status=error` (`imagen ilegible: … truncated`) y `detections=[]`;
  nunca como vía libre.

Archivos: [`comparacion.txt`](renombrada/comparacion.txt),
[`correspondencia.txt`](renombrada/correspondencia.txt), las detecciones de ambas corridas y
su `run.json`.

## 3. Fallo inducido del runner (5.2)

[`fallo_inducido/`](fallo_inducido/): en una **copia** de `casos/` se cambió la acción
permitida de `S5_f0005` de `STOP` a `FORWARD` ([`cambio.diff`](fallo_inducido/cambio.diff)),
contradiciendo el comando que la política emite correctamente ante tres obstáculos.

| Corrida | Resultado | Exit |
|---|---|---:|
| C05 con la expectativa original | `pass` | 0 |
| C05 con la expectativa alterada | `fail`: `S5_f0005: accion STOP no permitida (esperaba ['FORWARD'])` | 1 |

La copia se borró al terminar; `casos/` no se modificó. Salida literal:
[`salida.txt`](fallo_inducido/salida.txt).

## 4. Recálculo independiente de métricas (1.3, 1.4)

[`recalcular_metricas.py`](recalcular_metricas.py) no importa nada de `p5`: lee el COCO y el
JSONL y empareja por cuadro y clase, en orden de confianza, con la caja real libre de mayor
IoU ≥ 0.50, usando cada caja real una sola vez.

| Predicciones | TP | FP | FN | Precisión | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|
| Versionadas (`resultados/recorrido_metricas_78_…`, SHA-256 `ce503347…`) | 42 | 4 | 40 | 0.913043 | 0.512195 | **0.656250** |
| Nuevas de este ensayo (`p5.recorrer`) | 42 | 4 | 40 | 0.913043 | 0.512195 | **0.656250** |

Por clase (las dos corridas son iguales): person 22/3/1 (F1 0.917), dog 12/0/22 (F1 0.522),
cat 8/1/17 (F1 0.471). Coincide entero por entero con
[`resultados/metricas/metricas.json`](../../../resultados/metricas/metricas.json).
Criterio 1.4: `floor(12 × 0.65625) / 2 = 3.5`.

Salidas: [`recalculos/metricas_versionadas.json`](recalculos/metricas_versionadas.json) y
[`recalculos/metricas_ensayo.json`](recalculos/metricas_ensayo.json).

## 5. Recálculo independiente de p50/p95 (4.2)

[`recalcular_percentiles.py`](recalcular_percentiles.py) no usa numpy: descarta calentamientos
y fallos de `tiempos.csv` y calcula la interpolación lineal con la posición `(n − 1)·q`.

| Corrida | Válidas | Total local p50 | p95 | Máx. | ¿Igual a `resumen.json`? |
|---|---:|---:|---:|---:|---|
| Versionada (`mediciones/real_cpu_predeterminado_…`, i7-13650HX) | 100 | 15.868 ms | 19.196 ms | 22.058 ms | sí, las 5 etapas |
| Este ensayo (Xeon 2.10 GHz, 2 CPU) | 100 | 18.242 ms | 23.045 ms | 24.357 ms | sí, las 5 etapas |

En las dos máquinas, el p95 y el máximo quedan por debajo de `plazo_reaccion_ms` (100 ms).
Los tiempos dependen de la CPU; la corrida versionada no se sustituye.

Salidas: [`recalculos/percentiles_versionados.json`](recalculos/percentiles_versionados.json) y
[`recalculos/percentiles_ensayo.json`](recalculos/percentiles_ensayo.json).

## 6. Límites del ensayo

- Se evaluaron detección, decisiones y comandos en reproducción; **no se verificó
  movimiento físico del auto**.
- Las confianzas pueden variar del orden de 1e-6 entre máquinas; no cambian clases, cajas,
  decisiones ni métricas (sección 4).
- La autoevaluación con el prompt del profesor la agrega el PM A (Sebastián) después del tag
  `p5-entrega`.

Reproducir los recálculos (desde `Proyecto5/`, tras «Recorrido integral» y «Benchmark»):

```bash
python docs/evidencia/ensayo/recalcular_metricas.py \
    --gt datos/anotaciones.json --pred resultados/recorrido/detecciones.jsonl
python docs/evidencia/ensayo/recalcular_percentiles.py \
    --tiempos mediciones/reproduccion_p5_08/tiempos.csv \
    --resumen mediciones/reproduccion_p5_08/resumen.json
```
