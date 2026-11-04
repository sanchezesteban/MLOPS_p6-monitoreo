# Procedencia temporal y selección vigente de S1

S1 conserva **12 fotografías despejadas de dos sesiones originales**. La corrección fue [autorizada expresamente por Sebastián](https://github.com/sebastian0023/Proyecto-3-Clasificador-de-imagenes/pull/79#issuecomment-6610598090): retirar seis por escena compartida con ajuste y dos por posible persona; recuperar las dos originales de 59719 y 66562 ms, aceptadas por el PM como C1 aunque muestran principalmente pared. No se requieren nuevas capturas para este PR.

**El archivo capturas.csv es la fuente de verdad para t_capture_ms, no los números incluidos en el nombre del JPEG.** Se conservan los nombres históricos. Tres S1 vigentes llevan tiempo original en el nombre y tiempo normalizado distinto en el CSV: los de e0762564…, 8e76f0bf… y d870be1f…. Por ejemplo, S1_0000032187_8e76f0bf9ada44dca0ac9ef5a47dfb82.jpg tiene t_capture_ms=3813428. No se renombra ni se alteran tiempos para hacerlos coincidir.

## Normalización previa conservada

```text
O = 1793493718610840900 ns
O_complemento = 1793497499851940400 ns
A_estimado_ns = origen_original_ns + t_original_ms * 1000000
(t_normalizado_ms, residuo_ns) = divmod(A_estimado_ns - O, 1000000)
```

Desfase del complemento: 3781241 ms y residuo 99500 ns. Se verifica exactamente O + t_normalizado_ms*1000000 + residuo_ns = A_estimado_ns. No certifica reloj entre ejecuciones ni exposición del sensor. **En esta corrección no se recalculó ningún timestamp**: los diez registros conservados mantienen todos sus campos y las dos incorporaciones mantienen los campos de su CSV original.

| session_id original vigente | Cuadros |
|---|---:|
| 80a436749c3047ae9074fabba4ab220e | 9 |
| e2b4a168ded24ec38bc6db62dd7dfead | 3 |

La pausa registrada entre ambas sesiones sigue siendo aproximadamente 3623351 ms; no se comprime ni se simula continuidad. La aceptación por el PM es de la selección autorizada, no una medición automática de continuidad ni una caracterización estadística de escenas.

## Ocho exclusiones autorizadas

| Motivo | frame_id original | t_original_ms | t_capture_ms en CSV anterior |
|---|---|---:|---:|
| Posible persona | 714dd76f5ea14d8b946631e2f93df6f1 | 74375 | 3855616 |
| Posible persona | 39364f4da4954767895eab0aa90268e9 | 89109 | 3870350 |
| Escena compartida con ajuste | 4e9c766f2e784d69a16286e0ba45a338 | 1540635 | 5321876 |
| Escena compartida con ajuste | 46e5f55e3d644cc4ad8ec3cc22b69c2b | 1546260 | 5327501 |
| Escena compartida con ajuste | dbdf4b8d33a34ef18a360ffe00ea9805 | 1556526 | 5337767 |
| Escena compartida con ajuste | 30d9d82a8208484da8719f3e204ebecc | 1562994 | 5344235 |
| Escena compartida con ajuste | 66041d650c4f47a99c8a7399f9ae6343 | 1599600 | 5380841 |
| Escena compartida con ajuste | c64f1d420ea24817881a6c5d3031d0a2 | 1605319 | 5386560 |

Las dos posibles personas pertenecen a e2b4a168ded24ec38bc6db62dd7dfead. Las seis de escena compartida pertenecen a eb5c3d737acc4ccf8b450f37e4f6751e (4) y 9fa340d096094511b5ec82711d3f922b (2): mismo palo, mueble café y puerta del ajuste, según revisión visual del PM. Se excluyen sin asignarles nuevas etiquetas ni outside_risk.

## Dos recuperaciones verificadas

| frame_id | t_original_ms = t_capture_ms vigente | SHA-256 |
|---|---:|---|
| cb3a6daa6529446b80399e34ae6aae9c | 59719 | ec422ab550c9816b3891c89e25a9ea184d005b4623ef9140192b42d930ca2dd8 |
| a364a69c557a49eaac35d3d4148acd24 | 66562 | 488a4d9556a20fd6e3b308f15f31b42ea0c3772e9a9cf9402abb45c84a4d8969 |

Ambas conservan session_id=80a436749c3047ae9074fabba4ab220e, origen 1793493718610840900 ns, etiqueta despejado y outside_risk=0. Se recuperaron byte a byte de Proyecto5/datos.zip, entradas datos/prueba_manual/S1 con sus nombres originales; coinciden con los JPEG y el CSV de prueba_manual. Sus tiempos encajan entre 50062 y 103562 ms, sin normalización adicional. La aceptación expresa de C1 está enlazada al comienzo; no se extiende a otros cuadros de pared.

## Reconstrucción y respaldos

[procedencia_capturas.json](procedencia_capturas.json) conserva: auditoría histórica de las 18 S1 anteriores, auditoría vigente de las 12, once campos completos de cada exclusión/incorporación, originales y normalizados, residuos, motivos, autorización, SHA-256 del ZIP/CSV fuente y hashes de ambos CSV definitivos. El estado anterior corresponde al commit 021550eafbe1cc7d32f9474ed47f9d1dec53724a: 84 cuadros y 26 despejados, **solo como antecedente histórico**. La selección vigente es de 78 cuadros, 20 despejados y 58 obstáculos.

Antes de editar se verificó una copia externa de CSV, documentación y ocho JPEG. Las ocho copias retiradas se apartaron fuera del repositorio conservando nombres y bytes; los originales de prueba_manual, complemento_S1, ZIP y respaldos previos siguen intactos. No quedan JPEG excluidos dentro de evaluación. Ajuste y S2–S6 no cambiaron.

Los UUID históricos permanecen intactos. P5-06/P5-07 deben mantener una correspondencia trazable al emitir eventos que exijan prefijo de secuencia. El reproductor debe preservar huecos; no equivalen a evidencia de vía libre durante intervalos sin imágenes.
