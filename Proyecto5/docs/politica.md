# Política temporal (P5-10)

Convierte cada evento de percepción del contrato v1 (`config/contrato_v1.md`) en una decisión: estado anterior y nuevo, acción, razón, velocidad y dirección.

| Archivo | Qué es |
|---|---|
| `config/politica.yaml` | Clases de obstáculo, umbrales de confianza, zonas, histéresis y comandos |
| `src/p5/politica.py` | `cargar_config`, `Politica.decidir(evento)` y `Politica.detener(event, razon)` |
| `tests/test_politica.py` | Una prueba por regla, configuraciones inválidas y escenarios C1–C7 con detecciones sintéticas (`synthetic=true`) |

La política es un módulo puro. Decide **solo** con el evento de percepción y su propio estado, y no importa etiquetas, expectativas, relojes ni hardware (lo comprueba `test_la_politica_no_importa_etiquetas_ni_hardware`). Los tiempos del comando (`t_decision_ms`, `t_command_ms`, `valid_until_ms`), el watchdog, la marca de cuadro vencido (`stale`) y la emergencia los agrega quien arma el comando para el adaptador (P5-11 y P5-12).

## Configuración

`cargar_config` rechaza la configuración **antes de crear la política**, así que con una configuración inválida no se emite ningún movimiento. Se rechazan:

- claves desconocidas o faltantes, YAML ilegible y `version` distinta de 1;
- números no finitos, booleanos o texto donde va un número;
- `umbral` fuera de (0, 1] y `minimo_incierto` fuera de [0, `umbral`];
- zonas solapadas o fuera del cuadro (se exige `0 < limite_izquierda < limite_derecha < 1`) y `riesgo_y` fuera de (0, 1];
- `cuadros_liberar` que no sea un entero ≥ 1;
- velocidades fuera de (0, 1], `velocidad_precaucion` mayor que `velocidad_crucero` y `giro_correccion` fuera de (0, 1].

