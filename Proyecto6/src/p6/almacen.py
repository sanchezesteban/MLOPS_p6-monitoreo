"""Persistencia en SQLite. Eventos, ventanas, alertas y configuraciones; sin expiracion.

No hay borrado, TTL ni limpieza automatica: los registros y las capturas permanecen hasta
que una persona los borre explicitamente.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

ESQUEMA = """
CREATE TABLE IF NOT EXISTS configs (
  config_sha256 TEXT PRIMARY KEY, config_id TEXT, texto TEXT,
  detector_config_sha256 TEXT, detector_texto TEXT
);
CREATE TABLE IF NOT EXISTS runs (
  run_id TEXT PRIMARY KEY, escenario TEXT, inicio TEXT, fin TEXT, git_commit TEXT,
  git_sucio INTEGER, config_id TEXT, config_sha256 TEXT, model_nombre TEXT,
  model_archivo TEXT, model_sha256 TEXT, detector_config_sha256 TEXT, fuente_tipo TEXT,
  source_id TEXT, manifiesto TEXT, manifiesto_sha256 TEXT, fps REAL, frames INTEGER,
  entorno_json TEXT, referencia_sha256 TEXT, referencia_estado TEXT, metricas_json TEXT
);
CREATE TABLE IF NOT EXISTS eventos (
  event_id TEXT PRIMARY KEY, run_id TEXT, seq INTEGER, frame_id TEXT, source_id TEXT,
  image_source TEXT, image_source_sha256 TEXT, t_captura TEXT, t_fin TEXT, task TEXT,
  model_nombre TEXT, model_sha256 TEXT, detector_config_sha256 TEXT, config_sha256 TEXT,
  estado TEXT, error_msg TEXT, score_principal REAL, clase_principal TEXT, zona TEXT,
  n_detecciones INTEGER, detecciones_json TEXT, image_ref TEXT, image_sha256 TEXT,
  captura_motivo TEXT, window_id TEXT, synthetic INTEGER, lectura_ms REAL, pre_ms REAL,
  inferencia_ms REAL, post_ms REAL, t_captura_mono REAL, t_fin_mono REAL
);
CREATE TABLE IF NOT EXISTS ventanas (
  window_id TEXT PRIMARY KEY, run_id TEXT, seq INTEGER, frame_desde TEXT, frame_hasta TEXT,
  frames INTEGER, puntuados INTEGER, bajos INTEGER, sin_detecciones INTEGER,
  errores INTEGER, suficiente INTEGER, proporcion_baja REAL, inferencia_p50_ms REAL,
  inferencia_p95_ms REAL, fps_procesamiento REAL, rss_mib REAL, cpu_pct REAL,
  alertas_activas INTEGER, t_cierre TEXT, decisiones_json TEXT, config_sha256 TEXT
);
CREATE TABLE IF NOT EXISTS alertas (
  alert_id TEXT PRIMARY KEY, run_id TEXT, rule_id TEXT, regla TEXT, severidad TEXT,
  estado TEXT, t_apertura TEXT, t_actualizacion TEXT, t_resolucion TEXT,
  abierta_ventana INTEGER, resuelta_ventana INTEGER, motivo TEXT, motivo_ultimo TEXT,
  accion_sugerida TEXT, config_sha256 TEXT, ventanas_json TEXT, evidencia_image_ref TEXT
);
CREATE TABLE IF NOT EXISTS alerta_eventos (
  alert_id TEXT, event_id TEXT, PRIMARY KEY (alert_id, event_id)
);
CREATE INDEX IF NOT EXISTS ix_eventos_run ON eventos(run_id, seq);
CREATE INDEX IF NOT EXISTS ix_alertas_run ON alertas(run_id);
"""


def conectar(ruta: Path) -> sqlite3.Connection:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(ruta)
    con.row_factory = sqlite3.Row
    con.executescript(ESQUEMA)
    return con


def insertar(
    con: sqlite3.Connection, tabla: str, fila: dict[str, Any], reemplazar: bool = False
) -> None:
    cols = ", ".join(fila)
    marcas = ", ".join("?" for _ in fila)
    verbo = "INSERT OR REPLACE" if reemplazar else "INSERT"
    con.execute(f"{verbo} INTO {tabla} ({cols}) VALUES ({marcas})", tuple(fila.values()))


def filas(con: sqlite3.Connection, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    return [dict(r) for r in con.execute(sql, params).fetchall()]


def exportar_run(con: sqlite3.Connection, run_id: str, destino: Path) -> None:
    """Exporta el run a JSONL/JSON recalculables (evidencia primaria fuera de la base)."""
    destino.mkdir(parents=True, exist_ok=True)
    run = filas(con, "SELECT * FROM runs WHERE run_id=?", (run_id,))[0]
    run["entorno"] = json.loads(run.pop("entorno_json") or "{}")
    run["metricas"] = json.loads(run.pop("metricas_json") or "{}")
    (destino / "run.json").write_text(
        json.dumps(run, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    consultas = {
        "eventos.jsonl": "SELECT * FROM eventos WHERE run_id=? ORDER BY seq",
        "ventanas.jsonl": "SELECT * FROM ventanas WHERE run_id=? ORDER BY seq",
        "alertas.jsonl": "SELECT * FROM alertas WHERE run_id=? ORDER BY alert_id",
    }
    for nombre, sql in consultas.items():
        with (destino / nombre).open("w", encoding="utf-8") as f:
            for fila in filas(con, sql, (run_id,)):
                for k in [k for k in fila if k.endswith("_json")]:
                    fila[k.removesuffix("_json")] = json.loads(fila.pop(k) or "null")
                if nombre == "alertas.jsonl":
                    fila["event_ids"] = [
                        r["event_id"]
                        for r in filas(
                            con,
                            "SELECT event_id FROM alerta_eventos WHERE alert_id=? "
                            "ORDER BY event_id",
                            (fila["alert_id"],),
                        )
                    ]
                f.write(json.dumps(fila, ensure_ascii=False) + "\n")
