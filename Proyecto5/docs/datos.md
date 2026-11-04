# Datos de evaluación y verdad de referencia (P5-06, #58)

Paquete etiquetado de E3: cuadros de cámara como JPEG, manifiesto temporal, cajas y clases reales, estado esperado de la vía por cuadro, partición ajuste/evaluación y congelado por SHA-256. Las cifras vigentes **no se escriben a mano aquí**: salen de [`conteo_datos.md`](conteo_datos.md) (generado) y las discrepancias de [`discrepancias_datos.md`](discrepancias_datos.md) (generado).

> **Estado: fase 1.** Anotadas S1, S5 y ajuste. S2, S3, S4 y S6 se recapturan con una persona real (ver «Recaptura») y se anotan en la fase 2; hasta entonces el manifiesto y el COCO contienen solo S1 y S5, y las metas de E3 todavía no se cumplen.

En este documento, **verificado** = comprobado con archivos y comandos del repositorio; **declarado** = afirmado por una persona y no comprobable con archivos.

## Archivos

| Archivo | Qué es | Lo lee |
|---|---|---|
| `datos/evaluacion/S1..S6/*.jpg`, `datos/ajuste/S1/*.jpg` | Cuadros de la ESP32-CAM, 400×296, bytes originales de P5-05 | detector y recorrido (entrada) |
| `datos/evaluacion/capturas.csv`, `datos/ajuste/capturas.csv` | Metadatos de captura de P5-05 (Bryan); fuente de `t_capture_ms`, hash y orden | recorrido (entrada); este paquete |
| `datos/anotaciones.json` | COCO de evaluación: verdad de referencia | solo evaluación (métricas, expectativas) |
| `datos/anotaciones_ajuste.json` | COCO de ajuste, aparte para no repetir nombres de archivo | solo evaluación |
| `datos/manifiesto.csv`, `datos/manifiesto_ajuste.csv` | Manifiesto de #58 con `estado_esperado_via` | solo evaluación |
| `datos/HASHES.sha256` | Congelado (fase 2) | `scripts/verificar_hashes.py` |
| `docs/conteo_datos.md`, `docs/conteo_datos.json` | Conteos y metas (generados) | personas |
| `docs/discrepancias_datos.md` | Reporte de discrepancias (generado) | personas |
| `docs/revision/hoja_<secuencia>.jpg` | Hojas de contacto con cajas, tercios y línea de riesgo dibujadas sobre copias | personas; no son datos |

## Procedencia

