# Runner de casos C01–C10 (P5-13)

Ejecuta los diez casos con un solo comando y sale con código 1 si una expectativa no se
cumple. El runner usa **la misma política y el mismo adaptador** que la aplicación; las
expectativas se leen aparte y nunca se pasan a la política ni al detector.

> **Estado:** C01–C10 corren contra la política de #73, el adaptador de #74, el watchdog
> de #76 y los eventos reales de P5-14 (`datos/eventos/S1.jsonl` … `S6.jsonl`, modo
> `cortes_sesion`). La corrida del 4 nov 2026 da **7/10**: C01, C04, C05, C06 y C08–C10
> pasan; C02, C03 y C07 fallan por recall del detector congelado (S2 pierde la persona en
> tres cuadros; S3 tiene dos cuadros de borde centro; S6 no detecta el obstáculo). Está
> documentado en [`evidencia/casos/`](evidencia/casos/README.md) y en `docs/detector.md`
> §5. No se ajustan las expectativas para ocultar esos fallos.

## Uso

```bash
cd Proyecto5
PYTHONPATH=src python -m p5.casos \
    --casos casos \
    --config config/politica.yaml \
    --salida resultados/casos
```

Para correr un solo caso mientras se desarrolla:

```bash
PYTHONPATH=src python -m p5.casos \
    --casos casos \
    --config config/politica.yaml \
    --salida resultados/casos \
    --caso C08
```

Salidas:

```
resultados/casos/
├── resumen.json          # total, pass/fail/error y rutas a los comandos observados
├── C08/
│   ├── comandos.jsonl    # un paso por línea: cuadro o evento de control
│   └── resultado.json    # expectativa, resultado y fallos concretos
...
```

El proceso sale con código 0 solo si **todos** los casos seleccionados pasan. Si falta un
insumo, un evento no cumple el contrato o una expectativa no se cumple, sale con 1.

## Casos reales y sintéticos

### `tipo: real`

