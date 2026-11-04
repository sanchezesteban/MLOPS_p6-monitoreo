# Ficha del vehículo — P5-05 / issue #57

**P5-05b integrado localmente:** 78 JPEG de evaluación y siete de ajuste,
400×296 y orientación de captura 180°. Selección, encuadres S3/S4, seis sustituciones
S2, normalización/interrupción, gatos y peluche dog=16 aprobados según comunicación
del operador. Consentimiento de publicación completo: firma 2026-11-03, alcance GitHub confirmado.
Ver [autorizaciones](autorizaciones_finales_p5_05b.md) y [entrega actual](entrega_emilio_p5_05b.md).

Estado: datos integrados y validados; **pendiente de aceptación del alcance del rango físico y confirmaciones del operador**. La identificación del controlador es documental, sin inspección del chip; no se afirma cierre completo.

| Dato | Valor y fuente |
|---|---|
| Kit | TSCINBUNY Smart Robot Car Kit ZYC0024, confirmado por el operador |
| Cámara | ESP32-CAM; JPEG de 400 × 296 píxeles comprobados en evaluación y ajuste |
| Orientación | Rotación de 180° durante captura, confirmada por el operador; no se volvieron a codificar los JPEG |
| Alimentación | Baterías instaladas; motores/ruedas y control web funcionan según el operador. Capturas históricas S1/ajuste: USB, vehículo inmóvil. Tipo, tensión, celdas y carga de batería pendientes |
| Motores durante las capturas | **Apagados en todas las secuencias definitivas S1–S6; vehículo inmóvil y cámara funcionando**, declaración confirmada personalmente por el operador el 2026-11-03. Cumple la condición de #57 por confirmación del operador, sin verificación mediante sensores |
| Controlador de motores | **Controlador L298N según documentación del modelo, pendiente de corroboración física**; ver fuente y alcance abajo |
| Dirección | Giro sobre el propio eje observado por el operador. No se inventa servo, geometría ni ángulo de dirección de ruedas |
| Interfaz web | Avance, retroceso, derecha, izquierda y cámara; **sin barra, porcentajes ni selector de velocidad**, confirmado personalmente por el operador |
| Niveles seleccionables | **Un único nivel de actuación disponible por movimiento**. Describe el mando, no la velocidad física máxima del hardware |
| Velocidad inicial | **0.545 m/s = 1.962 km/h**, medición manual inicial comunicada; sin distancia/tiempo crudos ni condiciones suficientes para fijar un rango |
| Giro inicial por lado | Aproximadamente **90° en 0.35 s de movimiento observado** a derecha y a izquierda; no es tiempo de pulsación. Estimación 90/0.35 = **257.14 °/s** |
| Rango desde la web | No existe un rango seleccionable: solo está disponible el nivel observado. No se inventan velocidades mínima/máxima, PWM ni fracciones configurables |
| Rango físico de velocidad y dirección | **No caracterizado**. La velocidad con ese mando y los giros manuales aproximados no identifican el máximo físico ni todas las órdenes que pudiera admitir el firmware |
| Ritmo de recepción medido | Tres ventanas de 10 s: **48.9, 49.4, 48.6 JPEG distintos/s**, media **48.9667**, desviación muestral **0.4041**; [registro original](medicion_fps_issue57.json) |
| Límites de FPS | Mide recepción de JPEG completos y decodificables con hashes distintos, no exposición nominal del sensor ni frecuencia de guardado. Lecturas agrupadas producen intervalos cero. Condiciones del registro: «No registradas» |
| IP local variable | Última usada: `192.168.68.113`; stream `http://192.168.68.113:81/stream`, configurable con `--url`. No abrir controles y stream simultáneamente |
| Concurrencia | Un único cliente de cámara; cerrar controles, navegador y capturador antes de medir FPS |
| Condiciones visuales | Interior doméstico, suelo de baldosas, reflejos y luz variable; montaje/altura/inclinación y lux sin medición |

El archivo local de registro manual con distancias de 1 m y tiempos 1.80/1.83/1.84 s contiene entradas de ejemplo según aclaración del operador: **no se declara una velocidad física nueva a partir de él ni se incluye como evidencia**. El valor **0.55** introducido en esa prueba tampoco es una velocidad seleccionable de la web. El programa calcula a partir de lo introducido; dry-run no certifica que una prueba se haya realizado. No se inventan precisión, desviación estándar ni repeticiones de las mediciones manuales.

