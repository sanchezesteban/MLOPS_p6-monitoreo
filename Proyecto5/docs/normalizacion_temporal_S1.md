# Procedencia temporal de S1

Se conservan **18 cuadros originales** de cuatro sesiones; se apartaron posiciones 5 y 6 por encuadre casi exclusivo de pared, y 7 por oscuridad/bandas. Posiciones definidas ordenando t_capture_ms del CSV anterior. Los tiempos de los seleccionados no cambiaron en esta integración; no se comprimen pausas ni se renumeran IDs.

La normalización previa, autorizada anteriormente por el operador, usó evidencia registrada:

```text
O = 1793493718610840900 ns
O_complemento = 1793497499851940400 ns
A_estimado_ns = origen_original_ns + t_original_ms * 1000000
(t_normalizado_ms, residuo_ns) = divmod(A_estimado_ns - O, 1000000)
```

Desfase del complemento: 3781241 ms y residuo 99500 ns, conservado en [procedencia_capturas.json](procedencia_capturas.json), que incluye los valores originales y conservados de cada S1. Se verifica exactamente `O + t_normalizado_ms*1000000 + residuo_ns = A_estimado_ns`. No certifica reloj entre ejecuciones ni tiempo de exposición.

| session_id original | Cuadros conservados |
|---|---:|
| 80a436749c3047ae9074fabba4ab220e | 7 |
| e2b4a168ded24ec38bc6db62dd7dfead | 5 |
| eb5c3d737acc4ccf8b450f37e4f6751e | 4 |
| 9fa340d096094511b5ec82711d3f922b | 2 |

No es una secuencia continua: mantiene pausas entre sesiones de aproximadamente 3623351, 1451526 y 36606 ms, además de huecos por cuadros descartados. Su aceptación semántica como S1 debe revisarla el PM. El respaldo completo de CSV/auditorías previos permanece externo al PR; sus hashes fuente están en la procedencia.

Los UUID históricos permanecen intactos. El contrato de eventos exige prefijo de secuencia: P5-06/P5-07 deben acordar una correspondencia trazable al emitir eventos, sin editar los ID fuente. Las recapturas ya tienen prefijo. El reproductor debe preservar huecos; no equivalen a evidencia de vía libre en los intervalos sin imágenes.
