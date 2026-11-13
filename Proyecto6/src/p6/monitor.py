"""Monitor: fuente -> inferencia real -> evento + captura -> ventana -> reglas -> alertas.

Uso (desde Proyecto6/, con el modelo descargado):

    PYTHONPATH=src python -m p6.monitor --config config/monitoreo.yaml \
        --manifiesto escenarios/c1_normal.csv --escenario C1 --run-id c1-normal \
        --db evidencias/monitoreo.db --salida evidencias/escenarios/c1-normal

Escribe en la base SQLite (que lee el portal), copia las capturas seleccionadas a
`evidencias/capturas/<run_id>/` y exporta el run a JSONL en `--salida`.
"""

from __future__ import annotations

import argparse
import json
import platform
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import psutil

from p6 import RAIZ_P6, RAIZ_REPO, almacen, metricas, politica
from p6.config import ConfigMonitoreo, cargar, cargar_referencia
from p6.detector import Detector, DetectorError
from p6.fuente import Frame, SecuenciaFuente, ahora_iso, sha256_archivo
from p6.reglas import Decision, MotorReglas, Ventana, referencia_compatible


def git_estado() -> tuple[str | None, bool]:
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=RAIZ_REPO, check=True, capture_output=True, text=True
        ).stdout.strip()
        sucio = bool(
            subprocess.run(
                ["git", "status", "--porcelain", "--", "Proyecto6/src", "Proyecto6/config"],
                cwd=RAIZ_REPO,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        )
        return commit, sucio
    except (OSError, subprocess.CalledProcessError):
        return None, True


def rel_p6(ruta: Path) -> str:
    """Ruta relativa a Proyecto6/ (portable); absoluta si queda fuera."""
    ruta = ruta.resolve()
    return ruta.relative_to(RAIZ_P6).as_posix() if ruta.is_relative_to(RAIZ_P6) else ruta.as_posix()


@dataclass
class EstadoAlerta:
    alert_id: str
    ventanas: list[dict[str, Any]] = field(default_factory=list)


class Monitor:
    def __init__(
        self, cfg: ConfigMonitoreo, detector: Detector, con, run_id: str, dir_capturas: Path
    ) -> None:
        self.cfg = cfg
        self.det = detector
        self.con = con
        self.run_id = run_id
        self.dir_capturas = dir_capturas
        self.referencia = cargar_referencia(cfg.referencia)
        ok, self.referencia_estado = referencia_compatible(
            self.referencia, cfg, detector.model_sha256, detector.detector_config_sha256
        )
        self.motor = MotorReglas(cfg, self.referencia, ok)
        self.eventos: list[dict[str, Any]] = []
        self.ventanas: list[dict[str, Any]] = []
        self.alertas: dict[str, dict[str, Any]] = {}
        self.activas: dict[str, EstadoAlerta] = {}
        self._buffer: list[dict[str, Any]] = []
        self._todas: dict[int, tuple[list[str], list[str]]] = {}
        self._muestra = {"aceptada": 0, "duda": 0, "baja": 0, "sin_detecciones": 0, "error": 0}
        self._proceso = psutil.Process()
        self._proceso.cpu_percent(None)

    # ---- frame a evento -------------------------------------------------------------
    def procesar(self, frame: Frame) -> dict[str, Any]:
        cfg = self.cfg
        ev: dict[str, Any] = {
            "event_id": f"{self.run_id}-e{frame.indice:05d}",
            "run_id": self.run_id,
            "seq": frame.indice,
            "frame_id": frame.frame_id,
            "source_id": frame.source_id,
            "image_source": frame.ruta_rel,
            "image_source_sha256": None,
            "t_captura": frame.t_captura,
            "task": "detection",
            "model_nombre": self.det.nombre,
            "model_sha256": self.det.model_sha256,
            "detector_config_sha256": self.det.detector_config_sha256,
            "config_sha256": cfg.config_sha256,
            "estado": None,
            "error_msg": None,
            "score_principal": None,
            "clase_principal": None,
            "zona": None,
            "n_detecciones": 0,
            "detecciones_json": "[]",
            "image_ref": None,
            "image_sha256": None,
            "captura_motivo": None,
            "window_id": f"{self.run_id}-w{frame.indice // cfg.tamano_ventana:03d}",
            "synthetic": 0,
            "lectura_ms": None,
            "pre_ms": None,
            "inferencia_ms": None,
            "post_ms": None,
            "t_captura_mono": frame.t_captura_mono,
        }
        try:
            if not frame.ruta.is_file():
                raise DetectorError("imagen ausente")
            ev["image_source_sha256"] = sha256_archivo(frame.ruta)
            if frame.sha256_declarado and frame.sha256_declarado != ev["image_source_sha256"]:
                raise DetectorError("entrada invalida: SHA-256 distinto al del manifiesto")
            r = self.det.inferir(frame.ruta)
            ev.update(
                lectura_ms=r.lectura_ms,
                pre_ms=r.pre_ms,
                inferencia_ms=r.inferencia_ms,
                post_ms=r.post_ms,
            )
            scores = [d.confidence for d in r.detecciones]
            estado, s, z = politica.clasificar_frame(
                scores, cfg.umbral_inferior, cfg.umbral_superior
            )
            dets = [
                {
                    "class_id": d.class_id,
                    "class_name": d.class_name,
                    "score": round(d.confidence, 6),
                    "bbox_xyxy": list(d.bbox),
                    "zona": politica.zona(d.confidence, cfg.umbral_inferior, cfg.umbral_superior),
                }
                for d in r.detecciones
            ]
            ev.update(
                estado=estado,
                score_principal=s,
                zona=z,
                n_detecciones=len(dets),
                detecciones_json=json.dumps(dets),
                clase_principal=dets[0]["class_name"] if dets else None,
            )
        except DetectorError as exc:
            ev.update(estado=politica.ERROR, error_msg=str(exc))
        ev["t_fin"] = ahora_iso()
        ev["t_fin_mono"] = time.perf_counter()
        self._capturar(ev, frame)
        almacen.insertar(self.con, "eventos", ev)
        self.eventos.append(ev)
        self._buffer.append(ev)
        if len(self._buffer) == cfg.tamano_ventana:
            self.cerrar_ventana()
        return ev

    def _capturar(self, ev: dict[str, Any], frame: Frame) -> None:
        """Politica de captura: zonas/estados configurados siempre; el resto, 1 de cada N."""
        clave = ev["zona"] or ev["estado"]
        motivo = None
        if ev["zona"] in self.cfg.captura_zonas:
            motivo = f"zona {ev['zona']}"
        elif ev["estado"] in self.cfg.captura_estados:
            motivo = f"estado {ev['estado']}"
        else:
            if self._muestra[clave] % self.cfg.captura_muestra_cada == 0:
                motivo = f"muestra 1/{self.cfg.captura_muestra_cada} de {clave}"
            self._muestra[clave] += 1
        if motivo is None or not frame.ruta.is_file():
            return
        destino = self.dir_capturas / self.run_id / f"{frame.frame_id}{frame.ruta.suffix.lower()}"
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(frame.ruta, destino)
        ev.update(
            image_ref=rel_p6(destino), image_sha256=sha256_archivo(destino), captura_motivo=motivo
        )

    # ---- ventana y reglas ----------------------------------------------------------
    def cerrar_ventana(self) -> None:
        if not self._buffer:
            return
        evs, self._buffer = self._buffer, []
        seq = len(self.ventanas)
        g4 = metricas.g4_baja(evs)
        g1 = metricas.g1_inferencia(evs)
        g2 = metricas.g2_fps_procesamiento(evs)
        v = Ventana(
            seq=seq,
            window_id=f"{self.run_id}-w{seq:03d}",
            frames=len(evs),
            puntuados=g4["puntuados"],
            bajos=g4["bajos"],
            suficiente=g4["puntuados"] >= self.cfg.minimo_puntuados,
            proporcion_baja=g4["proporcion"],
            event_ids_bajos=[e["event_id"] for e in evs if e["zona"] == "baja"],
        )
        decisiones = self.motor.evaluar(v)
        t = ahora_iso()
        self._todas[seq] = ([e["event_id"] for e in evs], v.event_ids_bajos)
        for d in decisiones:
            self._ciclo_alerta(d, seq, t)
        fila = {
            "window_id": v.window_id,
            "run_id": self.run_id,
            "seq": seq,
            "frame_desde": evs[0]["frame_id"],
            "frame_hasta": evs[-1]["frame_id"],
            "frames": len(evs),
            "puntuados": v.puntuados,
            "bajos": v.bajos,
            "sin_detecciones": sum(e["estado"] == "sin_detecciones" for e in evs),
            "errores": sum(e["estado"] == "error" for e in evs),
            "suficiente": int(v.suficiente),
            "proporcion_baja": v.proporcion_baja,
            "inferencia_p50_ms": g1["p50_ms"],
            "inferencia_p95_ms": g1["p95_ms"],
            "fps_procesamiento": g2["fps"],
            "rss_mib": self._proceso.memory_info().rss / 2**20,
            "cpu_pct": self._proceso.cpu_percent(None),
            "alertas_activas": len(self.activas),
            "t_cierre": t,
            "decisiones_json": json.dumps([d.__dict__ for d in decisiones], default=list),
            "config_sha256": self.cfg.config_sha256,
        }
        almacen.insertar(self.con, "ventanas", fila)
        self.ventanas.append(fila)
        self.con.commit()

    def _ciclo_alerta(self, d: Decision, seq: int, t: str) -> None:
        regla = self.cfg.reglas[d.regla]
        activa = self.activas.get(d.regla)
        if d.condicion is True:
            ids: list[str] = []
            for w in d.ventanas or (seq,):
                todos, bajos = self._todas[w]
                ids += todos if d.regla == "evidencia_insuficiente" else bajos
            if activa is None:
                alert_id = f"{self.run_id}-a{len(self.alertas) + 1:03d}"
                activa = self.activas[d.regla] = EstadoAlerta(alert_id)
                self.alertas[alert_id] = {
                    "alert_id": alert_id,
                    "run_id": self.run_id,
                    "rule_id": regla.id,
                    "regla": d.regla,
                    "severidad": regla.severidad,
                    "estado": "activa",
                    "t_apertura": t,
                    "t_actualizacion": t,
                    "t_resolucion": None,
                    "abierta_ventana": seq,
                    "resuelta_ventana": None,
                    "motivo": d.motivo,
                    "motivo_ultimo": d.motivo,
                    "accion_sugerida": regla.accion_sugerida,
                    "config_sha256": self.cfg.config_sha256,
                    "ventanas_json": "[]",
                    "evidencia_image_ref": None,
                }
            a = self.alertas[activa.alert_id]
            activa.ventanas.append({"seq": seq, "motivo": d.motivo})
            a.update(
                t_actualizacion=t, motivo_ultimo=d.motivo, ventanas_json=json.dumps(activa.ventanas)
            )
            refs = {e["event_id"]: e.get("image_ref") for e in self.eventos}
            for eid in ids:
                self.con.execute(
                    "INSERT OR IGNORE INTO alerta_eventos VALUES (?, ?)", (activa.alert_id, eid)
                )
                if a["evidencia_image_ref"] is None and refs.get(eid):
                    a["evidencia_image_ref"] = refs[eid]
            almacen.insertar(self.con, "alertas", a, reemplazar=True)
        elif d.condicion is False and activa is not None:
            a = self.alertas[activa.alert_id]
            a.update(
                estado="resuelta",
                t_resolucion=t,
                resuelta_ventana=seq,
                motivo_ultimo=f"resuelta: {d.motivo}",
            )
            almacen.insertar(self.con, "alertas", a, reemplazar=True)
            del self.activas[d.regla]

    # ---- metricas del run ----------------------------------------------------------
    def metricas_run(self) -> dict[str, Any]:
        traz = []
        for e in self.eventos:
            ok = None
            if e["image_ref"]:
                p = RAIZ_P6 / e["image_ref"]
                ok = p.is_file() and sha256_archivo(p) == e["image_sha256"]
            traz.append(metricas.evento_trazable(e, ok))
        al = list(self.alertas.values())
        return {
            "G1_tiempo_inferencia": metricas.g1_inferencia(self.eventos),
            "G2_fps_procesamiento": metricas.g2_fps_procesamiento(self.eventos),
            "G3_rss_proceso": metricas.g3_rss([v["rss_mib"] for v in self.ventanas]),
            "G4_proporcion_baja": metricas.g4_baja(self.eventos),
            "G5_cobertura_trazabilidad": metricas.g5_trazabilidad(traz),
            "G6_version_esperada": metricas.g6_version(self.eventos, self.det.model_sha256),
            "G7_alertas_activas": {
                "al_final": metricas.g7_activas(al, len(self.ventanas) - 1),
                "por_ventana": [v["alertas_activas"] for v in self.ventanas],
                "total_abiertas": len(al),
            },
            "estados": {
                k: sum(e["estado"] == k for e in self.eventos)
                for k in ("ok", "sin_detecciones", "error")
            },
            "zonas": {
                k: sum(e["zona"] == k for e in self.eventos) for k in ("aceptada", "duda", "baja")
            },
            "ventanas": {
                "total": len(self.ventanas),
                "suficientes": sum(v["suficiente"] for v in self.ventanas),
            },
        }


def entorno(det: Detector) -> dict[str, Any]:
    import onnxruntime

    return {
        "python": sys.version.split()[0],
        "plataforma": platform.platform(),
        "procesador": platform.machine(),
        "onnxruntime": onnxruntime.__version__,
        "proveedor": "CPUExecutionProvider",
        "cpus": psutil.cpu_count(),
    }


def ejecutar(args: argparse.Namespace) -> dict[str, Any]:
    cfg = cargar(args.config)
    det = Detector(cfg.detector_config)
    con = almacen.conectar(Path(args.db))
    if almacen.filas(con, "SELECT 1 FROM runs WHERE run_id=?", (args.run_id,)):
        raise SystemExit(f"run_id {args.run_id} ya existe en {args.db}; usa otro")
    almacen.insertar(
        con,
        "configs",
        {
            "config_sha256": cfg.config_sha256,
            "config_id": cfg.config_id,
            "texto": cfg.texto,
            "detector_config_sha256": det.detector_config_sha256,
            "detector_texto": cfg.detector_config.read_text(encoding="utf-8"),
        },
        reemplazar=True,
    )
    manifiesto = Path(args.manifiesto).resolve()
    fuente = SecuenciaFuente(manifiesto, RAIZ_REPO, args.source_id, cfg.fps)
    mon = Monitor(cfg, det, con, args.run_id, Path(args.capturas).resolve())
    commit, sucio = git_estado()
    inicio = ahora_iso()
    for frame in fuente.frames():
        mon.procesar(frame)
    mon.cerrar_ventana()
    m = mon.metricas_run()
    ref_sha = (
        sha256_archivo(cfg.referencia) if cfg.referencia and cfg.referencia.is_file() else None
    )
    almacen.insertar(
        con,
        "runs",
        {
            "run_id": args.run_id,
            "escenario": args.escenario,
            "inicio": inicio,
            "fin": ahora_iso(),
            "git_commit": commit,
            "git_sucio": int(sucio),
            "config_id": cfg.config_id,
            "config_sha256": cfg.config_sha256,
            "model_nombre": det.nombre,
            "model_archivo": det.modelo_archivo,
            "model_sha256": det.model_sha256,
            "detector_config_sha256": det.detector_config_sha256,
            "fuente_tipo": fuente.tipo,
            "source_id": args.source_id,
            "manifiesto": rel_p6(manifiesto),
            "manifiesto_sha256": sha256_archivo(manifiesto),
            "fps": cfg.fps,
            "frames": len(fuente),
            "entorno_json": json.dumps(entorno(det)),
            "referencia_sha256": ref_sha,
            "referencia_estado": mon.referencia_estado,
            "metricas_json": json.dumps(m),
        },
    )
    con.commit()
    if args.salida:
        almacen.exportar_run(con, args.run_id, Path(args.salida))
    con.close()
    return m


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--config", default=str(RAIZ_P6 / "config/monitoreo.yaml"))
    p.add_argument("--manifiesto", required=True, help="CSV con columnas path,sha256")
    p.add_argument("--escenario", required=True, help="etiqueta: REF, C1, C2, ...")
    p.add_argument("--run-id", required=True)
    p.add_argument("--source-id", default="carrito-p5-esp32cam")
    p.add_argument("--db", default=str(RAIZ_P6 / "var/monitoreo.db"))
    p.add_argument("--capturas", default=str(RAIZ_P6 / "var/capturas"))
    p.add_argument("--salida", help="carpeta para exportar run.json y JSONL")
    m = ejecutar(p.parse_args(argv))
    print(json.dumps(m, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
