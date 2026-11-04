# Detector de objetos (P5-09, #61)

Este documento reúne lo que el evaluador revisa del detector: identidad, transformaciones, umbrales congelados, ajuste y límites conocidos. Las cifras salen de las corridas que se enlazan en cada sección. No hay números escritos a mano.

## 1. Identidad y licencia

| Campo | Valor |
|---|---|
| Modelo | YOLOX-Nano (`yolox_nano.onnx`), detector de una etapa sin anclas |
| Origen | [Megvii-BaseDetection/YOLOX](https://github.com/Megvii-BaseDetection/YOLOX), release `0.1.1rc0` |
| Entrenamiento | COCO 2017, 80 clases. El equipo no lo reentrenó ni lo adaptó |
| Licencia | Apache-2.0 |
| Pesos | `https://github.com/Megvii-BaseDetection/YOLOX/releases/download/0.1.1rc0/yolox_nano.onnx` (descarga pública, sin credenciales) |
| Tamaño | 3 659 407 bytes |
| SHA-256 | `c789161ed43c8269fcd4e67c67eeeb4e80c622da2eb296a20bc6007bd18a0b7d` |
| Runtime | ONNX Runtime 1.30.0, `CPUExecutionProvider` (fijado en `requirements.txt`) |
| Descriptor | [`modelo/descriptor.yaml`](../modelo/descriptor.yaml): URL, bytes, hash, licencia, entrada/salida y las 80 clases |

Los pesos no van en Git. `scripts/descargar_modelo.py` los descarga y solo los guarda si el SHA-256 y el tamaño coinciden; si no, sale con código 1 y no deja archivo. `DetectorONNX.desde_config` vuelve a calcular el hash antes de cargar el modelo y rechaza cualquier otro archivo. Evidencia: [`evidencia/p5-03-descarga.txt`](evidencia/p5-03-descarga.txt).

```bash
cd Proyecto5
python scripts/descargar_modelo.py --destino modelo/
PYTHONPATH=src python -m p5.detectar --imagenes <carpeta|archivos...> --config config/detector.yaml --salida <carpeta nueva>
```

Detrás de un proxy que intercepta TLS, `SSL_CERT_FILE` (o `REQUESTS_CA_BUNDLE`) apunta al PEM de su CA.

## 2. Clases y mapeo

El detector entrega las 80 clases COCO. `class_name` se toma del descriptor con el índice `class_id`, así que nombre e índice siempre coinciden. La política ([`config/politica.yaml`](../config/politica.yaml)) usa solo tres como obstáculo:

| Clase | `class_id` COCO |
|---|---:|
| `person` | 0 |
| `cat` | 15 |
| `dog` | 16 |

Las otras 77 clases (por ejemplo `tv` o `traffic light`) salen en el JSONL, pero la política las ignora. Una prueba (`tests/test_descargar_modelo.py`) verifica que las clases de obstáculo de la política coincidan con estos índices del descriptor.

## 3. Preprocesamiento y posprocesamiento

Implementación en [`src/p5/detector_onnx.py`](../src/p5/detector_onnx.py). Parámetros en [`config/detector.yaml`](../config/detector.yaml), que rechaza claves desconocidas y valores fuera de rango.

**Entrada.** El cuadro completo se lee en RGB y se convierte a BGR 0–255 `float32`, sin normalizar, con forma `[1, 3, 416, 416]`. Se escala con `r = min(416/H, 416/W)` (Pillow bilineal), se coloca arriba a la izquierda y se rellena con 114 (letterbox, sin deformar la imagen). Las cámaras de 400 × 296 quedan con `r = 1.04`.

**Salida.** El tensor `output` tiene forma `[1, 3549, 85]`, con rejillas de stride 8, 16 y 32. Se decodifica así:

- centro: `(o + celda) · stride`
- ancho y alto: `exp(o) · stride`
- confianza: `objectness · clase`

| Paso | Valor congelado |
|---|---|
| Umbral de confianza | 0.30 (igual a `minimo_incierto` de la política, para no filtrar lo que la política usa) |
| NMS | por clase, IoU 0.45 |
| Máximo de detecciones | 100 por cuadro |
| Regreso al cuadro original | `bbox / r`, recorte a `[0, W] × [0, H]`, 2 decimales y se descartan las cajas sin área |

**Fallos.** Hay cuatro casos que no pueden confundirse con una escena despejada:

- imagen ilegible o truncada
- excepción del runtime
- salida con NaN o infinito
- salida con forma inesperada

En los cuatro, el evento sale con `status=error` y `error_msg`. Una imagen sin objetos sale con `status=ok` y `detections=[]`.

## 4. Ajuste y congelado

- **No hubo ajuste.** El modelo, el umbral y el NMS se eligieron sin correr el detector sobre `datos/evaluacion/` ni sobre `datos/ajuste/`.
  - El umbral 0.30 viene de la política (acuerdo de los PM).
  - El NMS 0.45 es el valor por defecto de YOLOX.
  - YOLOX-Nano se eligió por tamaño y velocidad en CPU, no por resultados en nuestras imágenes.
  - No se compararon modelos sobre el conjunto de evaluación.
- **Congelado.** `config/detector.yaml` quedó fijo en el commit `e9b964b` (2026-11-03 15:24 -0600) y no ha cambiado desde entonces.
  - `config_sha256`: `677098403456a3708760223574b6d9c9b3cc758e93b80d02e385ac7e90182d03`. Es el mismo valor que lleva cada `run.json`.
  - El congelado es anterior a las métricas de #59 (P5-07), que todavía no se han corrido.
- **Corrida de diagnóstico.** La corrida S2/S6 de la sección 5 es posterior al congelado y no cambió ningún parámetro. Si alguien cambia el modelo o los umbrales a partir de lo que se ve ahí, ese cambio queda contaminado por el conjunto de evaluación y hay que declararlo (rúbrica 1.3).

## 5. Resultados en S2 y S6 (detector real + política real)

**Corrida.** Commit `6980269`, run `det-p5-09-s2-s6`, con los 29 cuadros de [`datos/evaluacion/S2`](../datos/evaluacion/S2) (17) y [`S6`](../datos/evaluacion/S6) (12). Cada secuencia pasó por `p5.politica.Politica` en orden de tiempo, con el estado reiniciado al empezar la secuencia.

**Archivos.**

- [`evidencia/p5-09/run.json`](evidencia/p5-09/run.json): cabecera con los hashes
- [`detecciones.jsonl`](evidencia/p5-09/detecciones.jsonl): eventos del contrato
- [`decisiones_politica.jsonl`](evidencia/p5-09/decisiones_politica.jsonl): decisión por cuadro
- [`hoja_contacto.jpg`](evidencia/p5-09/hoja_contacto.jpg): los 29 cuadros con sus cajas (rojo: clase de obstáculo; cian: otra clase)

```bash
PYTHONPATH=src python -m p5.detectar --imagenes datos/evaluacion/S2 datos/evaluacion/S6 \
    --config config/detector.yaml --salida <carpeta nueva> --run-id det-p5-09-s2-s6
```

> **Alcance.** Todavía no existen las anotaciones COCO (#58). Por eso la columna «Estímulo» viene de la etiqueta de escena de `capturas.csv` y de una revisión visual, no de cajas anotadas. Aquí no hay TP/FP/FN ni IoU; esas métricas son de #59. Lo que esta sección muestra es si el detector ve el obstáculo y qué hace la política con eso.

### S2: obstáculo central (17 cuadros: 13 en riesgo, 4 fuera de riesgo)

| `frame_id` | t (ms) | Estímulo en pantalla | Detecciones (≥ 0.30) | Política |
|---|---:|---|---|---|
| cli_00000 | 0 | persona | `person` 0.55 centro/riesgo; `tv` 0.51 | STOP `obstaculo_centro_riesgo` |
| cli_00001 | 21265 | persona | solo `tv` 0.53 | STOP `esperando_liberacion` |
| cli_00002 | 23453 | persona | solo `tv` 0.39 | STOP `esperando_liberacion` |
| cli_00003 | 45734 | persona | `person` 0.64 centro/riesgo; `tv` 0.61 | STOP `obstaculo_centro_riesgo` |
| cli_00004 | 51203 | persona | `tv` 0.76; `person` 0.37 (incierto) | STOP `obstaculo_incierto_centro` |
| cli_00005 | 74343 | perro | `tv` 0.67; `dog` 0.40 (incierto) | STOP `obstaculo_incierto_centro` |
| cli_00006 | 89359 | perro | `tv` 0.33; `traffic light` 0.30 (pared) | STOP `esperando_liberacion` |
| cli_00007 | 112953 | gato | ninguna | STOP `esperando_liberacion` |
| cli_00008 | 121281 | gato | solo `tv` 0.53 | **FORWARD 0.4 `via_libre`** |
| cli_00009 | 128375 | gato | `traffic light` 0.50 (pared) | **FORWARD 0.4 `via_libre`** |
| cli_00010 | 155000 | perro | `traffic light` 0.36 (pared) | **FORWARD 0.4 `via_libre`** |
| cli_00011 | 167531 | gato | ninguna | **FORWARD 0.4 `via_libre`** |
| cli_00012 | 832538 | perro | ninguna | **FORWARD 0.4 `via_libre`** |
| cli_00013–16 | 3452297–3541250 | perro ×3, persona (lejos, fuera de riesgo) | ninguna | FORWARD 0.4 `via_libre` |

**Resumen S2.**

- De los 13 cuadros en riesgo, el detector encontró la clase de obstáculo correcta en el centro en 4. Solo 2 llegan a 0.50 o más (obstáculo cierto); los otros 2 quedan en la banda incierta.
- En 4 cuadros solo detectó la pantalla (`tv`), y en 5 no detectó nada que la política use.
- No vio ninguno de los 4 estímulos lejanos.
- La política se detiene al inicio por la persona cierta. Después de tres cuadros con el centro «libre» (cli_00006 a cli_00008) reanuda a velocidad de crucero, **con un gato o un perro todavía al frente** en cli_00008 a cli_00012.

### S6: despejado → obstáculo → despejado (C7; 12 cuadros, D-D-D-D-B-B-B-B-D-D-D-D)

| `frame_id` | t (ms) | Escena | Estímulo | Detecciones (≥ 0.30) | Política |
|---|---:|---|---|---|---|
| cli_00017–20 | 0–2625 | despejado | — | ninguna | STOP ×2 (histéresis de inicio) y luego FORWARD 0.4 |
| cli_00021 | 41281 | obstáculo | perro, centro | solo `tv` 0.37 | **FORWARD 0.4 `via_libre`** |
| cli_00022 | 54922 | obstáculo | perro, izquierda | `person` 0.39 (clase equivocada, incierto) izquierda; `tv` 0.38 | **FORWARD 0.4 `via_libre`** |
| cli_00023 | 65375 | obstáculo | perro, derecha | `person` 0.34 (clase equivocada, incierto) derecha | **FORWARD 0.4 `via_libre`** |
| cli_00024 | 74141 | obstáculo | perro, centro | ninguna | **FORWARD 0.4 `via_libre`** |
| cli_00025–28 | 89438–93953 | despejado | — | ninguna | FORWARD 0.4 `via_libre` |

**Resumen S6.**

- Los 8 cuadros despejados salen sin detecciones; ahí no hay falsos positivos.
- En los 4 cuadros con obstáculo no aparece ningún `dog`. Dos cuadros dan `person` incierto en un lateral, y la política no reacciona a obstáculos inciertos laterales (regla 5: solo los ciertos).
- **Con el detector real, C7 no se cumple: el auto avanza a velocidad de crucero durante todo el episodio de bloqueo.**

## 6. Límites conocidos

1. **El estímulo en pantalla de celular se detecta como `tv`.** Las secuencias usan fotos 2D de personas, perros y gatos en un teléfono (método aprobado por el PM en #79).
   - YOLOX ve sobre todo el aparato: en S2, `tv` aparece en 8 de 13 cuadros en riesgo, a menudo con una confianza mayor que la del sujeto (cli_00004: `tv` 0.76 contra `person` 0.37).
   - La caja `tv` cubre casi la misma región que el sujeto. Sin embargo, `tv` no es clase de obstáculo y la política la ignora, así que el sujeto se pierde o queda incierto.
   - Este estímulo tampoco es representativo de un obstáculo real: una persona o un animal reales no vienen dentro de un marco luminoso.
2. **Sujetos pequeños o lejanos.** El sujeto en la pantalla ocupa entre 60 y 110 px de ancho a 400 × 296, y los 4 cuadros fuera de riesgo, menos de 50 px. YOLOX-Nano es la variante más pequeña de YOLOX (0.9 M parámetros, 25.8 mAP en COCO según sus autores) y es débil con objetos pequeños.
3. **Poca luz y alto contraste.** Las escenas están casi a oscuras y la pantalla es la única zona brillante, lejos de las fotos de COCO con las que se entrenó.
4. **Clase equivocada.** En S6 detectó un perro como `person` (cli_00022 y cli_00023). Para la política sigue siendo un obstáculo, pero en las métricas por clase cuenta como FP + FN.
5. **Falso positivo fijo `traffic light`.** El objeto oscuro de la pared (a la derecha, arriba de la línea de riesgo) sale como `traffic light` en 3 cuadros de S2, con confianza de hasta 0.50, y también en la evidencia de P5-04. La política lo ignora porque no es clase de obstáculo, pero contaría como FP si se evaluara esa clase.
6. **Solo clases COCO.** Conos, cajas, muros, escalones, cables o muebles no son obstáculo para este sistema aunque bloqueen la vía. Algunos sí existen en COCO (`chair`, `couch`), pero no están en `clases_obstaculo`. Un obstáculo fuera de las tres clases acordadas se trata como vía libre.
7. **Detección por cuadro, sin memoria.** El detector no usa cuadros anteriores. La estabilidad temporal depende de la histéresis de la política (3 cuadros para liberar), que no protege si los falsos negativos son consecutivos, como en S2 de cli_00006 a cli_00008.
8. **Proximidad sin metros.** El riesgo es `y2 ≥ H/2` (perspectiva), sin calibración. Un objeto alto y lejano, o uno bajo y cercano, puede quedar mal clasificado.

## 7. Qué implica y qué falta decidir (PM A y PM B)

Con el detector congelado y los estímulos actuales, el recorrido real falla en un caso de seguridad (S6/C7) y avanza con un obstáculo al frente en parte de S2 (C2). La rúbrica (2.2) da 0 a un caso cuyo comando es inseguro para la escena. Este documento no cambia nada para «arreglarlo».

Cualquier corrección debe decidirse sin usar estas 29 imágenes para elegir:

- **Cambiar de modelo o de umbral** (por ejemplo, YOLOX-S o YOLOX-Tiny) exige elegirlo con capturas de ajuste nuevas que tengan obstáculos (`datos/ajuste/` hoy solo tiene 7 cuadros S1 despejados), congelar otra vez y declararlo.
- **Agregar `tv` a las clases de obstáculo** haría pasar los casos actuales, pero se decidiría viendo el resultado de evaluación, y `tv` no es un obstáculo del dominio. No se recomienda.
- **Cambiar el estímulo** (fotos impresas, figuras o mascotas reales en lugar del teléfono) obliga a recapturar y vuelve a pasar por #57 y #58.
- **Mantener todo y declararlo** cuesta en 1.4 (F1), C2 y C7, pero el informe y las cifras quedan coherentes (5.3).

## 8. Reproducir cuadros no prueba movimiento ni frenado

*(Borrador para acordar con el grupo B, rúbrica 4.3.)*

El recorrido integral reproduce cuadros guardados con el auto inmóvil (motores apagados en todas las capturas, ver [`ficha_auto.md`](ficha_auto.md)). Envía los comandos a un adaptador virtual que solo los registra. Por eso, lo que se demuestra es la cadena **cuadro → detección → decisión → comando**, con sus tiempos de cómputo, y nada más.

Un STOP registrado no prueba que el auto frene, ni en cuánto tiempo o distancia. Eso depende del controlador, de los motores, de la inercia, del piso y de la batería, y nada de eso se midió aquí. Tampoco prueba que el detector funcione con el auto en movimiento, donde hay desenfoque, vibración, cambios de luz y cuadros que se pierden.

Además, los cuadros del recorrido no salieron de una cámara que avanza hacia el obstáculo: el estímulo se colocó frente a la cámara quieta. Por eso no se puede deducir la distancia de frenado a partir de la secuencia. La latencia medida en el benchmark es solo de cómputo; el tiempo físico de reacción también incluye la transmisión, el actuador y la mecánica.
