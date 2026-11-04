# S2: candidato temporal normalizado — P5-05b / issue #57

**Integrado localmente y aprobado por el PM; consentimiento completo para GitHub, firmado el 2026-11-03.** La conversión del reloj
registrado es reproducible y el candidato aprueba `--issue57`. Sebastián aceptó
expresamente S2 interrumpida con normalización documentada como S1, con los seis
adicionales al final o corte reconocido. Se verificaron las últimas seis posiciones.
Los encuadres S3/S4 y las seis sustituciones también fueron aprobados después;
[autorizaciones finales](autorizaciones_finales_p5_05b.md). La copia privada original sigue intacta.
No se certifica una captura continua ni sincronización UTC independiente.

## Evidencia y precisión del reloj

En [anchored_clock()](../scripts/capturas_core.py), cada lector toma una muestra
de `time.time_ns()` y una de `time.monotonic_ns()`. Luego avanza únicamente con
la diferencia monotónica. La reconexión de ese lector conserva su reloj; una
nueva ejecución crea otro anclaje. Un ajuste del reloj de Windows no altera un
lector ya iniciado, pero puede afectar la relación con un lector posterior.
Las dos muestras iniciales no son atómicas y no se guardaron para calibración.

CaptureStore guarda `(recepcion_ns - origen_ns) // 1000000`. Por eso
`origen + t_capture_ms * 1000000` reconstruye el tiempo registrado truncado,
no la hora exacta de recepción ni de exposición. Su truncamiento original es
inferior a 1 ms respecto al reloj de recepción del programa; no expresa exactitud UTC.

Se contrastaron las 58 filas principales y seis adicionales con las fechas de
escritura de los 60 JPEG todavía disponibles. Las diferencias son positivas:
1.9503–53.6898 ms en conjunto; en S2 principal 14–50 ms y adicional 23–46 ms
(rangos enteros truncados). No hay retrocesos dentro de las sesiones registradas.
Las fechas de archivos usan el mismo reloj de Windows: corroboran consistencia,
pero no son una referencia independiente.

Se consultó el registro System de Windows entre 03:20 y 05:00 UTC del 2026-11-04:
Kernel-General, evento 1, registra un salto de +4987838 ms a las 03:22:39.500 UTC,
anterior a las dos carpetas de captura y al primer cuadro principal de las
03:35:47.573381600 UTC. No se encontraron otros eventos de ese tipo en el intervalo,
ni eventos Time-Service entre 03:35 y 05:00 UTC. El salto previo no atraviesa la
cronología auditada. La ausencia de eventos no descarta ajustes graduales ni
certifica sincronización entre procesos; no existe calibración cruzada guardada.

**Conclusión:** hay evidencia coherente y sin señales observadas de un salto
durante estas capturas para normalizar el reloj registrado. La continuidad física
de S2 no se inventa: el PM ya aceptó la interrupción documentada y varias sesiones.

## Cálculo entero y pausa conservada

| Fuente S2 | Origen original, ns |
|---|---:|
| Principal y origen común O | 1793763347573381600 |
| Adicional | 1793767996073360200 |

```text
A = origen_original_ns + t_original_ms * 1000000
(t_derivado_ms, residuo_ns) = divmod(A - O, 1000000)
A = O + t_derivado_ms * 1000000 + residuo_ns
```

La diferencia de orígenes es **4648499978600 ns**: 4648499 ms más 978600 ns.
Esto equivale a **77 min 28.4999786 s**, entre el origen de S2 principal y el
origen adicional. No es la pausa desde el último cuadro principal: este ya estaba
en t=2831460 ms = **47 min 11.460 s** desde el origen principal.
La diferencia es 77:28.4999786 − 47:11.460 = **30:17.0399786**.
Ambas cifras describen extremos distintos y son compatibles; no se recortó la pausa.
No se usaron floats, cadencia prevista, números del nombre ni offsets arbitrarios.
Los once S2 principales conservados (f0007–f0017) mantienen sus tiempos y origen.
El primer conservado tiene t=46797 ms: no se desplaza artificialmente a cero.
Las seis incorporaciones conservan su sesión original
`3ecf440718884a7bb6eeb59e841e1cd0`. Su residuo es siempre **978600 ns**.

