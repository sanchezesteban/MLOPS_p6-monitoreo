# Inventario de adicionales (extras)

**Reglas que sigo para no contar dos veces:**
- **Base, sin bono:** las vistas mínimas de eventos y alertas, los dos umbrales, las capturas obligatorias, la regla sostenida configurada (R3.3), C1 y C2 y las 7 métricas base de [`metricas.md`](metricas.md).
- **Métricas:** cada métrica adicional es un indicador distinto de la métrica base de su grupo. No se reclaman variantes de parámetros (por ejemplo, otro percentil del mismo histograma).
- **Escenarios:** cada escenario adicional prueba una condición distinta de C1 y C2.
- **Funcionalidades:** cada funcionalidad es un flujo propio. La página de gráficas *muestra* algunas métricas adicionales, pero su bono es por la consulta visual, no por el cálculo, que se reclama aparte.

**Dónde se calcula cada cosa:**
- Métricas adicionales: [`src/p6/extras.py`](../src/p6/extras.py), desde observaciones primarias ya exportadas.
- Resultados por corrida: `evidencias/escenarios/<run>/metricas_extra.json`.
- Recálculo: `PYTHONPATH=src python -m p6.extras --run evidencias/escenarios/<run>`.
- Casos calculados a mano: [`tests/test_extras.py`](../tests/test_extras.py).

## Funcionalidades opcionales (F)

| ID | Descripción | Nivel solicitado | Complejidad y evidencia |
|---|---|---|---|
| F-01 | **Gráficas históricas por corrida** (`/graficas?run=`), en SVG generado en el servidor. Muestra el score principal por frame con los dos umbrales, colores por zona, `sin_detecciones` y `error` marcados sin score, límites de ventana, y apertura y resolución de cada alerta en su ventana. Muestra también la proporción baja por ventana frente a la referencia y a la condición (las ventanas insuficientes aparecen como «insuficiente», no como 0), la tabla de métricas adicionales por ventana y el incidente del manifiesto. | **10** | Consulta parametrizada por corrida sobre datos persistidos (SQLite, configuración y referencia). Estados verificados en `tests/test_extras.py::TestPortalExtras::test_graficas_estados`: sin corrida («elige una corrida»), corrida inexistente (404 con página de error), corrida sin incidente (mensaje) y caso normal. Capturas: `evidencias/extras/portal/F1-*.png` (s-sostenido, s-interrupcion, c2, vacío y no encontrado). |
| F-02 | **Revisión de capturas** (`/capturas`): galería de imágenes conservadas, con filtros por corrida, zona y estado. Cada tarjeta enlaza el evento y las alertas, muestra el motivo de la captura y avisa si el archivo falta. | **10** | Consulta parametrizada sobre `eventos.image_ref`, con comprobación de existencia en disco. Verificado: 21 capturas en zona baja en C2, estado vacío («No hay capturas»), filtro inválido (400) (`test_capturas_filtros_y_estados`). Capturas: `F2-capturas-c2-baja.png`, `F2-capturas-vacio.png`, `F2-capturas-filtro-invalido.png`. |
| F-03 | **Exportación de eventos a CSV** (`/exportar/eventos.csv?run=&zona=&estado=`) con los mismos filtros que `/eventos`, columnas fijas de identidad, estado, score, zona, modelo, configuración y captura, y la cabecera `X-Filas`. Enlazada desde `/graficas`. | **10** | Verificado en `test_exportar_csv_coincide_con_api`: el CSV tiene exactamente las filas de `/api/eventos` con el mismo filtro (21); un resultado vacío devuelve solo el encabezado; una corrida inexistente da 404; un estado inválido da 400. |

## Métricas adicionales (M)