## Fuente documental del controlador

El [manual ZYC0024.pdf alojado en Analog Technologies](https://www.analogtechnologies.com/document/ZYC0024.pdf), sección Product Performance Parameters, especifica un módulo L298N y reductora 48:1, además de ESP32-CAM y control Wi-Fi. El documento denomina al kit **ESP32Bot1.0** y su URL lleva ZYC0024: es una referencia compatible con la familia descrita, sin confirmar marca/revisión exacta del equipo instalado. Fuente consultada nuevamente el 2026-11-03. No se inspeccionó físicamente el chip; no se encontró firmware ni fotografía identificativa de la placa en el repositorio que lo corrobore independientemente. La reducción es documental, no una medición de esta unidad. No se atribuyen tensión exacta, RPM nominales ni velocidades no verificadas.

## Datos y procedencia

Evaluación: **78 JPEG** (S1=12, S2=17, S3=13, S4=12, S5=12, S6=12),
20 despejados, 58 obstáculos según CSV y **seis** fuera de riesgo. Ajuste:
**siete JPEG S1 despejados**, intactos, sin positivos y separado de evaluación.
No son resultados de inferencia. [CSV](../datos/evaluacion/capturas.csv),
[selección y exclusiones](seleccion_78_p5_05b.md), [hashes](../datos/HASHES_p5_05b.sha256).

S1 y S5 conservan sus 24 JPEG de la selección vigente anterior, por instrucción PM.
S1 mantiene sus dos sesiones y la solución autorizada de pared como C1; su
[normalización previa](normalizacion_temporal_S1.md) no se alteró. S5 conserva
los estímulos históricos de teléfono por esa instrucción, sin presentarlos como
recaptura física nueva. S2/S3/S4/S6 se sustituyeron por 54 fotografías de persona,
gatos reales, peluche dog autorizado y fases despejadas. S6 mantiene D4–B4–D4.
Los seis fuera de riesgo están al final de S2, con alias derivados e
[interrupción documentada](normalizacion_temporal_S2_p5_05b.md).
Los archivos de 84/78, JPEG y CSV fuente originales siguen preservados; la
[procedencia anterior](procedencia_capturas.json) es histórica y la
[procedencia P5-05b](procedencia_recaptura_persona_issue57.json) describe el conjunto actual.

## Procedimiento y pendientes físicos

Se conservan 0.545 m/s y aproximadamente 90°/0.35 s por lado como antecedentes manuales iniciales; 257.14 °/s es una estimación, no un resultado automatizado. No se solicita grabar ni repetir los giros para aumentar precisión: #57 no prescribe video, número de repeticiones ni incertidumbre. Se distinguen tiempo observado de movimiento y duración del comando. [Registro manual y FPS](mediciones_carrito_issue57.md).

El criterio literal de #57 pide rango real de velocidad/dirección; con el mando sin selector solo se conoce el comportamiento comunicado para su único nivel. Caracterizar un rango más amplio requeriría documentación de la revisión instalada y de las órdenes admitidas por el firmware, y una metodología física acordada. Corresponde al PM/profesor aceptar esta limitación o definir información adicional; no se modifica el vehículo ni se exige precisión no prescrita.

Quedan pendientes corroboración física del controlador, características de batería/montaje, alcance del rango. La separación de escenas se corrigió mediante la selección autorizada por el PM, sin cambiar las siete imágenes de ajuste; no se presenta como certificación automática de independencia estadística. La condición de motores apagados durante todas las capturas S1–S6 quedó cumplida por declaración confirmada del operador; no se solicitan recapturas por este motivo. No se habilita control automático real: protocolo instalado, STOP y parada independiente no verificados físicamente. El watchdog y adaptador virtual de main son pruebas de software, no certificación del vehículo. [Condiciones y criterios](entrega_emilio_issue57.md).

El [CSV de evaluación](../datos/evaluacion/capturas.csv) es la fuente de verdad para t_capture_ms; tres S1 conservan nombres con tiempos históricos distintos de los normalizados. No se renombraron los JPEG fuente; los seis alias derivados S2 tienen correspondencia explícita. Las clases person, dog y cat están definidas en [politica.yaml](../config/politica.yaml), campo clases_obstaculo; el descriptor P5-03 está referenciado en el PR #80 y no está en este HEAD histórico de partida. No se afirma que no exista en el proyecto ni que se haya ejecutado inferencia.
