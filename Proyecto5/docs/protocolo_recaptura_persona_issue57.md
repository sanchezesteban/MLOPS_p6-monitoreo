# Preparación de recaptura con persona real — P5-05b / issue #57

**Estado final posterior:** las aprobaciones S3/S4, seis sustituciones S2,
normalización/interrupción, gatos y peluche dog=16 están comunicadas por el operador.
La selección de 78 se integró localmente y validó de nuevo; ver [entrega vigente](entrega_emilio_p5_05b.md).
El contenido anterior se conserva como historial/protocolo; sus pendientes de
aprobación ya resueltos no describen el estado actual. Consentimiento completo: firma 2026-11-03 y alcance GitHub confirmados.

**Actualización temporal posterior:** el candidato privado normalizado aprueba
--issue57 con 78/20D/58B y seis fuera de riesgo; [evidencia y pendientes PM](normalizacion_temporal_S2_p5_05b.md).
Los rechazos temporales indicados abajo describen la propuesta anterior sin normalizar.
La evaluación activa y las fuentes no se modificaron.

Estado: **54 JPEG recibidos y auditados; no integrados ni aprobados para publicación**.
**Actualización del PM:** el perro de peluche está autorizado como estímulo
dog=16, identificado como peluche y no animal real. Los seis adicionales son
visualmente fuera de riesgo. El candidato privado tiene una escala S2 derivada
autorizada para investigación, con origen/tiempos originales auditados; aprueba
--issue57. El PM aceptó S2 interrumpida; falta revisar encuadres y justificación
de selección, sin cambiar el candidato.
Ver [autorización y estado actual](autorizacion_estimulo_dog_p5_05b.md).
El CSV fuente conserva 58 filas tras cuatro eliminaciones manuales del operador.
Hay personas, gatos y peluches; S6 usa peluche en su fase de obstáculo.
Ver [auditoría previa a integración](auditoria_recaptura_p5_05b.md).
Orden del PM comunicada por el operador: sustituir los estímulos de teléfono de
S2/S3/S4/S6 por una persona real. El detector puede identificar la pantalla como
tv; no se cambian sus clases, umbrales ni código. S1 y S5 se conservan por la
instrucción actual del PM, salvo una nueva orden expresa.
No se presenta la selección futura como una captura totalmente nueva: conservará
24 cuadros de S1/S5 y tendrá 54 nuevos, si el PM mantiene esa decisión.

## Entorno y protección

El PR #79 ya está fusionado en main: merge b6317b5, que incluye bd1ff9e.
Esta preparación corresponde a un **PR nuevo**, titulado
**P5-05b: Recaptura real S2, S3, S4 y S6**, sin modificar el historial del PR #79.
Trabajar en p5-05b-recaptura, creada desde origin/main b6317b5, en un worktree separado.
No se creó desde p5-05-capturas ni se incorporaron sus commits locales posteriores.
El checkout de métricas
permanece en p5-07-metricas, commit 67d5284. Nunca copiar sus commits a esta rama.
Los 173 archivos del inventario local previo están respaldados y se verificaron
contra el resguardo antes de crear el worktree (172 no versionados y un marcador
vacío ya versionado). La ruta de ese resguardo se entrega en el informe local;
no se publican datos privados ni copias ZIP.

Los snapshots completos están en [archivo/](../datos/archivo/README.md):
84 históricos de 021550e y 78 vigentes de bd1ff9e, sin mover ni recodificar nada.
La evaluación y el ajuste actuales permanecen intactos durante esta preparación.
Los archivos históricos nunca son entradas de la nueva evaluación ni del ajuste.

## Protocolo previamente fijado

| Secuencia | Cuadros nuevos | Condición |
|---|---:|---|
| S2 | 17 | Sujeto autorizado central; riesgo en mitad inferior y ejemplos aprobados fuera de riesgo |
| S3 | 13 | Sujeto autorizado completo a la izquierda de W/3, con margen |
| S4 | 12 | Sujeto autorizado completo a la derecha de 2W/3, con margen |
| S6 | 12 | Cuadros 1–4 libres, 5–8 con estímulo autorizado, 9–12 libres |
| Total | 54 | Una toma planificada, sin selección por desempeño del detector |

