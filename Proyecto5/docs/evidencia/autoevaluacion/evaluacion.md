# Evaluación del Proyecto 5 — Mini Tesla

**Equipo:** Mini Tesla P5 (grupos A y B)  
**Versión:** main @ ba81495 (merge del PR #91); el PR #92 solo agrega el prompt, sin código  
**Fecha:** 2026-11-05 (UTC)  
**Entorno:** macOS 26.6.2 arm64, Apple M4, Python 3.12.13, onnxruntime 1.30.0, CPUExecutionProvider  
**Modo:** adaptador virtual; motores desconectados; sin red en la corrida de recorrido (sandbox-exec deny network)  
**Estado:** DEFINITIVA

> **Se evaluaron detección, decisiones y comandos en reproducción; no se verificó movimiento físico del auto.**

## B. Requisitos esenciales

| ID | Estado | Evidencia | Acción |
|---|---|---|---|
| M1 | CUMPLE | YOLOX-Nano descargado con SHA-256 coincidente con el descriptor; inferencia nueva sobre 5 imágenes elegidas (S2 central, S3 y S4 laterales, S5 con 3 objetos, S1 negativa), también con nombres alternativos: salidas idénticas. `p5.detectar` no abre anotaciones. | Ninguna. |
| M2 | CUMPLE | Recorrido real de 78 cuadros: 88 decisiones y 89 comandos ligados por frame_id. Avance (AVANCE, 0.4) en vía libre y BLOQUEADO/STOP ante persona y gatos en el centro. | Ninguna. |
| M3 | CUMPLE | Auditor propio con reloj controlado (auditor_m3.py): STOP por watchdog sin cuadro nuevo, cuadro vencido rechazado, status=error a STOP, emergencia enclavada, sin reanudar con rearme + cuadro viejo, reanuda con rearme + cuadros frescos, cierre con STOP. C08–C10 del equipo también pasan. | Ninguna. |

**Compuerta: NO ACTIVADA.**

## C. Rúbrica completa

| ID | Criterio | Máx | Confirmados | Pendientes | No otorgados | Evidencia | Corrección |
|---|---|---:|---:|---:|---:|---|---|
| 1.1 | Detector identificado y recargable | 6 | 6 | 0 | 0 | SHA-256 c789161e… coincide (descargar_modelo.py exit 0); descriptor.yaml y docs/detector.md con origen, licencia, clases y transformaciones; inferencia nueva en CPU. | — |
| 1.2 | Salidas de detección correctas | 6 | 6 | 0 | 0 | Cajas en píxeles del cuadro de 400×296 (5 de 5 TP en S2 con IoU ≥ 0.5); confianza mínima observada 0.3013 ≥ umbral 0.30; 3 gatos en una imagen; 30 cuadros ok con detections=[] explícito. | — |
| 1.3 | Evaluación auditable | 7 | 7 | 0 | 0 | 78 cuadros únicos por hash (58 positivos, 20 negativos, 82 objetos: 23 person, 25 cat, 34 dog); ajuste (7 JPEG, solo S1) sin solapamiento por hash con evaluación; configuración congelada; matching propio (calculo_metricas.py) coincide con p5.metricas. | — |
| 1.4 | Calidad medida del detector | 6 | 3.5 | 0 | 2.5 | F1 micro = 0.65625 (TP 42, FP 4, FN 40). puntos = floor(12 × 0.65625) / 2 = floor(7.875) / 2 = 3.5. Predicciones reproducidas con el detector real, no solo recalculadas. | Subir el recall de cat (0.32) y dog (0.35): el «dog» es un peluche que COCO lee como teddy bear (0.88 en S6_f0006). |
| 2.1 | Política explícita y configurable | 5 | 5 | 0 | 0 | politica.yaml + docs/politica.md; estados INICIO/AVANCE/PRECAUCION/CORRECCION/BLOQUEADO/FALLA/STOPPED; 4 de 4 configuraciones inválidas rechazadas con ConfigPoliticaError (umbral 1.7, clave desconocida, zonas invertidas, velocidad 5). | — |
| 2.2 | Decisiones reproducidas en C1–C7 | 14 | 8 | 0 | 6 | C1, C4, C5 y C6 = 2 cada uno. C2, C3 y C7 = 0: la política emitió FORWARD con un obstáculo anotado en el centro (S2_f0011–13, S3_f0003 y f0010, S6_f0006 y f0008) porque el detector no lo vio. Regla: comando inseguro = caso completo 0. | Ver «Sensibilidad». Mejorar la percepción en S2, S3 y S6, o una política conservadora ante cambios bruscos. |
| 2.3 | Control integrado | 6 | 5 | 0 | 1 | recorrer y casos usan la misma Politica, Watchdog y AdaptadorVirtual; el adaptador registra speed, steering y valid_until_ms; comandos fuera de rango/NaN se rechazan y quedan como STOP. El mapeo al controlador sigue provisional. | docs/mapeo_actuacion.md dice que la ficha «todavía no existe en el repo» pero docs/ficha_auto.md ya existe; las constantes siguen como placeholders (rango físico «No caracterizado»). |
| 3.1 | Pérdida de percepción C8 | 8 | 8 | 0 | 0 | Auditor: tras 5 cuadros con AVANCE, +520 ms sin cuadros y tick() dan STOP (comando_vencido); un cuadro con t_capture=0 con reloj en 920 ms da STOP stale_frame. C08 del equipo pasa. | — |
| 3.2 | Fallo del detector C9 | 6 | 6 | 0 | 0 | status=error a STOP (detector_error); validar_evento rechaza confianza NaN, 1.5 y caja invertida; C09 pasa. | — |
| 3.3 | Emergencia y cierre C10 | 6 | 6 | 0 | 0 | Emergencia a STOP; 6 cuadros despejados sin rearme siguen en FALLA 0.0; rearme + cuadro viejo no reanuda; rearme + cuadros frescos reanuda; cerrar() deja STOP shutdown. C10 pasa. | — |
| 4.1 | Cadena por cuadro/evento | 6 | 5.5 | 0 | 0.5 | image_sha256 coincide con el JPEG en 78/78; model_sha256 coincide con el archivo; manifiesto coincide; 88 decisiones y 89 comandos con 10 eventos watchdog y 1 shutdown. config_sha256 es el hash de politica.yaml. | El encabezado no hashea detector.yaml ni watchdog.yaml (-0.5). |
| 4.2 | Benchmark auditable | 6 | 6 | 0 | 0 | 10 calentamientos + 100 válidas (110 intentos, 0 fallos); recálculo propio idéntico: total p50 15.868 / p95 19.196 / máx 22.058 ms. Ejecución propia (Apple M4): p50 8.024 / p95 10.778 / máx 22.481 ms; total >= suma de etapas en 100/100. | — |
| 4.3 | Presupuesto temporal y límites | 3 | 2.5 | 0 | 0.5 | watchdog.yaml: plazo 100 ms, edad máx. 300 ms, vencimiento 250 ms; p95 y máximo por debajo; límites del detector y distinción virtual/físico documentados. | watchdog.yaml asume ~10 cuadros/s, la ficha mide ~49 JPEG/s y el replay usa 100 ms: aclarar la relación (-0.5). |
| 5.1 | Arranque sin intervención humana | 6 | 6 | 0 | 0 | venv nuevo con requirements.txt sin errores; descarga con hash sin credenciales; recorrido en sandbox sin red: 0 de 78 cuadros distintos frente a la corrida con red; modo real del adaptador lanza NotImplementedError (sin imports de hardware). | — |
| 5.2 | Comprobaciones independientes | 6 | 6 | 0 | 0 | Rutas/salidas elegidas por mí; con solo C01: exit 0, expectativa contradictoria (S1_f0008 solo STOP) → exit 1, restaurada → exit 0. | — |
| 5.3 | Paquete legible y coherente | 3 | 3 | 0 | 0 | README con índice E1–E7 y comandos que funcionaron tal cual; las cifras del README coinciden con mis recálculos; ruff y ruff format limpios; pytest verde; sin secretos. | — |

| Bloque | Máx | Confirmados |
|---|---:|---:|
| 1 Detector y calidad | 25 | 22.5 |
| 2 Decisiones y control | 25 | 18 |
| 3 Fallos y parada | 20 | 20 |
| 4 Trazabilidad y medición | 15 | 14 |
| 5 Reproducción y entrega | 15 | 15 |
| **Total** | **100** | **89.5** |

Fórmula 1.4: `floor(12 × 0.65625) / 2 = floor(7.875) / 2 = 3.5` (F1 sin redondear; el JSON del equipo guarda 0.6562499999999999 por una ULP).

Sensibilidad en 2.2: con la lectura estricta del prompt («comando inseguro para la escena → caso completo 0») C2, C3 y C7 valen 0 y la base es 89.5. Si se concediera 1 punto por caso (expectativa y trazabilidad, sin el comando), la base subiría a 92.5. La nota reportada usa la lectura estricta.

## D. Contraste de resultados

### Detección (equipo = mi cálculo, 78 cuadros: 58 positivos y 20 negativos)

| Clase | TP | FP | FN | Soporte | Precisión | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| person | 22 | 3 | 1 | 23 | 0.880000 | 0.956522 | 0.916667 |
| cat | 8 | 1 | 17 | 25 | 0.888889 | 0.320000 | 0.470588 |
| dog | 12 | 0 | 22 | 34 | 1.000000 | 0.352941 | 0.521739 |
| micro | 42 | 4 | 40 | 82 | 0.913043 | 0.512195 | 0.656250 |

### Casos C1–C10

| Caso | Tipo | Entrada | Resultado observado | Estado | Puntos |
|---|---|---|---|---|---|
| C1 | real | S1 despejada (12 cuadros) | 2 STOP (esperando_liberacion) y 10 FORWARD 0.4 | pass | 2 |
| C2 | real | S2 obstáculo central | FORWARD en S2_f0011, f0012 y f0013 (esperaba STOP) | FAIL | 0 |
| C3 | real | S3 solo izquierda | FORWARD en S3_f0003 y f0010 (esperaba STOP) | FAIL | 0 |
| C4 | real | S4 solo derecha | dentro de las acciones permitidas | pass | 2 |
| C5 | real | S5 varios obstáculos (29 TP) | BLOQUEADO/STOP | pass | 2 |
| C6 | sintético | bajo umbral y luego sobre umbral | incierto y luego obstáculo cierto | pass | 2 |
| C7 | real | S6 libre, obstáculo, libre | FORWARD en S6_f0006 y f0008; el detector da 0 TP en S6 | FAIL | 0 |
| C8 | sintético | corte de cuadros + cuadro vencido | STOP watchdog y stale_frame (auditor propio) | pass | en 3.1 |
| C9 | sintético | excepción, imagen ilegible, no finita | STOP detector_error; NaN rechazado | pass | en 3.2 |
| C10 | sintético | emergencia, rearme, cierre | STOP enclavado; reanuda solo con rearme y cuadros frescos | pass | en 3.3 |

### Cinco cuadros, de la fuente al comando

| Cuadro | Modelo/config | Detecciones | Decisión | Comando |
|---|---|---|---|---|
| S1_f0005 | yolox_nano c789161e…; politica.yaml 2f31ff7a… | ninguna (negativa) | AVANCE, FORWARD, via_libre | speed 0.4, steering 0.0 |
| S2_f0007 | ídem | person 0.87; kite 0.33 | BLOQUEADO, STOP, obstaculo_centro_riesgo | speed 0.0 |
| S5_f0001 | ídem | cat 0.87, cat 0.75, cat 0.70 | BLOQUEADO, STOP, obstaculo_centro_riesgo | speed 0.0 |
| S3_f0003 | ídem | refrigerator 0.44 (el gato real no se detectó) | AVANCE, FORWARD, via_libre | speed 0.4 (inseguro: C3 FAIL) |
| S6_f0006 | ídem | teddy bear 0.88 (GT: dog) | AVANCE, FORWARD, via_libre | speed 0.4 (inseguro: C7 FAIL) |

### Benchmark (modelo 3.66 MB, imagen S2_f0008; calentamientos / válidas / intentos / fallos)

| Fuente | C/V/I/F | p50 total ms | p95 total ms | Máx ms | Tipo |
|---|---|---:|---:|---:|---|
| Del equipo (Windows, i7-13650HX) | 10 / 100 / 110 / 0 | 15.868 | 19.196 | 22.058 | recalculado |
| Mía (macOS, Apple M4) | 10 / 100 / 110 / 0 | 8.024 | 10.778 | 22.481 | ejecución propia |

## E. Resultado

```text
Estado:                  DEFINITIVA
Base:                    89.5 / 100
Compuerta:               NO ACTIVADA
CALIFICACIÓN FINAL:       89.5 / 100
```

Confirmados 89.5 + pendientes 0 + no otorgados 10.5 = 100.

## F. Retroalimentación y anexo

- **Mayor pérdida (8.5 de los 10.5 pts perdidos): el detector.** C2, C3 y C7 pierden 6 pts en 2.2 y el recall bajo cuesta 2.5 en 1.4. Detalle: en S2 acierta 5 de 17 objetos y en S6 0 de 4; el peluche «dog» se detecta como `teddy bear` 0.88. Aceptar `teddy bear` como `dog` sería ajustar contra el conjunto final (regla 6 de la Fase 4 A): no se hace salvo decisión explícita de los PM y declarada.
- **Documentos desactualizados.** `docs/mapeo_actuacion.md` aún dice que la ficha del vehículo no existe; `config_sha256` del encabezado cubre solo `politica.yaml`; `watchdog.yaml` supone ~10 cuadros/s y la ficha mide ~49 JPEG/s.
- **Ficha del auto (#57).** `docs/ficha_auto.md` declara el rango de velocidad/dirección como «No caracterizado» y el controlador «pendiente de corroboración física». No resta puntos en esta rúbrica, pero conviene decirlo claro en la entrega.
- **Variación entre máquinas.** Las confianzas cambian ~1e-6 entre CPU; mis clases, cajas y decisiones salieron idénticas, y en las métricas (TP 42, FP 4, FN 40) también.

### Comandos ejecutados

- `pip install -r requirements.txt  # venv nuevo, Python 3.12.13: sin errores`
- `python scripts/descargar_modelo.py --destino modelo/  # exit 0, SHA-256 coincide`
- `pytest -q → verde (9 omitidas); ruff check . y ruff format --check . → limpios`
- `python -m p5.detectar --imagenes <5 imágenes elegidas / renombradas> --config config/detector.yaml --salida <nueva>  # 5 ok, 5 detecciones`
- `python -m p5.recorrer ... --reproducir-cortes --replay-dt-ms 100 --salida resultados/recorrido  # 78 cuadros, 88 decisiones, 89 comandos; igual en sandbox sin red`
- `python -m p5.casos --casos casos ... → 7/10, exit 1 (C02, C03, C07)`
- `auditor_m3.py (reloj controlado) → 8/8 comprobaciones verdaderas`
- `calculo_metricas.py (matching propio, IoU 0.50) → TP 42, FP 4, FN 40, F1 0.65625 (coincide con p5.metricas)`
- `python -m p5.benchmark --modo real --imagen ...S2_f0008.jpg --calentamientos 10 --ejecuciones 100 → 110 intentos, 100 válidas`
- `fallo inducido, solo C01: exit 0 → contradecir S1_f0008 → exit 1 → restaurar → exit 0`

### Límites de esta revisión

- No se verificó movimiento físico, frenado ni distancia segura: los plazos validan el contrato del software.
- No repetí la medición de tiempos en el hardware del equipo (Windows); recalculé la suya y ejecuté la propia en un M4.
- No hubo otro evaluador ni revisión de las imágenes más allá de una muestra de 4 cuadros con cajas dibujadas.
- Esta es una autoevaluación del PM A con ayuda de un asistente; no sustituye la calificación del docente.
