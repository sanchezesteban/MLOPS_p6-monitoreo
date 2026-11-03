# Evidencia P5-04 (#56): detector real sobre 4 cuadros

Ejecución del detector real (YOLOX-Nano, pesos verificados por SHA-256) en CPU sobre cuatro
cuadros de la ESP32-CAM tomados del PR #79 (#57). Los archivos se copiaron con nombres neutros
(`img1.jpg`…`img4.jpg`) para que el nombre no aporte información. Se eligió por secuencia el
primer cuadro marcado como obstáculo en zona de riesgo (S2, S3, S5) y el primero despejado (S1),
sin ver antes la salida del detector. No se ajustó nada con estos resultados.

```bash
cd Proyecto5
python scripts/descargar_modelo.py --destino modelo/
PYTHONPATH=src python -m p5.detectar --imagenes <carpeta con img1..img4> --config config/detector.yaml \
    --salida <carpeta nueva> --run-id det-evidencia-p5-04
```

Salida (`exit=0`), commit `e9b964b`:

```
cli_00000  img1.jpg  ok  2 detecciones
cli_00001  img2.jpg  ok  3 detecciones
cli_00002  img3.jpg  ok  3 detecciones
cli_00003  img4.jpg  ok  0 detecciones
4 imagenes: 4 ok (1 sin objetos), 0 con error, 8 detecciones
```

| Archivo | Origen (`datos/evaluacion/` en #79) | SHA-256 de la imagen | Caso | Detecciones (clase, confianza, `xyxy` en píxeles de 400×296) |
|---|---|---|---|---|
| `img1.jpg` | `S2/S2_0000000000_S2_0b56bd58….jpg` | `efddf451…5006` | Central | `person` 0.549 [146, 191, 254, 266]; `tv` 0.515 (pantalla del teléfono) |
| `img2.jpg` | `S3/S3_0000000000_S3_96c47575….jpg` | `fb797263…ea12` | Lateral izquierdo | `person` 0.750 [29, 196, 114, 272]; `tv` 0.734; `traffic light` 0.367 (objeto en la pared: falso positivo) |
| `img3.jpg` | `S5/S5_0000000000_S5_20800b49….jpg` | `7d619ac1…2d6e` | Varios | tres `cat` 0.867 / 0.754 / 0.701, uno al lado del otro |
| `img4.jpg` | `S1/S1_0000000000_3ca02f25….jpg` | `338bc1c1…7bb4` | Negativa | ninguna: `status=ok`, `detections=[]` |

Lectura con las zonas del contrato (tercios del ancho de 400 px: 133 y 267):

- La persona de `img1` toca la zona central y está en riesgo (`y2 = 266 ≥ 148`).
- La de `img2` queda solo en la zona izquierda (`x2 = 114 < 133`).

`tv` y `traffic light` no son clases de obstáculo (`config/politica.yaml`), así que la política las ignora. Son límites conocidos del detector para documentar en #61. Los estímulos son fotos en la pantalla de un teléfono, y YOLOX también detecta la pantalla como `tv`.

Archivos: [`run.json`](run.json) (cabecera de ejecución) y [`detecciones.jsonl`](detecciones.jsonl) (eventos del contrato v1, validados con `p5.contrato.validar_evento` antes de escribirse).

Las pruebas de imagen ilegible, de varios objetos, de imagen negativa y de imagen renombrada están en `tests/test_detectar_real.py` y `tests/test_detector_onnx.py`.
