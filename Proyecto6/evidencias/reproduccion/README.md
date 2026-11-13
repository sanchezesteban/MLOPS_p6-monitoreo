# Reproducción desde un clon limpio (hito 07 de la guía)

- **Fecha:** 2026-11-13.
- **Revisión clonada:** `8850936` (rama `p6-02-escenarios-extra`; incluye la base `6184d32`).
- **Entorno:** venv nuevo instalado **solo** con `Proyecto6/requirements.txt`; Python 3.13.18, onnxruntime 1.31.1, Linux x86_64.

## Pasos seguidos (los del README)

```bash
git clone -b p6-02-escenarios-extra https://github.com/sanchezesteban/MLOPS_p6-monitoreo.git clon
cd clon/Proyecto6
python -m venv venv && venv/bin/pip install -r requirements.txt
venv/bin/python ../Proyecto5/scripts/descargar_modelo.py --destino ../Proyecto5/modelo/   # SHA-256 coincide
venv/bin/python -m pytest -q                                                              # 30 passed
export PYTHONPATH=src
venv/bin/python -m p6.monitor --manifiesto escenarios/c1_normal.csv --escenario R-c1 --run-id repro-c1 --db var/m.db --salida var/c1
venv/bin/python -m p6.monitor --manifiesto escenarios/c2_baja_confianza.csv --escenario R-c2 --run-id repro-c2 --db var/m.db --salida var/c2
venv/bin/python -m p6.recalcular --run var/c1      # 35 comprobaciones, 0 fallidas
venv/bin/python -m p6.recalcular --run var/c2      # 57 comprobaciones, 0 fallidas
venv/bin/python scripts/comparar_corridas.py var/c1 evidencias/escenarios/c1-normal
venv/bin/python scripts/comparar_corridas.py var/c2 evidencias/escenarios/c2-baja-confianza
```

## Resultado de la comparación

Salida de `scripts/comparar_corridas.py`:

```json
{"frames": [36, 36], "estados_zonas_iguales": true, "max_abs_delta_score": 0.0, "alertas_iguales": true, "alertas": []}
{"frames": [66, 66], "estados_zonas_iguales": true, "max_abs_delta_score": 0.0, "alertas_iguales": true, "alertas": [["baja-confianza-v1", 0, 1]]}
```

La corrida nueva reproduce C1 y C2 **frame a frame**:
- mismas imágenes de origen (SHA-256);
- mismos estados y zonas;
- scores idénticos (|Δ| = 0);
- misma alerta de C2: `baja-confianza-v1`, abierta en w000 y resuelta en w001.

Los tiempos (G1–G3) cambian de una corrida a otra, como se espera.

**Límite:** el clon se hizo en el mismo tipo de equipo que las corridas originales. En otra CPU o versión de onnxruntime, los scores pueden variar del orden de 1e-6, y la tolerancia del script es 1e-4.
