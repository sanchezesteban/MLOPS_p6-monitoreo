# P5-05b: Recaptura real S2, S3, S4 y S6

Parte de #57.

**Borrador local; no abrir el PR definitivo todavía.** El PR #79 está fusionado
en main (b6317b5). Esta rama nace de ese origin/main y no altera el PR anterior.

El protocolo anterior mostraba personas/animales en un teléfono; el detector
identificaba el dispositivo como tv. Por orden del PM, se preparan 54 capturas
con persona real: S2=17, S3=13, S4=12 y S6=12 (4 libres, 4 con persona, 4 libres).
Se conservan S1=12 y S5=12 salvo nueva instrucción. La selección final esperada
es de 78 cuadros: 20 despejados y 58 con obstáculos; todavía no está capturada.

## Preparación implementada

- Archivo exacto de 84 JPEG desde 021550e y snapshot de los 78 desde bd1ff9e,
  con CSV originales, SHA-256 y procedencia; sin retirar evaluación/ajuste.
- IDs consecutivos por secuencia, como S2_f0001; reanudación sin renumerar ni
  sobrescribir registros previos. Tiempos/sesiones reales y hashes del JPEG.
- Comprobación opcional de resolución 400×296 tras rotar 180°, sin redimensionar;
  guías solo en vista previa, motores apagados y sin selección por inferencia.
- pytest.importorskip("cv2") antes de imports del capturador en test_capturas.py.
- Protocolo, constancia pendiente de consentimiento e incidencias sin datos personales.

## Requisitos antes de publicar

- [ ] Obtener exactamente las 54 capturas reales y revisar escenarios/tiempos/IDs.
- [ ] Confirmar consentimiento firmado que cubre publicación y tratamiento previsto;
  documento privado fuera de Git, solo constancia sin datos personales.
- [ ] PM: decidir los ejemplos nuevos fuera de riesgo; las cinco marcas antiguas
  de S2/S3 no se trasladan automáticamente.
- [ ] Integrar únicamente S2/S3/S4/S6; comprobar JPEG/CSV/hashes, 78 cuadros,
  mínimos por secuencia, 20 despejados, 58 obstáculos e independencia del ajuste.
- [ ] Actualizar procedencia, incidencias, conteos y validaciones sobre el conjunto nuevo.
- [ ] Entregar el conjunto congelado a Emilio para COCO/manifiesto; #59 usará
  solo las predicciones correspondientes. No modificar sus anotaciones ni el algoritmo.
- [ ] Revisar y solicitar revisión de Sebastián; no hacer merge sin aprobación.

## Validación de la preparación local

- Python 3.10.8 con OpenCV: 276 pruebas y 53 subpruebas aprobadas.
- Capturador/contrato/recaptura: 80 pruebas y 53 subpruebas aprobadas.
- Entorno virtual aislado sin OpenCV: test_capturas.py omitido con 1 skipped,
  antes de importar el capturador. Sin descargas ni sustitución de cv2 por mocks.
- Ruff check y Ruff format --check aprobados.
- --issue57 aprobado sobre los 78 JPEG anteriores y los siete de ajuste intactos.
- Archivo 84/78 verificado byte a byte contra sus commits; SHA-256, CSV, IDs,
  tiempos y correspondencia de archivos correctos. Sin hashes/IDs/sesiones
  compartidos entre evaluación y ajuste; la revisión visual previa sigue documentada.
- Python 3.12 no está disponible localmente; no se afirma haber ejecutado esa versión.

Las pruebas de preparación no acreditan capturas nuevas, independencia de escenas
futuras ni resultados reales del detector. Repetir la validación final al integrar
el conjunto nuevo; no modificar las reglas para aprobarlo.
Usar Closes #57 únicamente con todos los criterios cumplidos y entrega confirmada.
