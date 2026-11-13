"""Portal de monitoreo: consulta de eventos y alertas (FastAPI + Jinja2, lee la base SQLite).

    PYTHONPATH=src python -m p6.portal --db evidencias/monitoreo.db   # http://127.0.0.1:8060

Vistas: /eventos, /eventos/{id}, /alertas, /alertas/{id}, /ventanas, /config/{sha} y /runs.
Cada evento enlaza su captura, ventana, configuracion y alertas; cada alerta enlaza su regla,
configuracion, ventanas y los eventos que la originaron. Solo lectura.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from p6 import RAIZ_P6

PLANTILLAS = Path(__file__).parent / "templates"
CARPETAS_PERMITIDAS = ("evidencias", "var", "datos")


def _q(con: sqlite3.Connection, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    return [dict(r) for r in con.execute(sql, params).fetchall()]


def crear_app(db: Path, raiz: Path = RAIZ_P6) -> FastAPI:
    app = FastAPI(title="P6 · Centro de monitoreo CV")
    tpl = Jinja2Templates(directory=str(PLANTILLAS))
    tpl.env.filters["fmt"] = lambda v, n=3: "—" if v is None else f"{v:.{n}f}"

    def con() -> sqlite3.Connection:
        if not db.is_file():
            raise HTTPException(503, f"No existe la base {db}; ejecuta p6.monitor primero")
        c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        c.row_factory = sqlite3.Row
        return c

    def runs(c: sqlite3.Connection) -> list[dict[str, Any]]:
        return _q(c, "SELECT run_id, escenario, inicio FROM runs ORDER BY inicio")

    def render(request: Request, nombre: str, **ctx: Any) -> HTMLResponse:
        return tpl.TemplateResponse(request, nombre, ctx)

    @app.get("/", include_in_schema=False)
    def inicio() -> RedirectResponse:
        return RedirectResponse("/runs")

    @app.get("/runs", response_class=HTMLResponse)
    def ver_runs(request: Request) -> HTMLResponse:
        with con() as c:
            filas = _q(c, "SELECT * FROM runs ORDER BY inicio")
            for f in filas:
                f["metricas"] = json.loads(f.pop("metricas_json") or "{}")
                f["entorno"] = json.loads(f.pop("entorno_json") or "{}")
                f["n_alertas"] = c.execute(
                    "SELECT COUNT(*) FROM alertas WHERE run_id=?", (f["run_id"],)
                ).fetchone()[0]
        return render(request, "runs.html", runs=filas)

    def filtrar_eventos(c, run, zona, estado, limite) -> list[dict[str, Any]]:
        sql, p = "SELECT * FROM eventos WHERE 1=1", []
        if run:
            sql += " AND run_id=?"
            p.append(run)
        if zona:
            sql += " AND zona=?"
            p.append(zona)
        if estado:
            sql += " AND estado=?"
            p.append(estado)
        sql += " ORDER BY run_id, seq LIMIT ?"
        p.append(limite)
        return _q(c, sql, tuple(p))

    @app.get("/eventos", response_class=HTMLResponse)
    def ver_eventos(
        request: Request,
        run: str | None = None,
        zona: str | None = None,
        estado: str | None = None,
        limite: int = Query(500, ge=1, le=5000),
    ) -> HTMLResponse:
        with con() as c:
            evs = filtrar_eventos(c, run, zona, estado, limite)
            alertas_por_evento: dict[str, list[str]] = {}
            for r in _q(c, "SELECT * FROM alerta_eventos"):
                alertas_por_evento.setdefault(r["event_id"], []).append(r["alert_id"])
            return render(
                request,
                "eventos.html",
                eventos=evs,
                runs=runs(c),
                f={"run": run, "zona": zona, "estado": estado},
                alertas_por_evento=alertas_por_evento,
            )

    @app.get("/eventos/{event_id}", response_class=HTMLResponse)
    def ver_evento(request: Request, event_id: str) -> HTMLResponse:
        with con() as c:
            e = _q(c, "SELECT * FROM eventos WHERE event_id=?", (event_id,))
            if not e:
                raise HTTPException(404, f"evento {event_id} no existe")
            e = e[0]
            e["detecciones"] = json.loads(e.pop("detecciones_json") or "[]")
            al = _q(
                c,
                "SELECT a.* FROM alertas a JOIN alerta_eventos ae "
                "ON a.alert_id=ae.alert_id WHERE ae.event_id=?",
                (event_id,),
            )
            v = _q(c, "SELECT * FROM ventanas WHERE window_id=?", (e["window_id"],))
            run = _q(c, "SELECT * FROM runs WHERE run_id=?", (e["run_id"],))
            cfg = _q(
                c, "SELECT config_id FROM configs WHERE config_sha256=?", (e["config_sha256"],)
            )
        return render(
            request,
            "evento.html",
            e=e,
            alertas=al,
            ventana=v[0] if v else None,
            run=run[0] if run else None,
            config=cfg[0] if cfg else None,
        )

    @app.get("/alertas", response_class=HTMLResponse)
    def ver_alertas(
        request: Request,
        run: str | None = None,
        estado: str | None = None,
        severidad: str | None = None,
    ) -> HTMLResponse:
        sql, p = "SELECT * FROM alertas WHERE 1=1", []
        for col, val in (("run_id", run), ("estado", estado), ("severidad", severidad)):
            if val:
                sql += f" AND {col}=?"
                p.append(val)
        with con() as c:
            al = _q(c, sql + " ORDER BY t_apertura", tuple(p))
            for a in al:
                a["n_eventos"] = c.execute(
                    "SELECT COUNT(*) FROM alerta_eventos WHERE alert_id=?", (a["alert_id"],)
                ).fetchone()[0]
            return render(
                request,
                "alertas.html",
                alertas=al,
                runs=runs(c),
                f={"run": run, "estado": estado, "severidad": severidad},
            )

    @app.get("/alertas/{alert_id}", response_class=HTMLResponse)
    def ver_alerta(request: Request, alert_id: str) -> HTMLResponse:
        with con() as c:
            a = _q(c, "SELECT * FROM alertas WHERE alert_id=?", (alert_id,))
            if not a:
                raise HTTPException(404, f"alerta {alert_id} no existe")
            a = a[0]
            a["ventanas"] = json.loads(a.pop("ventanas_json") or "[]")
            evs = _q(
                c,
                "SELECT e.* FROM eventos e JOIN alerta_eventos ae "
                "ON e.event_id=ae.event_id WHERE ae.alert_id=? ORDER BY e.seq",
                (alert_id,),
            )
            seqs = [w["seq"] for w in a["ventanas"]]
            ves = [
                v
                for v in _q(c, "SELECT * FROM ventanas WHERE run_id=? ORDER BY seq", (a["run_id"],))
                if v["seq"] in seqs
            ]
        return render(request, "alerta.html", a=a, eventos=evs, ventanas=ves)

    @app.get("/ventanas", response_class=HTMLResponse)
    def ver_ventanas(request: Request, run: str | None = None) -> HTMLResponse:
        with con() as c:
            sql = "SELECT * FROM ventanas" + (" WHERE run_id=?" if run else "")
            vs = _q(c, sql + " ORDER BY run_id, seq", (run,) if run else ())
            for v in vs:
                v["decisiones"] = json.loads(v.pop("decisiones_json") or "[]")
            return render(request, "ventanas.html", ventanas=vs, runs=runs(c), f={"run": run})

    @app.get("/config/{sha}", response_class=HTMLResponse)
    def ver_config(request: Request, sha: str) -> HTMLResponse:
        with con() as c:
            cfg = _q(c, "SELECT * FROM configs WHERE config_sha256=?", (sha,))
        if not cfg:
            raise HTTPException(404, f"configuracion {sha} no existe")
        return render(request, "config.html", cfg=cfg[0])

    @app.get("/archivo/{ruta:path}", include_in_schema=False)
    def archivo(ruta: str) -> FileResponse:
        destino = (raiz / ruta).resolve()
        permitido = any(destino.is_relative_to((raiz / d).resolve()) for d in CARPETAS_PERMITIDAS)
        if not permitido or not destino.is_file():
            raise HTTPException(404, "archivo no disponible")
        return FileResponse(destino)

    @app.get("/api/eventos")
    def api_eventos(
        run: str | None = None,
        zona: str | None = None,
        estado: str | None = None,
        limite: int = Query(500, ge=1, le=5000),
    ):
        with con() as c:
            return filtrar_eventos(c, run, zona, estado, limite)

    @app.get("/api/alertas")
    def api_alertas(run: str | None = None):
        with con() as c:
            sql = "SELECT * FROM alertas" + (" WHERE run_id=?" if run else "")
            return _q(c, sql + " ORDER BY t_apertura", (run,) if run else ())

    return app
