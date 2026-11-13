"""Graficas historicas en SVG generadas en el servidor (sin JavaScript ni librerias externas).

1. Score principal por frame con los dos umbrales, zonas coloreadas, frames sin detecciones
   y errores marcados aparte (sin score), limites de ventana y apertura/resolucion de alertas.
2. Proporcion de frames bajos por ventana frente a la referencia y a la condicion de la
   regla; las ventanas insuficientes se dibujan como "sin evidencia", no como cero.
"""

from __future__ import annotations

from html import escape
from typing import Any

COLOR = {"aceptada": "#11703a", "duda": "#c98a00", "baja": "#b3261e"}
ANCHO, ALTO, M = 1100, 320, 46
MD = 96  # margen derecho para las etiquetas de umbrales


def _x(i: int, n: int) -> float:
    return M + (ANCHO - M - MD) * (i + 0.5) / max(n, 1)


def _y(v: float) -> float:
    return ALTO - M - (ALTO - 2 * M) * v


def svg_scores(
    eventos: list[dict[str, Any]],
    alertas: list[dict[str, Any]],
    inferior: float,
    superior: float,
    tam_ventana: int,
) -> str:
    n = len(eventos)
    p = [
        f'<svg viewBox="0 0 {ANCHO} {ALTO}" role="img" aria-label="Score principal por frame" '
        f'style="width:100%;max-width:{ANCHO}px;background:#fff;border:1px solid #dde">'
    ]
    for v in (0, 0.25, 0.5, 0.75, 1):
        p.append(
            f'<line x1="{M}" x2="{ANCHO - MD}" y1="{_y(v)}" y2="{_y(v)}" stroke="#eee"/>'
            f'<text x="{M - 6}" y="{_y(v) + 4}" font-size="11" text-anchor="end">{v}</text>'
        )
    for i in range(0, n, tam_ventana):
        x = _x(i, n) - (ANCHO - M - MD) / max(n, 1) / 2
        p.append(
            f'<line x1="{x}" x2="{x}" y1="{M}" y2="{ALTO - M}" stroke="#ccd" '
            'stroke-dasharray="2 3"/>'
        )
    for v, nombre, color in ((superior, "superior", "#11703a"), (inferior, "inferior", "#b3261e")):
        p.append(
            f'<line x1="{M}" x2="{ANCHO - MD}" y1="{_y(v)}" y2="{_y(v)}" stroke="{color}" '
            f'stroke-dasharray="6 4"/><text x="{ANCHO - MD + 4}" y="{_y(v) + 4}" '
            f'font-size="11" fill="{color}">{nombre} {v}</text>'
        )
    # La alerta se abre (y se resuelve) al CERRAR una ventana: se marca en su ultimo frame.
    for k, a in enumerate(alertas):
        ya = 12 + 11 * (k % 3)
        marcas = (
            (a["abierta_ventana"], "", "abre"),
            (a.get("resuelta_ventana"), "4 3", "resuelve"),
        )
        for ventana, estilo, texto in marcas:
            if ventana is None:
                continue
            x = _x(min((ventana + 1) * tam_ventana - 1, n - 1), n)
            p.append(
                f'<line x1="{x}" x2="{x}" y1="{ya + 2}" y2="{ALTO - M}" stroke="#6a1b9a" '
                f'stroke-width="1.5" stroke-dasharray="{estilo}"/><text x="{x + 3}" y="{ya}" '
                f'font-size="10" fill="#6a1b9a">{texto} {escape(a["alert_id"])} '
                f"({escape(a['rule_id'])})</text>"
            )
    for e in eventos:
        x = _x(e["seq"], n)
        titulo = escape(
            f"{e['event_id']} {e['estado']} {e.get('zona') or ''} "
            f"{'' if e['score_principal'] is None else round(e['score_principal'], 3)}"
        )
        if e["estado"] == "ok":
            p.append(
                f'<a href="/eventos/{escape(e["event_id"])}"><circle cx="{x}" '
                f'cy="{_y(e["score_principal"])}" r="4" fill="{COLOR[e["zona"]]}">'
                f"<title>{titulo}</title></circle></a>"
            )
        else:
            color = "#777" if e["estado"] == "sin_detecciones" else "#b3261e"
            marca = "▽" if e["estado"] == "sin_detecciones" else "✕"
            p.append(
                f'<a href="/eventos/{escape(e["event_id"])}"><text x="{x}" '
                f'y="{ALTO - M + 16}" font-size="11" text-anchor="middle" fill="{color}">'
                f"{marca}<title>{titulo}</title></text></a>"
            )
    p.append(
        f'<text x="{M}" y="{ALTO - 6}" font-size="11">frame (0–{n - 1}) · ● score '
        "principal por zona · ▽ sin detecciones · ✕ error (sin score) · "
        "| abre / ¦ resuelve alerta (al cierre de ventana) · gris punteado: límites de ventana"
        "</text></svg>"
    )
    return "".join(p)


def svg_ventanas(ventanas: list[dict[str, Any]], p_ref: float | None, condicion: float) -> str:
    n = len(ventanas)
    h = 230
    ancho_barra = (ANCHO - M - MD) / max(n, 1)

    def y(v: float) -> float:
        return h - M - (h - 2 * M) * v

    p = [
        f'<svg viewBox="0 0 {ANCHO} {h}" role="img" aria-label="Proporcion baja por ventana" '
        f'style="width:100%;max-width:{ANCHO}px;background:#fff;border:1px solid #dde">'
    ]
    for v in (0, 0.5, 1):
        p.append(
            f'<text x="{M - 6}" y="{y(v) + 4}" font-size="11" text-anchor="end">{v}</text>'
            f'<line x1="{M}" x2="{ANCHO - MD}" y1="{y(v)}" y2="{y(v)}" stroke="#eee"/>'
        )
    for i, w in enumerate(ventanas):
        x = M + i * ancho_barra + 4
        etiqueta = escape(w["window_id"].rsplit("-", 1)[-1])
        if w["suficiente"]:
            pb = w["proporcion_baja"]
            color = "#b3261e" if pb >= condicion else "#7a8aa0"
            p.append(
                f'<rect x="{x}" y="{y(pb)}" width="{ancho_barra - 8}" height="{y(0) - y(pb)}" '
                f'fill="{color}"><title>{etiqueta}: {w["bajos"]}/{w["puntuados"]} = '
                f"{pb:.3f}</title></rect>"
            )
        else:
            p.append(
                f'<rect x="{x}" y="{y(1)}" width="{ancho_barra - 8}" height="{y(0) - y(1)}" '
                f'fill="none" stroke="#999" stroke-dasharray="4 3"/><text x="{x + 4}" '
                f'y="{y(0.5)}" font-size="10" fill="#666">insuficiente '
                f"({w['puntuados']} punt.)</text>"
            )
        p.append(
            f'<text x="{x + (ancho_barra - 8) / 2}" y="{h - M + 14}" font-size="10" '
            f'text-anchor="middle">{etiqueta}</text>'
        )
    lineas = [(condicion, f"condición {condicion}", "#b3261e")]
    if p_ref is not None:
        lineas.append((p_ref, f"referencia {p_ref:.3f}", "#11703a"))
    for v, texto, color in lineas:
        p.append(
            f'<line x1="{M}" x2="{ANCHO - MD}" y1="{y(v)}" y2="{y(v)}" stroke="{color}" '
            f'stroke-dasharray="6 4"/><text x="{ANCHO - MD + 4}" y="{y(v) + 4}" '
            f'font-size="10" fill="{color}">{texto}</text>'
        )
    p.append("</svg>")
    return "".join(p)
