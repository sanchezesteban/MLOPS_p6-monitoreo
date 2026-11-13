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

import yaml
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from p6 import RAIZ_P6, extras
from p6.portal import graficas

ZONAS = ("aceptada", "duda", "baja")
ESTADOS = ("ok", "sin_detecciones", "error")
COLUMNAS_CSV = (
    "event_id",
    "run_id",
    "seq",
    "frame_id",
    "source_id",
    "t_captura",
    "t_fin",
    "estado",
    "error_msg",
    "score_principal",
    "clase_principal",
    "zona",
    "n_detecciones",
    "window_id",
    "model_sha256",
    "config_sha256",
    "image_source",
    "image_source_sha256",
    "image_ref",
    "image_sha256",
    "captura_motivo",
    "inferencia_ms",
)


def _validar(valor: str | None, permitidos: tuple[str, ...], nombre: str) -> str | None:
    """'' o None = sin filtro; un valor fuera del catalogo es un error explicito (400)."""
    if not valor:
        return None
    if valor not in permitidos:
        raise HTTPException(400, f"{nombre} invalido: {valor!r}; usa uno de {list(permitidos)}")
    return valor


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

    @app.exception_handler(HTTPException)
    async def error_http(request: Request, exc: HTTPException) -> Response:
        """Paginas HTML muestran el error en el portal; /api y CSV responden JSON."""
        ruta = request.url.path
        if ruta.startswith(("/api/", "/exportar/", "/archivo/")):
            return Response(
                json.dumps({"detail": exc.detail}),
                status_code=exc.status_code,
                media_type="application/json",
            )
        return tpl.TemplateResponse(
            request,
            "error.html",
            {"codigo": exc.status_code, "detalle": exc.detail},
            status_code=exc.status_code,
        )

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
        zona = _validar(zona, ZONAS, "zona")
        estado = _validar(estado, ESTADOS, "estado")
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

    def cargar_run(c: sqlite3.Connection, run: str) -> dict[str, Any]:
        r = _q(c, "SELECT * FROM runs WHERE run_id=?", (run,))
        if not r:
            raise HTTPException(404, f"la corrida {run!r} no existe")
        r = r[0]
        evs = _q(c, "SELECT * FROM eventos WHERE run_id=? ORDER BY seq", (run,))
        for e in evs:
            e["detecciones"] = json.loads(e.pop("detecciones_json") or "[]")
        ves = _q(c, "SELECT * FROM ventanas WHERE run_id=? ORDER BY seq", (run,))
        als = _q(c, "SELECT * FROM alertas WHERE run_id=? ORDER BY t_apertura", (run,))
        for a in als:
            a["event_ids"] = [
                x["event_id"]
                for x in _q(
                    c, "SELECT event_id FROM alerta_eventos WHERE alert_id=?", (a["alert_id"],)
                )
            ]
        cfg = _q(c, "SELECT texto FROM configs WHERE config_sha256=?", (r["config_sha256"],))
        r["config"] = yaml.safe_load(cfg[0]["texto"]) if cfg else {}
        return {"run": r, "eventos": evs, "ventanas": ves, "alertas": als}

    @app.get("/graficas", response_class=HTMLResponse)
    def ver_graficas(request: Request, run: str | None = None) -> HTMLResponse:
        with con() as c:
            lista = runs(c)
            if not run:
                return render(request, "graficas.html", runs=lista, f={"run": None}, d=None)
            d = cargar_run(c, run)
        cfg = d["run"]["config"]
        pol = cfg.get("politica", {})
        ref = extras.calcular_desde(d["run"], d["eventos"], d["ventanas"], d["alertas"])
        ref_json = RAIZ_P6 / "evidencias/referencia/referencia.json"
        p_ref = json.loads(ref_json.read_text())["proporcion_baja"] if ref_json.is_file() else None
        puntuados = sum(e["estado"] == "ok" for e in d["eventos"])
        d["svg_scores"] = graficas.svg_scores(
            d["eventos"],
            d["alertas"],
            pol.get("umbral_inferior", 0),
            pol.get("umbral_superior", 1),
            cfg.get("ventanas", {}).get("tamano_frames", 10),
        )
        d["svg_ventanas"] = graficas.svg_ventanas(
            d["ventanas"],
            p_ref,
            cfg.get("reglas", {}).get("baja_confianza", {}).get("proporcion_minima", 0.5),
        )
        return render(
            request,
            "graficas.html",
            runs=lista,
            f={"run": run},
            d=d,
            extra=ref,
            puntuados=puntuados,
        )

    @app.get("/capturas", response_class=HTMLResponse)
    def ver_capturas(
        request: Request,
        run: str | None = None,
        zona: str | None = None,
        estado: str | None = None,
        limite: int = Query(200, ge=1, le=2000),
    ) -> HTMLResponse:
        zona = _validar(zona, ZONAS, "zona")
        estado = _validar(estado, ESTADOS, "estado")
        sql, p = "SELECT * FROM eventos WHERE image_ref IS NOT NULL", []
        for col, val in (("run_id", run), ("zona", zona), ("estado", estado)):
            if val:
                sql += f" AND {col}=?"
                p.append(val)
        with con() as c:
            caps = _q(c, sql + " ORDER BY run_id, seq LIMIT ?", (*p, limite))
            alertas_por_evento: dict[str, list[str]] = {}
            for r in _q(c, "SELECT * FROM alerta_eventos"):
                alertas_por_evento.setdefault(r["event_id"], []).append(r["alert_id"])
            for e in caps:
                e["existe"] = (raiz / e["image_ref"]).is_file()
            return render(
                request,
                "capturas.html",
                capturas=caps,
                runs=runs(c),
                f={"run": run, "zona": zona, "estado": estado},
                alertas_por_evento=alertas_por_evento,
            )

    @app.get("/exportar/eventos.csv")
    def exportar_csv(
        run: str | None = None,
        zona: str | None = None,
        estado: str | None = None,
        limite: int = Query(5000, ge=1, le=5000),
    ) -> Response:
        import csv
        import io

        with con() as c:
            if run and not _q(c, "SELECT 1 FROM runs WHERE run_id=?", (run,)):
                raise HTTPException(404, f"la corrida {run!r} no existe")
            evs = filtrar_eventos(c, run, zona, estado, limite)
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=COLUMNAS_CSV, extrasaction="ignore", lineterminator="\n")
        w.writeheader()
        w.writerows(evs)
        nombre = "eventos" + "".join(f"_{v}" for v in (run, zona, estado) if v) + ".csv"
        return Response(
            buf.getvalue(),
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="{nombre}"',
                "X-Filas": str(len(evs)),
            },
        )

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