El runner **no corre el detector**. Reproduce un `eventos.jsonl` ya producido por el
detector de P5-04 (#56) o por el recorrido integral de P5-14 (#66). Cada línea es un
`PerceptionEvent` completo del contrato v1.

```yaml
id: C01
nombre: Via libre
tipo: real
estado_inicial: INICIO
entrada:
  secuencia: seq01
  manifiesto: datos/manifiesto.csv
  eventos: datos/eventos/seq01.jsonl   # opcional; por defecto datos/eventos/<seq>.jsonl
expectativa: expectativas/C01.yaml
```

Si el archivo de eventos no existe, el caso falla con `insumo_faltante`; no se salta. El
runner valida que la secuencia tenga un solo `run_id`, `frame_id` único con prefijo de la
secuencia y `t_capture_ms` creciente (`validar_secuencia`). Después compara cada cuadro
con `casos/expectativas/cuadros.csv`, generado por P5-15 con las anotaciones de P5-06:

```bash
PYTHONPATH=src python -m p5.expectativas \
    --coco datos/anotaciones.json \
    --manifiesto datos/manifiesto.csv \
    --config config/politica.yaml \
    --salida casos/expectativas/cuadros.csv
```

En `main` los eventos reales son `datos/eventos/S1.jsonl` … `S6.jsonl` (P5-14, modo
`cortes_sesion`). P5-15 escribe un `cuadros_<secuencia>.csv` por secuencia y el runner
compara todas sus filas; usa los mismos `frame_id` canónicos (`S2_f0007`…, con los huecos
de S3/S4) que los eventos.

### `tipo: sintetico`

Los eventos vienen en el YAML y no necesitan datos ni detector. El runner construye el
`PerceptionEvent` con `synthetic: true` y lo valida contra el contrato.

```yaml
entrada:
  sequence_id: c08
  run_id: run-c08
  image_width: 640
  image_height: 480
  eventos:
    - {tipo: cuadro, frame_id: c08_f0001, t_capture_ms: 0, detections: []}
    - {tipo: watchdog, id: watchdog_1, t_ms: 600, razon: sin_cuadros}
```

Tipos de evento:

| `tipo` | Campos | Qué hace el runner |
|---|---|---|
| `cuadro` | `frame_id`, `t_capture_ms`, `detections`, `status`, `error_msg` | Avanza el reloj y llama a la política |
| `watchdog` | `id`, `t_ms`, `razon` | Avanza el reloj y pide el STOP del watchdog |
| `emergencia` | `id`, `t_ms`, `razon` | Activa la emergencia enclavada y pide STOP |
| `rearme` | `id`, `t_ms`, `valido` | Libera la emergencia solo si `valido: true` |
| `cierre` | `id`, `t_ms` | Cierra el adaptador; debe quedar un STOP `shutdown` |

## Expectativas

La expectativa vive en `casos/expectativas/<caso>.yaml` y se lee **después** de ejecutar
el caso. Puede tener:

- `acciones_por_cuadro`: CSV de P5-15 para casos reales.
- `cuadros`: lista de `{frame_id, acciones_permitidas, velocidad_max}` para casos
  sintéticos cuadro por cuadro (C06).
- `pasos`: lista de `{id, acciones_permitidas, velocidad_max, permitir_error}` para casos
  con eventos de control (C08–C10).
- `estados_requeridos`: estados de vía que la secuencia debe contener.
- `plazo_reaccion_cuadros`: máximo de cuadros para reaccionar a un bloqueo. Es el plazo
  que el runner aplica hoy en los casos reales.
- `plazo_reaccion_ms`: se conserva en las expectativas de P5-15; el plazo en milisegundos
  del watchdog se valida con #64 (`stop_por_watchdog`).
- `requisitos`: reglas adicionales.

Requisitos implementados:

| Requisito | Qué comprueba |
|---|---|
| `movimiento_minimo` | Al menos N comandos de movimiento; evita aprobar deteniéndose siempre |
| `sin_movimiento_entre_obstaculos` | No hay movimiento entre el primer y el último cuadro bloqueado |
| `reanuda_tras_despeje` | Hay movimiento dentro de N cuadros despejados tras el bloqueo |
| `stop_por_watchdog` | El evento de watchdog produce STOP dentro del plazo |
| `sin_movimiento_despues_de` | Después de un evento no hay comandos de movimiento |
| `cuadro_vencido_rechazado` | El cuadro vencido termina en STOP con razón de vencimiento |
| `stop_por_error` | Los eventos de error del detector producen STOP |
| `evento_invalido_rechazado` | Un evento fuera de contrato queda registrado con STOP seguro |
| `rearme_requerido` | No hay movimiento con la emergencia enclavada y se reanuda tras el rearme |
| `stop_al_cerrar` | El último comando del cierre es STOP `shutdown`/`cierre` |

## Reloj simulado

No se usa `time.sleep`: el runner avanza un reloj compartido con `t_capture_ms`/`t_ms` y
el adaptador pone `t_command_ms` con ese mismo reloj. Así C08 puede probar el corte de
cuadros y el vencimiento de forma determinista.

## Prueba de fallo inducido

El issue pide demostrar que el runner falla cuando una expectativa no se cumple. Se hace
sobre una copia, sin tocar el archivo congelado:

```bash
cp -R casos /tmp/casos_fallo
# cambiar, por ejemplo, la acción permitida de c08_f0004 a FORWARD
PYTHONPATH=src python -m p5.casos \
    --casos /tmp/casos_fallo \
    --config config/politica.yaml \
    --salida /tmp/resultados_fallo \
    --caso C08
echo $?   # 1
```

La salida esperada es un `resultado: fail` con el fallo concreto del cuadro o del
requisito. Después se restaura la copia y se vuelve a correr para comprobar el código 0.

## Pruebas

```bash
cd Proyecto5
pytest
ruff check .
ruff format --check .
```

Las pruebas del runner usan un ejecutor guionizado para validar la comparación, el código
de salida y los requisitos sin depender de P5-10/P5-11. La integración con el ejecutor real
se prueba cuando #73, #74 y #64 estén mergeados.

## Evidencia de la primera corrida

[`docs/evidencia/casos/`](evidencia/casos/README.md) guarda la corrida de C08–C10 contra
la política, el adaptador y el watchdog ya mergeados en `main`, más la salida del fallo
inducido sobre una copia de la expectativa de C08.

## Pendientes para cerrar P5-13

1. La fase 2 de P5-06 (#87) ya está en `main`: `datos/anotaciones.json` y
   `datos/manifiesto.csv` cubren las 78 imágenes. El runner usa los `cuadros_S*.csv`
   congelados de P5-15.
2. C02, C03 y C07 se documentan como límite del detector; no se ajustan las expectativas.
3. Si el PM decide mejorar el detector o cambiar el estímulo, repetir C01–C10 y actualizar
   `docs/evidencia/casos/`.