Los JPEG, sus tiempos, sesiones, etiquetas de escena y la selección vienen de P5-05 (#57, PR #79). Ver la [nota de entrega de Bryan](entrega_emilio_issue57.md), la [procedencia](procedencia_capturas.json) y la [normalización temporal de S1](normalizacion_temporal_S1.md). Este paquete no recodifica, renombra, mueve ni reordena esos archivos ni sus CSV.

Verificado el 3 nov 2026 sobre `main` (`6980269`): `python scripts/validar_capturas.py --issue57` aprueba; el SHA-256 recalculado de los 85 JPEG coincide con los CSV; todas las imágenes miden 400×296, sin etiqueta EXIF de orientación; cada secuencia del CSV ya viene en orden de `t_capture_ms` estrictamente creciente. La orientación (no volteadas) se revisó visualmente en S1, S5 y ajuste.

## Esquema

### `frame_id`

`frame_id = <sequence_id>_fNNNN`, consecutivo dentro de cada secuencia en orden de `t_capture_ms` (`S1_f0001`, `S1_f0002`, …). Es el mismo que asignan `p5.recorrer` (P5-14) y `p5.expectativas` (P5-15) al leer `capturas.csv`, que numeran en el orden de las filas; por eso `p5.datos.leer_capturas` **se detiene** si una secuencia no viene ordenada, en vez de numerar distinto. El identificador original de P5-05 se conserva en `frame_id_origen` (en S1 es un UUID; en S2–S6 viene como `S2_<uuid>`).

Ajuste usa `sequence_id = AJ1` (de su `S1` original, conservado en `sequence_id_origen`) y `frame_id = AJ1_f0001…`: nunca choca con evaluación y cumple la regla del contrato de que `frame_id` empiece con `{sequence_id}_`.

### Manifiesto (`datos/manifiesto.csv`)

Columnas de #58, en este orden: `sequence_id, frame_id, t_capture_ms, ruta, ancho, alto, sha256, estado_esperado_via`. Después, columnas de trazabilidad (un `csv.DictReader` que no las pide las ignora): `frame_id_origen, sequence_id_origen, session_id, n_cajas, n_obstaculos, n_en_riesgo, zonas_en_riesgo, scene_label_p505, outside_risk_p505`.

- `t_capture_ms`: el relativo por secuencia de `capturas.csv`, sin normalizar (S1 conserva su pausa real entre sesiones). El contrato exige `t_capture_ms` creciente por `run_id`: si una corrida encadena secuencias, el recorrido debe rehacer el reloj. `p5.recorrer` (P5-14) ya lo hace (100 ms por cuadro más un hueco entre secuencias) y conserva el original como `t_capture_origen_ms`; con `--reproducir-cortes` conserva además el delta real al cambiar `session_id` y lo registra en `cortes.json`.
- `ruta`: relativa a `Proyecto5/` (`datos/evaluacion/S1/<archivo>.jpg`), idéntica al `file_name` del COCO.
- `sha256` y `ancho`/`alto`: se recalculan desde los bytes del JPEG al construir el manifiesto y deben coincidir con `capturas.csv`.
- `estado_esperado_via` ∈ `libre, izq, der, laterales, centro, bloqueado`. Se calcula **desde las cajas anotadas** con `p5.contrato.zonas_ocupadas` y `p5.contrato.en_riesgo` (tercios de W; riesgo si `y2 ≥ H/2`), solo con las clases `clases_obstaculo` de `config/politica.yaml` y solo con cajas en riesgo:

| Estado | Zonas ocupadas en riesgo |
|---|---|
| `libre` | ninguna (incluye cuadros con obstáculos solo lejos) |
| `izq` / `der` | solo izquierda / solo derecha |
| `laterales` | izquierda y derecha, centro libre |
| `centro` | centro, con o sin un lateral |
| `bloqueado` | las tres |

`laterales` no está en la lista de #58 (cinco valores), pero es el criterio de `p5.expectativas` (Ikram); se acepta como sexto valor por decisión del 3 nov.

### COCO (`datos/anotaciones.json`)

- `bbox` en `xywh`, píxeles del cuadro original, origen arriba-izquierda; `area = w·h`; `iscrowd = 0`.
- `categories` con los índices COCO del detector (`modelo/descriptor.yaml`, YOLOX-nano): `person = 0`, `cat = 15`, `dog = 16`. **No** son los `category_id` oficiales de un JSON COCO (1/17/18). `p5.metricas` (#59) y `p5.expectativas` emparejan por `name`, así que el número no influye.
- Una entrada en `images` por cuadro revisado, con `id` estable (`S5_f0012` → 5012) y campos extra `sequence_id`, `frame_id`, `frame_id_origen`, `t_capture_ms`, `sha256` y `sin_objetos`.
- **Vacío explícito = imagen en `images` sin ninguna anotación** (la convención COCO que leen `p5.expectativas` y `p5.metricas`). `sin_objetos: true` es solo un campo informativo que pone el anotador; ningún cálculo depende de él, y el manifiesto marca error si `sin_objetos: true` convive con anotaciones. Un cuadro **ausente** de `images` es un cuadro sin anotar, y es error.

## Regla de anotación

- La verdad de referencia la decidió **Emilio (A2) a mano**, cuadro por cuadro, en el anotador local (`scripts/anotador/`). **No hubo pre-anotación**: ni el detector ni ningún otro modelo propusieron cajas, y las etiquetas de escena de P5-05 no se convirtieron en cajas. El anotador no ejecuta modelos.
- Se anota toda instancia **identificable** de `person`, `dog` o `cat`, incluidas las laterales, las que quedan fuera de la zona de riesgo y las cortadas por el borde. Caja ajustada al **sujeto representado** (en S5, la persona o animal en la pantalla del teléfono), no al teléfono ni a reflejos.
- La caja encierra **toda la parte visible** del sujeto, como en COCO. En S5 las cajas de personas incluyen sus brazos (por ejemplo, un brazo que abraza a la persona de al lado), aunque eso haga que las cajas de personas vecinas se encimen. La decisión se tomó el 3 nov al revisar con zoom S5_f0009 y S5_f0011: con cajas solo de cabeza y torso, una detección correcta del detector, entrenado con esa convención, podía quedar por debajo de IoU 0.50 y contar como FP + FN.
- Lo que no se puede identificar como una de esas clases no se anota y se documenta abajo.
- Las guías (tercios y `y = H/2`) solo se dibujan en pantalla; los JPEG se abren en modo lectura.

### Casos dudosos no anotados

| Cuadro | Región aproximada (px, xyxy) | Decisión y motivo |
|---|---|---|
| `S5_f0011` | x 325–337, y 282–295 (borde inferior derecho de la pantalla del teléfono) | No anotado. Forma pequeña cortada por el borde; podría ser la coronilla de una cuarta persona, pero no se puede identificar como persona. Decisión de Emilio, 3 nov. |

`S5_f0009` se revisó con zoom: el brazo que asoma a la izquierda pertenece al hombre del centro (abraza a las dos mujeres); son tres personas, sin una cuarta, y la caja del hombre incluye su brazo.

## Recaptura de S2, S3, S4 y S6

En `docs/detector.md` ([PR #82](https://github.com/sebastian0023/Proyecto-3-Clasificador-de-imagenes/pull/82), P5-09), Edith encontró que, con el detector real YOLOX-nano, en S2 y S6 el detector ve el teléfono como `tv` y deja de ver al sujeto en pantalla, lo que hace fallar C7. El 3 nov Sebastián (PM A) decidió recapturar S2, S3, S4 y S6 con una persona real; S1 y S5 no cambian. Las versiones anteriores de S2, S3, S4 y S6 (estímulos en teléfono) **no se anotaron**. La recaptura la sube Bryan (P5-05); al llegar se repite la validación de P5-05, el análisis de pHash y esta anotación.

## Partición ajuste/evaluación

- **Evaluación:** las secuencias S1–S6 completas. No se reparten cuadros contiguos de una secuencia entre conjuntos.
- **Ajuste:** `AJ1` (S1 de ajuste de P5-05), 7 cuadros negativos de sesiones distintas a evaluación. **Limitación declarada: ajuste no tiene positivos.**
- Verificado: evaluación y ajuste no comparten JPEG, SHA-256, `frame_id` ni `session_id`, y no hay pares casi duplicados por pHash entre ellos (ver `conteo_datos.md`). La independencia de escena de ajuste se apoya en la revisión visual autorizada por el PM en P5-05 (declarado).

### Configuración de referencia (no congelada por este paquete)

`config/*.yaml` no entra en `datos/HASHES.sha256`: es de otros integrantes. Como referencia, al 3 nov 2026 en `main` (`6980269`):

| Archivo | SHA-256 |
|---|---|
| `config/politica.yaml` | `2f31ff7a17c2277fa0c39ab14e038e9d3dbfc8c3ac109e16515b789727595ac9` |
| `config/detector.yaml` | `677098403456a3708760223574b6d9c9b3cc758e93b80d02e385ac7e90182d03` (igual al `config_sha256` de `docs/detector.md`) |

**Pendiente (Sebastián, PM A, y Edith, A1):** declarar por escrito que el umbral de confianza y el NMS del detector no se ajustaron con el conjunto de evaluación, y qué datos de ajuste se usaron (o que no hubo ajuste). Criterio 1.3 del evaluador.

## Separación entre entradas de inferencia y etiquetas (criterio 5.3)

El detector y la política **no leen** `datos/anotaciones*.json`, `datos/manifiesto*.csv` ni `estado_esperado_via`, y `p5.datos` (que sí los lee) no se importa desde el detector, la política ni el recorrido.

Verificado en código (3 nov 2026):

- `p5.recorrer` (rama `p5-14-recorrido-integral`, `dd79977`, `leer_manifiesto`, líneas 121–150) recorre `capturas.csv` y solo lee `status`, `error_msg`, `t_capture_ms`, `image_width`, `image_height`, `image_path`/`path`, `sha256`, `sequence_id` y `frame_id`. **No lee `scene_label` ni `outside_risk`**, aunque estén en el CSV, y su `Frame` no tiene campos de etiqueta.
- `src/p5/detector_onnx.py`, `src/p5/detectar.py` y `src/p5/politica.py` (en `main`) no abren anotaciones ni expectativas: fuera de los módulos de datos y evaluación (`p5.datos`, `p5.duplicados`, y en sus ramas `p5.expectativas` y `p5.metricas`), `src/` no lee COCO, `scene_label` ni `estado_esperado` (la única mención, en `detector_onnx.py`, dice que no abre anotaciones), y ningún módulo de inferencia o control importa `p5.datos`.
- Por eso el recorrido se alimenta de `capturas.csv` (`--datos datos/evaluacion --manifiesto datos/evaluacion/capturas.csv`), no de `datos/manifiesto.csv`: no se agregan columnas alias para que el recorrido pueda leer el archivo que contiene la verdad de referencia.

## Limitaciones

- S5 usa estímulos 2D (personas y animales en la pantalla de un teléfono), no sujetos físicos; la metodología la confirmó Sebastián en el PR #79 (declarado).
- Escena doméstica de interior, una sola cámara, poca luz en varias tomas.
- Ajuste sin positivos: no caracteriza la respuesta ante obstáculos.
- Los JPEG de S1 tienen nombres históricos cuyo número no es su `t_capture_ms`; la fuente de verdad temporal es `capturas.csv`.
- Casi duplicados: varios cuadros consecutivos de una secuencia son casi iguales por pHash; la meta de «únicos» se cuenta por SHA-256 y el pHash se reporta como informativo, con sus grupos.

## Comandos

```bash
cd Proyecto5
python scripts/anotador/servidor.py --secuencias S1 S5 AJ1    # anotar (http://127.0.0.1:8765)
python scripts/construir_manifiesto.py --secuencias S1 S5 AJ1  # manifiestos + discrepancias
pip install -r requirements.txt -r requirements-datos.txt      # solo para el pHash
python scripts/contar_datos.py --secuencias S1 S5 AJ1          # conteo_datos.md/.json
python scripts/revisar_anotaciones.py --hojas docs/revision --secuencias S1 S5 AJ1
python scripts/congelar_datos.py                               # datos/HASHES.sha256 (fase 2)
python scripts/verificar_hashes.py                             # Linux y Windows
sha256sum -c datos/HASHES.sha256                               # alternativa en Linux
```

En la fase 2, los mismos comandos sin `--secuencias`.