| Parámetro | Valor | Justificación |
|---|---:|---|
| `clases_obstaculo` | person, dog, cat | Clases acordadas por los PM; el detector de P5-03 (#55) debe entregarlas con estos nombres COCO. Otro objeto no se trata como obstáculo (límite conocido) |
| `confianza.umbral` | 0.50 | Desde aquí la detección es un obstáculo cierto y puede detener al auto |
| `confianza.minimo_incierto` | 0.30 | Entre 0.30 y 0.50 la detección es incierta: reduce la velocidad, pero no detiene ni libera. Debajo de 0.30 se ignora |
| `zonas.limite_izquierda` / `limite_derecha` | 1/3 y 2/3 del ancho | Los mismos tercios del contrato v1 |
| `zonas.riesgo_y` | 0.5 | La caja está en riesgo si su borde inferior llega a la mitad baja del cuadro (proxy de cercanía por perspectiva, **no es una distancia en metros**) |
| `histeresis.cuadros_liberar` | 3 | Para reanudar se piden 3 cuadros válidos seguidos con el centro libre. Así un solo cuadro despejado (por ejemplo, un falso negativo) no hace alternar parada y avance |
| `comandos.velocidad_crucero` | 0.4 | Fracción de la velocidad máxima. **Tentativa** hasta el mapeo del adaptador (P5-11) |
| `comandos.velocidad_precaucion` | 0.2 | Mitad del crucero para obstáculos inciertos, lejanos o laterales |
| `comandos.giro_correccion` | 0.5 | Fracción del giro máximo para alejarse de un obstáculo lateral |

## Clasificación de detecciones

Para cada detección del cuadro (se consideran **todas**, no solo la de mayor confianza):

1. Si la clase no está en `clases_obstaculo` o la confianza es menor que `minimo_incierto`, se ignora.
2. Certeza: `cierto` si confianza ≥ `umbral`; `incierto` en otro caso.
3. Zonas: toda zona que toca el intervalo `[x1, x2]` de la caja. Una caja que cruza un lateral y el centro también bloquea el centro (criterio conservador del contrato).
4. Riesgo: `y2 ≥ riesgo_y · H`.

## Reglas, en orden de prioridad

| # | Condición | Acción | Estado nuevo | `reason` |
|---|---|---|---|---|
| 1 | `status=error` | STOP | FALLA | `error_percepcion` |
| 1 | `status=stale` | STOP | FALLA | `cuadro_vencido` |
| 2 | Obstáculo cierto que toca el centro, en riesgo | STOP | BLOQUEADO | `obstaculo_centro_riesgo` |
| 3 | Estado INICIO, BLOQUEADO o FALLA y aún no hay `cuadros_liberar` cuadros seguidos con el centro libre de obstáculos ciertos **e inciertos** en riesgo | STOP | se mantiene | `esperando_liberacion` u `obstaculo_incierto_centro` |
| 4 | Obstáculo incierto en el centro, en riesgo | FORWARD lento | PRECAUCION | `obstaculo_incierto_centro` |
| 5 | Obstáculo cierto solo a la izquierda, en riesgo, y derecha libre | STEER_RIGHT lento | CORRECCION | `obstaculo_izquierda` |
| 5 | Obstáculo cierto solo a la derecha, en riesgo, y izquierda libre | STEER_LEFT lento | CORRECCION | `obstaculo_derecha` |
| 5 | Obstáculos laterales en riesgo, o la zona de destino no está libre | FORWARD lento | PRECAUCION | `obstaculos_laterales_centro_libre` |
| 5 | Solo obstáculos **inciertos** en un lateral, en riesgo (ninguno cierto en un lateral) | FORWARD lento, sin girar | PRECAUCION | `obstaculo_incierto_lateral` |
| 6 | Obstáculo cierto en el centro, lejos (fuera de riesgo) | FORWARD lento | PRECAUCION | `obstaculo_centro_lejos` |
| 7 | Nada relevante | FORWARD crucero | AVANCE | `via_libre` |

Una zona de destino está libre si no hay ningún obstáculo en riesgo en ella, ni cierto ni incierto. La política nunca gira hacia la zona ocupada, y solo corrige (gira) por un obstáculo **cierto**: uno incierto, en el centro o en un lateral, solo baja la velocidad. Ante un obstáculo central no busca una ruta alternativa: se detiene, lo cual es válido según la rúbrica.

`Politica.detener(event, razon)` sirve para los eventos sin cuadro (watchdog, error del detector, cierre). Emite STOP y pasa a FALLA, de modo que reanudar exige otra vez `cuadros_liberar` cuadros válidos.

## Estados y transiciones

| Estado | Significado | Sale a |
|---|---|---|
| INICIO | Arranque, detenido | BLOQUEADO, FALLA; AVANCE, CORRECCION o PRECAUCION tras `cuadros_liberar` cuadros con el centro libre |
| AVANCE | Vía libre, velocidad de crucero | cualquiera |
| CORRECCION | Obstáculo lateral, gira hacia el lado libre | cualquiera |
| PRECAUCION | Obstáculo incierto (centro o lateral), lejano o laterales en ambos lados; avanza lento | cualquiera |
| BLOQUEADO | Obstáculo cierto en el centro en riesgo | FALLA; movimiento tras `cuadros_liberar` cuadros con el centro libre |
| FALLA | Cuadro con error o vencido, o evento sin cuadro (`detener`) | BLOQUEADO; movimiento tras `cuadros_liberar` cuadros con el centro libre |

Bloquear es inmediato (un solo cuadro con obstáculo cierto) y liberar pide `cuadros_liberar` cuadros. La histéresis es asimétrica a favor de la seguridad.

## Límites conocidos

- Solo `person`, `dog` y `cat` cuentan como obstáculo. Cualquier otro objeto (caja, silla, pared, juguete) no se trata como obstáculo y la política puede avanzar hacia él.
- Si un obstáculo físico de esas clases no sale como `person`, `dog` o `cat` en el detector (por ejemplo, un peluche que el detector clasifica como `teddy bear`), tampoco se trata como obstáculo. Los obstáculos de las secuencias deben comprobarse antes con el detector.
- La cercanía es un proxy por la posición de la caja en el cuadro, no una distancia calibrada. Un comando registrado en el adaptador virtual no prueba que el auto frene físicamente.

## Cambios

- Cambio del 4 nov: regla `obstaculo_incierto_lateral` por revisión de código (hallazgo de Juan Pablo); no cambia umbrales ni configuración; previo a la corrida final.

## Pendiente de acordar

- Velocidades y giro definitivos, según el adaptador y la ficha del auto (P5-11, #63; P5-05, #57).
- Dónde viven `max_frame_age_ms`, el plazo del watchdog y la duración de un comando (`valid_until_ms`), y quién marca `stale` (P5-12, #64). La política ya responde STOP a `status=stale`.