| ID | Grupo | Métrica | Nivel solicitado | Definición, población, ausencia de datos y comprobación |
|---|---|---|---|---|
| M-01 | G2 | **FPS de captura** | **5** | (frames emitidos − 1) / (emisión del último − emisión del primero), por ventana y por corrida. Mide la etapa de la **fuente**, distinta de la base G2, que mide el procesamiento. Con menos de 2 frames o duración 0 da `None`. Caso a mano en `test_fps_captura_latencia_sindet_errores`. Resultado: 5.00 en todas las corridas, igual al fps declarado. |
| M-02 | G2 | **Latencia de extremo a extremo p50/p95** | **5** | `t_fin_mono − t_captura_mono` en ms, desde que la fuente emite el frame hasta que el evento está listo, con el mismo reloj monótono del proceso. Población: frames inferidos; los errores se excluyen. Sin frames da `None`. Ejemplo: C1 p95 = 39.1 ms. |
| M-03 | G4 | **Proporción de frames sin detecciones** | **5** | `sin_detecciones` / (`ok` + `sin_detecciones`). Excluye errores; sin frames inferidos da `None`. No equivale a un error del modelo. Ejemplos: C1 = 0.333 (escenas despejadas de S1), referencia = 0.024. |
| M-04 | G1 | **Tasa de errores técnicos** | **5** | Frames con `estado = error` / frames emitidos, por ventana y por corrida. Sin frames da `None`. Caso controlado: en `s-interrupcion` vale 1.000 en w002–w004 y 0.000 en el resto (corrida: 0.375). |
| M-05 | G3 | **CPU del proceso** | **3** | `psutil.Process().cpu_percent()` muestreado al cerrar cada ventana (100 = 1 núcleo); máximo y media. Ejemplo: C1, máximo 18.5 %. |
| M-06 | G4 | **Distancia KS a la referencia** | **8** | Estadístico de Kolmogorov–Smirnov de dos muestras entre los scores principales de la ventana (o de la corrida) y los 41 de la referencia. Solo se calcula si tiene el mismo modelo y la misma configuración del detector y la ventana tiene ≥ 6 frames puntuados; si no, da `None`. **Supuestos y límites:** es descriptivo; los frames consecutivos no son independientes, así que no se reporta p-valor; no confirma drift. **Caso controlado de cambio** (`s-sostenido`): 0.56–0.66 en las ventanas degradadas frente a 0.18–0.37 en las normales; la referencia contra sí misma da 0.000. Casos a mano en `test_ks_a_mano`. |
| M-07 | G7 | **Tiempo de detección** | **8** | `t_apertura` de la primera alerta de cada regla abierta después del inicio del incidente − `t_captura` del primer frame anómalo. Correlaciona tres fuentes: el registro del incidente (columna `fase` del manifiesto), los eventos y las alertas. Sin incidente o sin alerta da `None`. **Casos controlados:** `s-sostenido` da 1.824 s (baja confianza) y 5.832 s (cambio sostenido); `s-interrupcion` da 5.800 s (evidencia insuficiente). Las alertas abiertas antes del incidente se ignoran (`test_tiempos_incidente_controlado`). |
| M-08 | G7 | **Tiempo de recuperación** | **8** | `t_resolucion` de esa alerta − `t_captura` del primer frame de la fase `recuperacion`. Hace la misma correlación que M-07, pero es un indicador distinto del catálogo: mide la recuperación, no la detección. Sin recuperación o sin resolución da `None`. **Casos controlados:** 1.823 s (`s-sostenido`) y 1.828 s (`s-interrupcion`). |

## Escenarios adicionales (S)

Detalle completo en [`escenarios_extra.md`](escenarios_extra.md).

| ID | Condición | Nivel solicitado | Por qué ese nivel |
|---|---|---|---|
| S-01 | **Cambio sostenido de confianza** (`s-sostenido`) | **8** | Es una secuencia temporal: normal → degradada → recuperación. Muestra la transición, la persistencia (la alerta sostenida solo se abre en la 3.ª ventana seguida) y la recuperación (se resuelve). Sus registros están vinculados y las expectativas se verifican con 71 comprobaciones y 0 fallidas. |
| S-02 | **Interrupción del stream** (`s-interrupcion`) | **10** | Es una secuencia compuesta: fallo (30 frames sin imagen, en `error`), diagnóstico (ventanas INSUFICIENTES con reglas no evaluables), reacción (alerta `evidencia-insuficiente-v1`), recuperación (alerta resuelta) y verificación posterior (recálculo con 0 fallidas y G5 = 0.625 explicado). Hay evidencia reproducible de cada etapa. |

## Resumen de puntos solicitados (los otorga el evaluador)

| Tipo | Elementos | Puntos solicitados |
|---|---|---|
| F | F-01, F-02, F-03 | 10 + 10 + 10 = 30 |
| M | M-01 a M-08 | 5 + 5 + 5 + 5 + 3 + 8 + 8 + 8 = 47 |
| S | S-01, S-02 | 8 + 10 = 18 |
| **Total** | | **95** (no hay tope de extras) |
