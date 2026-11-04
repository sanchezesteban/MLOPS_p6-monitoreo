# Contrato v1: percepción (A → B) y comando (B → adaptador)

Único acoplamiento entre el grupo A (Percepción y datos) y el grupo B (Control y verificación). Cualquier cambio sube `schema_version` y requiere aprobación de los dos PM.

| Archivo | Qué es |
|---|---|
| `config/schemas/evento_percepcion.schema.json` | JSON Schema del evento de percepción (un mensaje por cuadro) |
| `config/schemas/comando.schema.json` | JSON Schema del comando que recibe el adaptador (uno por decisión o evento) |
| `config/schemas/run_header.schema.json` | JSON Schema de la cabecera de ejecución (una por corrida) |
| `config/ejemplos/*.json` | Ejemplos válidos: `ok`, `vacio`, `error`, `stale`, `comando_forward`, `comando_stop`, `run_header` |
| `src/p5/contrato.py` | Dataclasses, validador (schema + reglas de abajo) y zonas |
| `tests/test_contrato.py` | Valida los ejemplos y rechaza mensajes inválidos |

El JSON Schema revisa la forma: campos, tipos, rangos y que no haya campos desconocidos. Las reglas entre campos (orden de la caja, coherencia `status`/`error_msg`, `STOP` ⇒ velocidad cero, números finitos) las revisa `p5.contrato`. Un mensaje es válido solo si pasa las dos capas.

## Reloj y unidades

- Todos los `t_*_ms` (`t_capture_ms`, `t_decision_ms`, `t_command_ms`, `valid_until_ms`) son milisegundos en el **reloj de la ejecución**: un solo origen por `run_id`, monotónico y controlable. Las pruebas lo avanzan a mano para disparar watchdog y vencimientos sin esperar al reloj físico.
- El manifiesto guarda el tiempo real de captura; el reproductor de `p5.recorrer` arma el reloj de la ejecución: dentro de cada secuencia avanza `replay_dt_ms` (100 ms por defecto) por cuadro y entre secuencias suma un hueco mayor que los plazos del watchdog. El tiempo real queda como procedencia en `t_capture_origen_ms`.
- `t_capture_ms` es estrictamente creciente dentro del `run_id`.
- `frame_id` es único dentro de un `run_id` y empieza con `{sequence_id}_` (p. ej. `seq01_f0007`).
- Hashes: SHA-256 en hex minúsculas (64 caracteres) calculado sobre los bytes del archivo.
- Caja `bbox`: formato `xyxy` = `[x1, y1, x2, y2]` en píxeles del **cuadro original** (no del tensor redimensionado), origen arriba a la izquierda, `x` hacia la derecha, `y` hacia abajo. `0 ≤ x1 < x2 ≤ image_width`, `0 ≤ y1 < y2 ≤ image_height`.

## Cabecera de ejecución (una por corrida)

| Campo | Tipo | Regla |
|---|---|---|
| `schema_version` | string | `"1.0"` |
| `run_id` | string | Identifica la corrida; lo repiten todos los eventos y comandos |
| `commit` | string | Commit o versión de la entrega |
| `model_sha256` | hex64 | Hash de los pesos cargados |
| `config_sha256` | hex64 | Hash del archivo de configuración usado |
| `data_manifest_sha256` | hex64 | Hash del manifiesto de cuadros |
| `runtime` | string | p. ej. `onnxruntime 1.19.2 CPU` |
| `hardware` | string | CPU y SO |
| `virtual_mode` | bool | `true` = adaptador virtual, motores desconectados |
| `t_start_utc` | string | Fecha ISO 8601 de inicio (solo informativa; no se usa para decidir) |
| `replay_dt_ms` | número > 0 o ausente | Intervalo de reproducción por cuadro dentro de cada secuencia; ausente si la corrida no reproduce un manifiesto |

## Evento de percepción (A → B, uno por cuadro)

| Campo | Tipo | Regla |
|---|---|---|
| `schema_version` | string | `"1.0"` |
| `run_id` | string | Igual al de la cabecera |
| `sequence_id` | string | |
| `frame_id` | string | Único en la corrida; empieza con `{sequence_id}_` |
| `t_capture_ms` | número ≥ 0 | Reloj de la ejecución (mismo origen que los tiempos del comando), estrictamente creciente en el `run_id` |
| `t_capture_origen_ms` | número ≥ 0 o `null` | Opcional: tiempo de captura original del manifiesto (procedencia); `null` si no aplica |
| `image_path` | string o `null` | Ruta del cuadro relativa a la carpeta de datos (`--datos`), separador `/`; `null` solo si `status=error` y no hubo archivo |
| `image_sha256` | hex64 o `null` | Hash de los bytes del cuadro; `null` solo con `status=error` |
| `image_width`, `image_height` | entero ≥ 1 o `null` | `null` solo con `status=error` (imagen ilegible) |
| `model_sha256` | hex64 | Pesos que produjeron las detecciones |
| `config_sha256` | hex64 | Configuración efectiva (umbral de confianza, NMS) |
| `status` | `ok` / `stale` / `error` | A emite solo `ok` o `error`; `stale` lo asigna B al recibir (regla 3) |
| `error_msg` | string o `null` | Obligatorio con `error` y `stale`; `null` con `ok` |
| `synthetic` | bool | `true` si las detecciones no vienen del detector real (pruebas de política) |
| `detections` | lista | Vacía si no hay objetos; siempre presente |
| `detections[].class_name` | string | |
| `detections[].class_id` | entero ≥ 0 | |
| `detections[].confidence` | número finito en [0, 1] | |
| `detections[].bbox` | 4 números finitos | `xyxy` en píxeles del cuadro original |

