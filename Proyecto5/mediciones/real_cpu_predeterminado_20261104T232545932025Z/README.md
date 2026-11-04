# E7: benchmark real local — issue #60 / PR #90

Medicion autorizada, no simulacion. Una sola corrida definitiva; no se repitio para mejorar tiempos.

- Inicio UTC: 2026-11-04T23:25:45.933073+00:00
- CPU: 13th Gen Intel(R) Core(TM) i7-13650HX; 20 procesadores logicos.
- SO: Windows-11-10.0.26300-SP0; Python 3.12.16; ONNX Runtime 1.30.0.
- CPUExecutionProvider; sin SessionOptions ni --hilos, como DetectorONNX. Intra/inter=0: automaticos.
- 10 calentamientos excluidos, 100 mediciones validas, 110 intentos, 0 fallos.
- Corriente verificada antes y despues. Carga previa total 4,61%; ver auditoria_equipo.json.

| Etapa (ms) | p50 | p95 | Maximo |
|---|---:|---:|---:|
| inferencia_ms | 8.828450 | 10.444850 | 14.623000 |
| politica_adaptador_ms | 0.918450 | 1.375170 | 4.826800 |
| posprocesamiento_ms | 3.443900 | 4.662870 | 5.223500 |
| preprocesamiento_ms | 2.565200 | 3.015080 | 3.169700 |
| total_local_ms | 15.868200 | 19.195585 | 22.058500 |

p95 y maximo del total local son inferiores a 100 y 250 ms; tambien se registra el plazo de edad de 300 ms.
No incluye red, camara, frenado fisico, lectura inicial de imagen o carga de sesion.
Politica + adaptador incluye evento/validacion/watchdog y JSONL/flush del adaptador virtual, sin motores.

## Integridad y reproduccion

- tiempos.csv: todos los intentos en orden; fallos.csv: solo fallos (cabecera si no hubo).
- contexto.json y resumen.json: parametros, opciones de sesion y hashes de entradas, pesos y codigo.
- comandos.jsonl: registro del adaptador virtual.
- resumen_recalculado.json: identico byte por byte a resumen.json.
- verificacion_independiente.json: recalculo adicional de CSV con biblioteca estandar.
- ejecucion.json: argumentos exactos, fechas y referencias de Git.
- codigo_benchmark.patch: cambios de codigo/pruebas sobre main no confirmados al medir.
- auditoria_equipo.json: corriente y muestra de carga previa/posterior.
- validaciones_software.json: 58 pruebas propias, 516 totales y Ruff aprobados.
- HASHES.sha256: integridad de todos estos archivos; no es una firma digital.
- .gitattributes: preserva los bytes originales, incluidos los CRLF de comandos.jsonl;
  no se normalizan sus finales de linea ni se edita la salida del adaptador.

Desde Proyecto5, sin inferencia y sin sobrescribir:

```powershell
python -B scripts/recalcular_benchmark.py --mediciones mediciones/real_cpu_predeterminado_20261104T232545932025Z
```

El HEAD registrado es e3530d6; el main integrado sin commit es 5a38de8.
Los hashes del codigo ejecutado y el parche hacen trazable el estado local; no atribuirlo al arbol limpio del HEAD.
El ensayo corto 3/10 permanece fuera del repositorio y no sustituye esta evidencia.
La revision del operador y el commit/push del PR quedan pendientes.
