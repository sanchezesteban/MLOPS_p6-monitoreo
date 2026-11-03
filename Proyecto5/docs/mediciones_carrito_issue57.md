# Mediciones físicas y FPS — issue #57

Antecedentes manuales comunicados: 0.545 m/s = 1.962 km/h; giro sobre el propio eje de aproximadamente 90° en 0.35 s observados por lado, estimación 257.14 °/s. No son mediciones automatizadas. No se inventan rangos físicos, precisión, desviación estándar ni repeticiones. Los tiempos de ejemplo 1.80/1.83/1.84 s del registrador no son evidencia física.

La web solo ofrece avance, retroceso, derecha, izquierda y cámara, **sin selector de velocidad**. Existe un único nivel seleccionable por movimiento. El valor **0.55** de la prueba de software no es una consigna disponible; no se confunden PWM, fracciones normalizadas ni m/s con el nivel del mando.

## Registro manual opcional, sin actuaciones

No hace falta ejecutarlo de nuevo para conservar las mediciones disponibles. La herramienta calcula entradas manuales; no certifica que una prueba se haya realizado.

```powershell
& .\Proyecto5\.venv\Scripts\python.exe .\Proyecto5\scripts\medir_movimiento.py --tipo avance --dry-run --nivel "mando original unico, sin selector de velocidad"
```

--tipo admite avance, derecha e izquierda. La herramienta solicita tres entradas por tipo como función de registro, **no como mínimo impuesto por #57 ni como solicitud de repetir giros**. Separa duración solicitada/real del comando de tiempo observado y distancia/ángulo; lo desconocido queda nulo. Calcula v=d/t, km/h=3.6v y omega=angulo/tiempo observado, y estadísticas solo de lo introducido. Guarda JSON exclusivo en resultados/mediciones, ignorado por Git. No envía órdenes; --modo-real sigue bloqueado por firmware/STOP/parada independiente no comprobados.

Registrar únicamente mediciones realizadas, no copiar ejemplos. No se pide video ni nuevas repeticiones de giros, ni se implementó análisis de orientación. El rango físico literal del issue sigue sin caracterizarse: el PM/profesor debe decidir si acepta el único nivel del mando o qué evidencia adicional necesita, sin modificar el vehículo ni inventar capacidades.

## FPS de recepción

Cerrar controles y capturador. Motores apagados/desconectados; un único cliente.

```powershell
& .\Proyecto5\.venv\Scripts\python.exe .\Proyecto5\scripts\medir_fps.py --url http://192.168.68.113:81/stream
```

Espera primer JPEG válido como ancla y mide tres ventanas secuenciales de 10 s. Cuenta llegadas posteriores con hashes distintos, registra intervalos y descarta corruptos/duplicados. Cortes/congelación invalidan repetición; HTTP se cierra antes de la siguiente. No guarda JPEG ni modifica CSV. --espera-inicial/--espera-cuadros ajustan esperas. Una escena estática puede producir hashes idénticos: no afirmar FPS nominales del sensor.

[Registro medido original](medicion_fps_issue57.json): 489/494/486 cuadros nuevos en 10 s cada uno, 48.9/49.4/48.6 recibidos/s; promedio 48.97 (valor sin redondear 48.9667), desviación muestral de FPS 0.4041. Se comprobó coherencia de conteos, ventanas y listas, y coincidencia byte a byte con el archivo local original. Condiciones no registradas; intervalos cero reflejan lecturas agrupadas. No se repitió la medición ni se conectó al carrito durante esta revisión.