## Comando (B → adaptador, uno por decisión o evento)

| Campo | Tipo | Regla |
|---|---|---|
| `schema_version` | string | `"1.0"` |
| `run_id` | string | |
| `frame_id` | string o `null` | Cuadro que disparó la decisión; `null` en eventos de reloj o de sistema |
| `event` | string o `null` | `watchdog`, `stale_frame`, `detector_error`, `emergency`, `rearm`, `shutdown`, …; `null` si la decisión es por un cuadro normal |
| `detections_ref` | string o `null` | `frame_id` del evento de percepción cuyas detecciones alimentaron la decisión; `null` si no se usó ninguna (watchdog, emergencia, cuadro vencido o con error); si `frame_id` y `detections_ref` son no nulos, deben ser iguales |
| `state_before`, `state_after` | string | Estados de la política (los define el grupo B en su configuración) |
| `action` | `FORWARD` / `STEER_LEFT` / `STEER_RIGHT` / `STOP` | |
| `reason` | string no vacío | Motivo legible (p. ej. `obstaculo_centro_riesgo`) |
| `speed` | número en [0, 1] | Fracción de la velocidad máxima configurada |
| `steering` | número en [-1, 1] | Negativo = izquierda, positivo = derecha, 0 = recto |
| `t_decision_ms` | número ≥ 0 | Instante en que la política decidió |
| `t_command_ms` | número ≥ `t_decision_ms` | Instante en que el adaptador recibió el comando |
| `valid_until_ms` | número o `null` | Vencimiento del comando; obligatorio y `> t_command_ms` en acciones de movimiento; debe ser `null` en `STOP` |
| `received` | bool | `true` si el adaptador lo aceptó y registró |
| `error` | string o `null` | Error asociado (detector, configuración, rechazo del adaptador) |
| `synthetic` | bool | `true` si viene de detecciones sintéticas |

Al menos uno de `frame_id` o `event` es no nulo.

## Zonas (proxy geométrico, no distancia en metros)

Sobre el ancho `W` del cuadro original:

- izquierda `[0, W/3)`, centro `[W/3, 2W/3]`, derecha `(2W/3, W]`.
- Una caja **ocupa toda zona que toca** su intervalo horizontal `[x1, x2]`: izquierda si `x1 < W/3`; centro si `x1 ≤ 2W/3` y `x2 ≥ W/3`; derecha si `x2 > 2W/3`. Una caja que cruza izquierda y centro bloquea el centro (criterio conservador).
- Zona de riesgo: `y2 ≥ 0.5·H` (el borde inferior de la caja llega a la mitad baja del cuadro). Es un proxy de cercanía por perspectiva; no es una distancia calibrada.

`p5.contrato.zonas_ocupadas(bbox, W)` y `p5.contrato.en_riesgo(bbox, H)` implementan estas reglas para que A y B calculen lo mismo.

## Reglas

1. `status=ok` con `detections=[]` es un **cuadro válido sin objetos**: puede autorizar avance si la política lo permite.
2. `status=error` (excepción, timeout, salida malformada o no finita, imagen ilegible), `status=stale` y la **ausencia de cuadros** (corte de entrada detectado por el watchdog) **nunca** equivalen a vía libre. A emite solo `ok` o `error`; `stale` lo asigna B al recibir (regla 3). Con `error` o `stale`, `detections` va vacía.
3. Vencimiento: un cuadro está vencido si `t_now_ms − t_capture_ms > max_frame_age_ms`, o si `t_now_ms < t_capture_ms` (reloj inconsistente ⇒ `STOP`). El grupo B lo comprueba al recibir y lo marca `stale`; un cuadro vencido se rechaza y no reanuda movimiento. `max_frame_age_ms` y el plazo del watchdog viven en la configuración de la política (grupo B).
4. `STOP` ⇒ `speed = 0`, `steering = 0` y `valid_until_ms = null`; cancela el comando previo de inmediato, aunque este no haya vencido.
5. Movimiento (`FORWARD`, `STEER_LEFT`, `STEER_RIGHT`) ⇒ `speed > 0` y `valid_until_ms` definido. `FORWARD` va con `steering = 0`, `STEER_LEFT` con `steering < 0` y `STEER_RIGHT` con `steering > 0`. Al llegar `valid_until_ms` sin un comando nuevo, el adaptador se detiene sin esperar otro cuadro.
6. Las etiquetas reales y las acciones esperadas nunca forman parte de estos mensajes: la política decide solo con el evento de percepción y su propio estado.
