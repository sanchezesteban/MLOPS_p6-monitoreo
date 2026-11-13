# Umbrales, zonas, referencia, ventanas y reglas

Configuración: [`config/monitoreo.yaml`](../config/monitoreo.yaml), con `config_id` `p6-config-v1` y SHA-256 `62a273b9…07da4c`. Se guarda en cada evento, ventana y alerta, y su texto está en la tabla `configs`. El portal la muestra en `/config/<sha>`.

## Política de zonas (R3.2)

- **Unidad: frame.** `s` = la mayor confianza entre las candidatas del frame.
- `s ≥ 0.50` → **aceptada** por la política. No afirma que la predicción sea correcta.
- `0.25 ≤ s < 0.50` → **duda**.
- `s < 0.25` → **baja**.
- En las igualdades, 0.25 pertenece a duda y 0.50 a aceptada (lo cubre `tests/test_politica_metricas.py`).
- `sin_detecciones` y `error` son **estados aparte**, sin score ni zona. Nunca se les asigna confianza 0.
- **Detección:**
  - El piso de salida del detector bajó de 0.30 (P5) a **0.05**, con NMS por clase de IoU 0.45, letterbox 416 y máximo 100 detecciones ([`config/detector.yaml`](../config/detector.yaml)). Así, todas las candidatas ≥ 0.05 llegan a la política y las zonas de duda y baja son observables.
  - Cada candidata guarda su score, su caja y su propia zona en `detecciones[]`.
  - Las proporciones usan **frames puntuados** como denominador, nunca candidatas, y los dos denominadores no se mezclan.
- **Muestreo:** los frames consecutivos de una secuencia son parecidos, así que no se presentan como observaciones independientes. Por eso las reglas actúan sobre ventanas y exigen persistencia.

## Referencia y justificación de los umbrales (R3.1, R3.3)

- **Corrida de referencia:** `ref-carrito`, con 42 frames reales de la ESP32-CAM del carrito (secuencias S2, S3 y S5 del P5) a 5 fps, el modelo `c789161e…` y la configuración del detector `dc30841a…`. El archivo resultante es [`evidencias/referencia/referencia.json`](../evidencias/referencia/referencia.json), con SHA-256 `5d512afc…`.
- **Conjuntos disjuntos:** la referencia **no comparte frames** con C1 (S1, S4, S6) ni usa imágenes degradadas.
- **Observaciones:** 41 frames puntuados y 1 sin detecciones. Cuantiles de `s`: p10 = 0.212, p15 = 0.272, p25 = 0.412, p50 = 0.606, p75 = 0.852, p90 = 0.874.
- **Umbral inferior 0.25:** deja en zona baja 6 de 41 frames de referencia (14.6 %), es decir, la cola inferior entre p10 y p15. Así, en condiciones normales un frame «bajo» es poco frecuente y merece revisión.
- **Umbral superior 0.50:** deja 24 de 41 frames aceptados (58.5 %) y 11 en duda (26.8 %). Un umbral más alto, como 0.80 (ejemplo de la guía), mandaría a duda más de la mitad de la operación normal, porque YOLOX-Nano sobre capturas de 400×296 da puntuaciones moderadas.
- **Proporción de baja de referencia:** `p_ref = 6/41 = 0.146`. La referencia guarda su identidad: modelo, configuración del detector y umbral inferior. `reglas.referencia_compatible` **solo compara** si los tres coinciden; si no, la regla queda «no evaluable». Si cambia el modelo o el preprocesamiento, hay que generar una referencia nueva y una serie separada.
- **Orden de los pasos:** los umbrales y las reglas se fijaron con la referencia **antes** de las corridas oficiales C1 y C2. Antes hubo corridas exploratorias, fuera de la evidencia, para probar el pipeline y elegir la degradación de C2. En ellas también se descartó una ventana de 6 frames por ser demasiado ruidosa.

## Ventanas y mínimo de observaciones

- **Ventana:** 10 frames consecutivos (2 s de stream).
- **Ventana suficiente:** tiene al menos **6 frames puntuados**.
- **Ventana insuficiente:** no abre ni cierra alertas de confianza (decisión `None`, «no evaluable») y se muestra como INSUFICIENTE en `/ventanas`. **Evidencia insuficiente ≠ normalidad.**
- En la referencia, las ventanas suficientes tienen como máximo una proporción baja de 0.30 (3/10).

## Reglas de alerta (R5.1)

| Regla | Condición | Ventana / persistencia | Datos insuficientes | Severidad |
|---|---|---|---|---|
| `baja-confianza-v1` | proporción de frames bajos ≥ 0.5 | 1 ventana suficiente. La alerta sigue activa mientras se cumpla y se resuelve en la primera ventana suficiente que no cumpla. | No evaluable: ni abre ni resuelve | warning |
| `cambio-sostenido-v1` | proporción − `p_ref` ≥ 0.25 (es decir, ≥ 0.396) | 3 ventanas suficientes **seguidas** (≥ 6 s). Una ventana suficiente que no excede reinicia la racha. | Las ventanas insuficientes no suman ni reinician la racha. Sin referencia compatible, no es evaluable. | critical |
| `evidencia-insuficiente-v1` | 3 ventanas insuficientes seguidas | 3 ventanas | Es la regla que cubre este caso | info |

Cada alerta guarda:
- regla, severidad, momento de apertura, actualización y resolución;
- motivo con cifras y acción sugerida;
- `config_sha256` y las ventanas que la sustentan;
- los `event_id` que la originaron: los frames en zona baja para las reglas de confianza, y todos los frames de las ventanas para la de evidencia insuficiente;
- una captura de evidencia.

La confianza **no** confirma drift ni pérdida de calidad: la alerta sirve para iniciar una investigación.