| ID fuente adicional | t original, ms | A reconstruido, ns | ID derivado | t derivado, ms |
|---|---:|---:|---|---:|
| S2_f0001 | 0 | 1793767996073360200 | S2_f0018 | 4648499 |
| S2_f0002 | 5844 | 1793768001917360200 | S2_f0019 | 4654343 |
| S2_f0003 | 13297 | 1793768009370360200 | S2_f0020 | 4661796 |
| S2_f0004 | 22563 | 1793768018636360200 | S2_f0021 | 4671062 |
| S2_f0005 | 24875 | 1793768020948360200 | S2_f0022 | 4673374 |
| S2_f0006 | 38781 | 1793768034854360200 | S2_f0023 | 4687280 |

Entre S2_f0017 (principal, t=2831460 ms) y el primer adicional quedan
**1817039978600 ns = 30 min 17.0399786 s**, según el reloj reconstruido.
El CSV entero representa la pausa con precisión de milisegundos; el residuo
conservado permite reconstruir toda la diferencia sin perder la fracción.
No se sustituye esa interrupción por un intervalo corto ni se reasignan sesiones.

## Sesiones originales y orden final verificado

| session_id original | Cuadros S2 conservados | t común, ms |
|---|---|---|
| 65b863c17bcf4f41973224beed18e1af | f0007–f0008 | 46797–58828 |
| cd13ae31792e458cb3180bc7507eaa5a | f0009–f0016 | 300734–838702 |
| 38471f5bb4294d87b3b1e1b0b623a256 | f0017 | 2831460 |
| 3ecf440718884a7bb6eeb59e841e1cd0 | alias f0018–f0023 (originales f0001–f0006) | 4648499–4687280 |

Los seis adicionales ocupan posiciones 12–17 de S2, al final. Se conservan
cuatro sesiones y tres cortes; [registro de cortes](cortes_sesion_S2_p5_05b.csv).
El candidato satisface el orden solicitado, pero el reproductor consultado
comprime los cortes a 100 ms: [hallazgo y propuesta](propuesta_reproductor_cortes_p5_05b.md).
No se modificó ese componente ni se considera verificada una corrida integral.

## Selección, identidad y trazabilidad

Se conserva la propuesta previa: sustituir únicamente seis S2 principales
f0001–f0006 por los seis adicionales, sin usar inferencias para decidir. La
justificación de selección conserva los motivos conocidos y las seis sustituciones aprobadas; no es una sesión única de 17.
También se conservan documentadas las cuatro exclusiones manuales anteriores:
S3_f0004, S3_f0005, S4_f0002 y S4_f0008, disponibles en el ZIP de respaldo.

Los alias derivados f0018–f0023 y sus rutas nuevas existen en la **selección derivada integrada**:
no son nuevos eventos de captura. No se renombró ningún original. Las once
imágenes principales conservan IDs y rutas. La
[correspondencia de los 17 S2](correspondencia_normalizacion_S2_p5_05b.csv)
incluye origen, sesión, ID, ruta y tiempo originales, A reconstruido, ID/ruta/tiempo
derivados, residuo y SHA. Emilio debe unir por dataset fuente + sesión + ID + SHA;
el COCO definitivo usará los IDs/rutas derivados del conjunto finalmente congelado.
No utilizar el nombre histórico del JPEG como tiempo de captura.

CSV de origen, sin cambios:

- Principal: `5fab0bf5d06036fe329a4c16c7ab53dc10cca9d52fab44f9bcf5eb48b54ac652`.
- Adicional: `d6863a267f56c82ca654d8e93969c68b4aa83f3dd5f67ce261eb2f0bbc0ba32a`.
- Candidato normalizado: `f8a04169513825fb2c943772c4353924eb453fe88ba1f2419fe70971487f6181`.

El respaldo íntegro previo y los snapshots históricos de 84/78 siguen intactos.
El candidato privado conserva además el CSV combinado anterior byte por byte,
auditoría por fila y procedencia completa de las 78 imágenes. El puntero local
`Proyecto5/resultados/normalizacion_S2_privada/ubicacion.json`, ignorado por Git,
localiza candidato, manifiestos, contraste con mtime, eventos de reloj, logs de
pruebas y verificaciones. No publicar ese directorio ni sus imágenes de revisión.

## Herramienta y resultados

[normalizar_tiempos_capturas.py](../scripts/normalizar_tiempos_capturas.py) exige
origen común presente en los datos, sesión original para los alias y destino nuevo.
Verifica SHA y colisiones, no redondea al alza tiempos empatados ni sobrescribe.
La herramienta no mide fiabilidad del reloj ni autoriza el protocolo.
Ejemplo sobre la copia combinada privada anterior, con el entorno activado:

```powershell
python Proyecto5/scripts/normalizar_tiempos_capturas.py --datos "$fuentePrivada/datos/evaluacion" --salida "$copiaNueva/datos/evaluacion" --secuencia S2 --origen-unix-ns 1793763347573381600 --alias-sesion 3ecf440718884a7bb6eeb59e841e1cd0 --primer-alias 18
python Proyecto5/scripts/validar_capturas.py --issue57 --datos "$copiaNueva/datos/evaluacion" --ajuste "$fuentePrivada/datos/ajuste"
```

El conjunto integrado conserva 12/17/13/12/12/12, 78 JPEG, 20 despejados, 58 obstáculos
y seis outside_risk; siete imágenes de ajuste separadas. `--issue57`: aprobado,
sin errores. Los 85 SHA coinciden, no hay huérfanos ni IDs/hashes duplicados o
compartidos con ajuste, y los tiempos son estrictamente crecientes por secuencia.
La revisión visual de los seis peluches respalda y2<148, con margen pequeño en
algunos cuadros; Emilio debe confirmar cajas al anotar. La escena de ajuste es
diferente de la recaptura; S1/S5 y la selección previa de ajuste no se alteraron.
No se afirma independencia estadística entre cuadros de una misma secuencia.

Python 3.10.8: **287 pruebas y 53 subpruebas aprobadas**, incluidas 11 nuevas de
aritmética, residuos, pausa, alias, conservación y límites del reloj anclado.
Ruff check y format --check ejecutados de nuevo y aprobados (44 archivos). Sin cámara ni inferencia.
No se ejecutó Python 3.12 localmente. El validador permanece sin cambios.

## Autorizaciones finales y dependencias

El PM aprobó los encuadres S3/S4, seis sustituciones, normalización e interrupción
S2 documentada, gatos reales y peluche dog=16. Se verificó el orden y se integró
la copia ya validada sin regenerar tiempos. La [selección](seleccion_78_p5_05b.md)
conserva las cuatro exclusiones manuales sin inventar sus motivos individuales.

El [reproductor consultado](propuesta_reproductor_cortes_p5_05b.md) todavía comprime
la pausa a 100 ms y no lee sesiones. Se entregan cortes y correspondencias para
que sus responsables coordinen la solución; no se modificó su código ni el #59.
El consentimiento está completo, firmado el 2026-11-03. Quedan COCO/manifiesto
y confirmación de recepción de Emilio. No se necesitan otras once capturas por este bloqueo temporal.

Validación final sobre el conjunto integrado: [resumen](estado_final_p5_05b.json).
Todos los tiempos originales, sesiones, residuos y SHA anteriores permanecen verificables.