- ESP32-CAM, **400 × 296 después de orientar**, rotación **180°**. Las guías
  solo aparecen en vista previa; el JPEG guardado conserva la orientación elegida.
- Motores apagados/desconectados durante todas las secuencias. No activar controles.
  Un solo cliente del stream; cerrar controles web, otros visores y medidores de FPS.
- Una caja ocupa cualquier zona que toque. A 400×296, límites X=133.33/266.67 y
  Y=148. Persona completa, incluidos pies y extremidades, dentro del tercio lateral
  con margen para S3/S4. Zona de riesgo si y2>=148; fuera de riesgo si y2<148.
- Fijar posición de cámara, escenario, fases y cadencia antes de capturar. Usar
  vista previa para encuadre geométrico, sin ejecutar el detector ni revisar sus
  confianzas para elegir, repetir o sustituir tomas. No eliminar cuadros desfavorables.
- Registrar incidencias de corte, error, sobrecaptura o incumplimiento físico;
  conservar el material y consultar al PM antes de excluir o repetir una secuencia.

Las cinco marcas outside_risk antiguas están en S2 (4) y S3 (1) y no se heredan.
Ahora existen seis ejemplos adicionales con el peluche dog autorizado, revisados
por encima de Y=148. La propuesta privada mantiene las cuotas sustituyendo seis
S2 por correspondencia explícita. La investigación y copia normalizada fueron
autorizadas posteriormente por el operador; [cálculo y auditoría](normalizacion_temporal_S2_p5_05b.md).
El candidato aprueba --issue57, conserva originales/sesiones y documenta la pausa.
El PM ya aceptó S2 interrumpida/normalizada y los seis adicionales al final.
Antes de integrar, revisar encuadres y [justificación de selección](seleccion_78_p5_05b.md).
No añadir cuadros para alterar las cuotas ni modificar reglas para aprobar.

## Captura en Windows

Activar un entorno con [requirements-capturas.txt](../requirements-capturas.txt)
y situarse en la raíz del worktree. Se puede reutilizar el Python del checkout
principal sin instalar ni copiar su código. La ruta concreta se entrega al operador.
Crear **una carpeta nueva fuera del repositorio**, compartida por las cuatro ejecuciones:

```powershell
$base = Join-Path $env:LOCALAPPDATA ("P5-57\recaptura_persona_v2\" + (Get-Date -Format yyyyMMdd_HHmmss))
$stream = "http://192.168.1.93:81/stream"
```

Confirmar la IP real antes de abrir el stream; la dirección puede cambiar.
Con el entorno activado, ejecutar uno a la vez y cerrar con Q antes del siguiente:

```powershell
python Proyecto5/scripts/capturar_esp32.py --url $stream --destino $base --secuencia S2 --rotacion 180 --resolucion 400x296 --intervalo 0
python Proyecto5/scripts/capturar_esp32.py --url $stream --destino $base --secuencia S3 --rotacion 180 --resolucion 400x296 --intervalo 0
python Proyecto5/scripts/capturar_esp32.py --url $stream --destino $base --secuencia S4 --rotacion 180 --resolucion 400x296 --intervalo 0
python Proyecto5/scripts/capturar_esp32.py --url $stream --destino $base --secuencia S6 --rotacion 180 --resolucion 400x296 --intervalo 0
```

Antes de la primera captura, pulsar B en S2/S3/S4 y D en S6. Espacio guarda un
cuadro fresco. En S6: D durante cuatro capturas, B durante cuatro y D durante las
últimas cuatro, siguiendo la transición física real. Z alterna outside_risk
cuando corresponda al caso aprobado y visible; es independiente de B/D.
Verificar los conteos guardados 17/13/12/12 y pulsar Q al completarlos: no hay
cierre automático por cupo. No cambiar de secuencia con 1–6 durante estas tomas.

