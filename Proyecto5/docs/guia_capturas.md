# Capturas ESP32-CAM y validación — issue #57

Preparación vigente: [recaptura con persona real](protocolo_recaptura_persona_issue57.md)
en p5-05b-recaptura para un PR nuevo tras el merge de #79; S2/S3/S4/S6 y
[consentimiento escrito](consentimiento_recaptura_issue57.md).
La selección de 78 se conserva intacta hasta integrar las 54 nuevas verificadas.
El PM autorizó el perro de peluche como estímulo dog=16, declarado como peluche;
ver [convención y bloqueo temporal actual](autorizacion_estimulo_dog_p5_05b.md).
Los nuevos IDs son S2_f0001, etc.; se continúa el máximo al reabrir sin cambiar
IDs históricos. --resolucion 400x296 exige el tamaño orientado sin redimensionar.

Instalar dependencias de captura en el entorno del proyecto y ejecutar desde la raíz. Para las pruebas/estilo se necesitan pytest y Ruff; CI requiere Python 3.12 y sus dependencias. La base de main ya fue integrada en la rama; no se modifican sus módulos para validar capturas.

```powershell
& .\Proyecto5\.venv\Scripts\python.exe -m pip install -r Proyecto5/requirements-capturas.txt
$destino = Join-Path $env:LOCALAPPDATA ("P5-57\recaptura_persona_v2\" + (Get-Date -Format yyyyMMdd_HHmmss))
& .\Proyecto5\.venv\Scripts\python.exe .\Proyecto5\scripts\capturar_esp32.py --destino $destino --secuencia S2 --rotacion 180 --resolucion 400x296 --intervalo 0 --url http://192.168.1.93:81/stream
```

Mantener motores apagados/desconectados. Cerrar página de controles y cualquier otro cliente de cámara. La IP es local y variable; sin --url el programa conserva la dirección histórica. Usar un destino separado para nuevas capturas: no mezclar sesiones nuevas directamente con el conjunto revisado. El capturador continúa CSV existentes sin reemplazar JPEG; conservar una copia de seguridad antes de integrar.

| Tecla | Acción |
|---|---|
| 1–6 | Elegir S1–S6; conserva auto y reinicia temporizador, etiqueta vuelve a pendiente |
| B / D / U | Obstáculo / despejado / pendiente |
| Z | Alternar objeto fuera de riesgo; campo independiente de B/D |
| Espacio / C | Captura manual |
| A | Activar/pausar auto; --intervalo 2 inicia auto cada 2 s |
| G | Mostrar/ocultar guías de tercios y mitad |
| Q / Escape | Detener captura y cerrar hilo, HTTP y CSV |

La rotación (0, 90 horario, 180, 270 antihorario) se aplica antes de calcular zonas y guardar. Las guías se dibujan solo en una copia de vista previa: no se guardan. JPEG viejos/repetidos/corruptos no sirven como nuevos; ante cortes se bloquea guardado y se reconecta. --espera-inicial y --espera-cuadros (10 s por defecto), --reintento y --edad-maxima permiten configurar esperas y frescura.

## Escenarios y revisión visual

Solo person/dog/cat, definidas en [politica.yaml](../config/politica.yaml), campo clases_obstaculo. No se encontró descriptor formal de P5-03 en este checkout. La aceptación previa de estímulos 2D corresponde al protocolo histórico: la nueva orden del PM exige persona real en S2/S3/S4/S6. Conservar la procedencia anterior, sin afirmar detección automática. Una caja del sujeto ocupa cada tercio que toca. Riesgo: borde inferior y2 >= H/2; a 400×296 el límite es 148. El teléfono y los reflejos no son cajas de person/dog/cat.

- S1: vía libre. La selección vigente incluye dos fotografías de pared (59719 y 66562 ms) aceptadas expresamente por el PM como C1; esta decisión no autoriza incorporar otras tomas indeterminadas. [Autorización y trazabilidad](normalizacion_temporal_S1.md).
- S2: sujeto central, con ejemplos en mitad inferior; los extras fuera de riesgo están arriba de 148.
- S3: caja completa a izquierda de W/3, con margen; derecha y centro libres.
- S4: caja completa a derecha de 2W/3, con margen; izquierda y centro libres.
- S5: varios sujetos simultáneos cubren los tercios, incluido centro en riesgo. Las cajas/anotaciones y detección real quedan a P5-06/P5-03.
- S6: episodio real D–D–D–D–B–B–B–B–D–D–D–D; no reordenar por nombre ni mezclar episodios para simular transición.

CSV: sequence_id, frame_id, t_capture_ms, path, sha256, sequence_start_unix_ns, session_id, scene_label, outside_risk, image_width, image_height. **capturas.csv es la fuente de verdad para t_capture_ms, no el nombre del JPEG.** Tres S1 conservan números históricos distintos de los tiempos normalizados; no renombrar ni modificar tiempos para igualarlos. Tiempos corresponden a recepción local, no exposición del sensor. Mantener IDs/tiempos/sesiones/hashes; no reenumerar.

## Validación

```powershell
& .\Proyecto5\.venv\Scripts\python.exe .\Proyecto5\scripts\validar_capturas.py --issue57
& .\Proyecto5\.venv\Scripts\python.exe -m pytest Proyecto5/tests -q
```

El validador exige 6×10, >=60 distintos, >=20 B y >=20 D, sin pendientes, fuera de riesgo y ajuste de 1–2 secuencias separado por sesiones/hashes. Comprueba archivos, SHA-256, dimensiones, IDs, CSV y tiempos; no certifica clases ni detecciones. No debilitar reglas. [Ficha](ficha_auto.md), [procedencia](procedencia_capturas.json) e [informe para Emilio](entrega_emilio_issue57.md).

Selección conservada del protocolo anterior en PR #79: **78 JPEG de evaluación** (S1=12, S2=17, S3=13, S4=12, S5=12, S6=12), **20 despejados**, 58 obstáculos y 5 fuera de riesgo; ajuste conserva 7 S1 despejadas. Una nueva orden del PM requiere recapturar S2/S3/S4/S6 con persona real; aún no hay reemplazo ni un nuevo congelado para anotaciones/métricas. Cualquier retirada o reclasificación de otro negativo exige revisar el mínimo de 20. La aprobación del validador actual no certifica la futura selección ni independencia visual.