La resolución requerida se comprueba antes de guardar. Una discrepancia detiene
la sesión sin redimensionar ni configurar firmware; revisar cámara/stream antes
de continuar. No se admiten cuadros viejos, corruptos o duplicados exactos como
capturas nuevas; sus intentos rechazados aparecen en consola, sin consumir IDs.
Guardar un registro de incidencias: la consola no es un manifiesto de intentos.
Usar la [plantilla de incidencias](incidencias_recaptura_issue57.csv): una fila
por incidencia real, con secuencia, sesión y frame_id si ya existe, hora observada,
descripción y acción. No completar datos desconocidos ni borrar el intento fallido.
La plantilla vacía no acredita una sesión sin incidencias.

## Identidad, tiempo y entrega

Cada cuadro realmente guardado recibe S2_f0001, S2_f0002, etc., con contador por
secuencia. Reabrir continúa tras el máximo existente, sin renumerar UUID antiguos.
No se cambió el esquema CSV. El primer cuadro guardado fija el origen temporal;
t_capture_ms deriva del reloj monotónico de recepción anclado a UTC, no del número
de cuadro ni de la cadencia prevista. Se preservan pausas y cada session_id real
(UUID nuevo por ejecución si no se especifica uno). No reutilizar sesiones antiguas
para aparentar continuidad. El hash se calcula sobre los bytes del JPEG guardado.

Entregar la carpeta $base completa con **54 JPEG, subcarpetas S2/S3/S4/S6 y un
capturas.csv**, registro de incidencias y [nota de consentimiento](consentimiento_recaptura_issue57.md)
completada sin datos personales. No enviar el documento firmado ni incorporarlo a Git.
Las nuevas fotografías permanecen privadas fuera del repositorio hasta verificar
que el consentimiento firmado existe y cubre publicación en el repositorio.

Para revisar integridad parcial sin exigir seis secuencias:

```powershell
python Proyecto5/scripts/validar_capturas.py --datos $base --solo-integridad
```

La integración posterior verificará todos los bytes/hashes, CSV, sesiones,
orígenes, IDs únicos, etiquetas y mínimos; reemplazará únicamente S2/S3/S4/S6 tras
revisar las 54 reales, consentimiento y decisiones del PM. Mantener S1=12 y S5=12;
con S6=8 D/4 B se esperan 78 cuadros y exactamente 20 despejados. No quitar otro D.
Actualizar procedencia y documentación, ejecutar --issue57/Ruff/pytest sin
debilitar reglas y revisar el diff antes de publicar. Hoy no se integra ninguna.
La [procedencia de preparación](procedencia_recaptura_persona_issue57.json)
distingue los 84 históricos, los 78 vigentes y los 78 futuros aún no disponibles.
No sobrescribir la procedencia histórica con sesiones o hashes previstos.

## Dependencias y aviso preparado, no enviado

> Emilio: el PM solicitó recapturar S2, S3, S4 y S6 con una persona real. La
> selección anterior de 78 no es el congelado definitivo para #58. Compartiremos
> la nueva selección, sus hashes y correspondencias cuando estén verificadas;
> conserva tus anotaciones actuales y no las sobrescribas automáticamente.

El módulo de #59 se conserva en su rama. Su corrida real debe usar el nuevo COCO,
manifiesto/HASHES.sha256 congelados por commit y predicciones correspondientes,
sin reutilizar resultados sobre la selección anterior. No modificar archivos de
Emilio/Edith ni mezclar anotaciones o cuadros de ajuste. La distribución de
fuera de riesgo queda a confirmación del PM, sin asumir éxito del detector.

## Publicación posterior

No publicar esta rama ni abrir el PR definitivo mientras falten las 54 fotografías,
el consentimiento y las verificaciones de integración. Usar **Parte de #57** en
la descripción preparada; Closes #57 solo tras cumplir todos los requisitos y
confirmar la entrega a Emilio. No hacer merge sin revisión de Sebastián.
Los borradores de [descripción del PR](pr_p5_05b_recaptura.md) y
[actualización del issue](actualizacion_issue57_recaptura.md) son locales: no se
han enviado mensajes ni actualizado GitHub.
