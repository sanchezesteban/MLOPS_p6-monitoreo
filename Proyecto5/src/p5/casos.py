"""Runner de casos C01-C10 (P5-13).

Ejecuta cada caso contra la misma politica y el mismo adaptador que la aplicacion y
compara lo observado con una expectativa que vive aparte. El runner no lee la
expectativa desde la politica ni desde el detector: solo la usa al final, para
decidir si el caso pasa.

    PYTHONPATH=src python -m p5.casos --casos casos --config config/politica.yaml \
        --salida resultados/casos

Los casos `real` se reproducen desde un `eventos.jsonl` ya producido por el detector
(P5-04) o por el recorrido integral (P5-14); el runner no corre el detector. Los
casos `sintetico` traen sus eventos en el YAML. El reloj es simulado y avanza con
`t_capture_ms`/`t_ms`: nunca se usa `sleep`.

Si falta un insumo o una expectativa no se cumple, el proceso sale con codigo 1.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

import yaml

from p5.contrato import (
    MOVEMENT_ACTIONS,
    ContratoError,
    PerceptionEvent,
    validar_evento,
    validar_secuencia,
)

HASH_CERO = "0" * 64
TIPOS_CASO = frozenset({"real", "sintetico"})
TIPOS_CONTROL = frozenset({"watchdog", "emergencia", "rearme", "cierre"})
ESTADOS_BLOQUEADOS = frozenset({"centro", "bloqueado"})


class InsumoFaltanteError(RuntimeError):
    """El caso no puede correr porque falta un archivo o un dato obligatorio."""


class CasoInvalidoError(ValueError):
    """El YAML del caso o de la expectativa no tiene la forma esperada."""


@dataclass(frozen=True)
class Caso:
    id: str
    nombre: str
    tipo: str
    estado_inicial: str
    entrada: dict[str, Any]
    expectativa_path: Path
    ruta: Path


@dataclass(frozen=True)
class Expectativa:
    id: str
    datos: dict[str, Any]
    ruta: Path


@dataclass
class Paso:
    """Un cuadro o un evento de control ya procesado por el ejecutor."""

    id: str
    tipo: str
    t_ms: float
    comando: dict[str, Any] | None = None
    decision: dict[str, Any] | None = None
    error: str | None = None


@dataclass
class ResultadoCaso:
    id: str
    nombre: str
    tipo: str
    estado: str = "error"
    fallos: list[str] = field(default_factory=list)
    error: str | None = None
    pasos: list[Paso] = field(default_factory=list)
    expectativa: str | None = None
    expectativa_sha256: str | None = None


class EjecutorCaso(Protocol):
    """Contrato minimo entre el runner y quien ejecuta politica + adaptador."""

    def avanzar(self, t_ms: float) -> None: ...

    def cuadro(self, evento: PerceptionEvent) -> Paso: ...

    def control(self, evento: dict[str, Any]) -> Paso: ...

    def fallo(self, t_ms: float, razon: str, paso_id: str) -> Paso: ...

    def cerrar(self) -> None: ...


def sha256_archivo(ruta: Path) -> str:
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


def _ruta_visible(ruta: Path) -> Path:
    """Ruta relativa al directorio de trabajo para mensajes y evidencia, si es posible."""
    try:
        return ruta.resolve().relative_to(Path.cwd().resolve())
    except ValueError:
        return ruta


def _texto_requerido(datos: dict[str, Any], clave: str, origen: Path) -> str:
    valor = datos.get(clave)
    if not isinstance(valor, str) or not valor.strip():
        raise CasoInvalidoError(f"{origen}: falta {clave} o no es texto no vacio")
    return valor


def cargar_caso(ruta: Path) -> Caso:
    try:
        datos = yaml.safe_load(ruta.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise CasoInvalidoError(f"{ruta}: no se pudo leer ({exc})") from exc
    if not isinstance(datos, dict):
        raise CasoInvalidoError(f"{ruta}: se espera un mapa")

    caso_id = _texto_requerido(datos, "id", ruta)
    nombre = _texto_requerido(datos, "nombre", ruta)
    tipo = _texto_requerido(datos, "tipo", ruta)
    if tipo not in TIPOS_CASO:
        raise CasoInvalidoError(f"{ruta}: tipo {tipo!r} no es real ni sintetico")
    estado_inicial = _texto_requerido(datos, "estado_inicial", ruta)
    entrada = datos.get("entrada")
    if not isinstance(entrada, dict) or not entrada:
        raise CasoInvalidoError(f"{ruta}: falta entrada o no es un mapa")
    expectativa = _texto_requerido(datos, "expectativa", ruta)
    expectativa_path = (ruta.parent / expectativa).resolve()
    if not expectativa_path.is_file():
        raise CasoInvalidoError(f"{ruta}: no existe la expectativa {expectativa_path}")

    return Caso(
        id=caso_id,
        nombre=nombre,
        tipo=tipo,
        estado_inicial=estado_inicial,
        entrada=entrada,
        expectativa_path=expectativa_path,
        ruta=ruta,
    )


def cargar_expectativa(caso: Caso) -> Expectativa:
    try:
        datos = yaml.safe_load(caso.expectativa_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise CasoInvalidoError(f"{caso.expectativa_path}: no se pudo leer ({exc})") from exc
    if not isinstance(datos, dict):
        raise CasoInvalidoError(f"{caso.expectativa_path}: se espera un mapa")
    if datos.get("id") != caso.id:
        raise CasoInvalidoError(
            f"{caso.expectativa_path}: id {datos.get('id')!r} distinto de {caso.id!r}"
        )
    if "cuadros" not in datos and "pasos" not in datos and "acciones_por_cuadro" not in datos:
        raise CasoInvalidoError(
            f"{caso.expectativa_path}: falta cuadros, pasos o acciones_por_cuadro"
        )
    return Expectativa(id=caso.id, datos=datos, ruta=_ruta_visible(caso.expectativa_path))


def descubrir_casos(carpeta: Path) -> list[Path]:
    if not carpeta.is_dir():
        raise CasoInvalidoError(f"{carpeta}: no es una carpeta")
    return sorted(p for p in carpeta.glob("C*.yaml") if p.is_file())


def _run_id_sintetico(caso: Caso) -> str:
    valor = caso.entrada.get("run_id", f"run-{caso.id.lower()}")
    if not isinstance(valor, str) or not valor.strip():
        raise CasoInvalidoError(f"{caso.ruta}: run_id debe ser texto no vacio")
    return valor


def _evento_sintetico(caso: Caso, datos: dict[str, Any]) -> tuple[PerceptionEvent, float]:
    frame_id = _texto_requerido(datos, "frame_id", caso.ruta)
    try:
        t_capture = float(datos["t_capture_ms"])
    except (KeyError, TypeError, ValueError) as exc:
        raise CasoInvalidoError(f"{caso.ruta}: {frame_id} sin t_capture_ms numerico") from exc

    status = datos.get("status", "ok")
    if status not in {"ok", "stale", "error"}:
        raise CasoInvalidoError(f"{caso.ruta}: {frame_id} tiene status {status!r}")
    ancho = caso.entrada.get("image_width")
    alto = caso.entrada.get("image_height")
    if not isinstance(ancho, int) or not isinstance(alto, int):
        raise CasoInvalidoError(f"{caso.ruta}: el caso sintetico necesita image_width/image_height")
    secuencia = _texto_requerido(caso.entrada, "sequence_id", caso.ruta)
    error_msg = datos.get("error_msg")
    if status == "ok":
        error_msg = None
    elif not isinstance(error_msg, str) or not error_msg:
        raise CasoInvalidoError(f"{caso.ruta}: {frame_id} con status {status} necesita error_msg")

    evento = {
        "schema_version": "1.0",
        "run_id": _run_id_sintetico(caso),
        "sequence_id": secuencia,
        "frame_id": frame_id,
        "t_capture_ms": t_capture,
        "image_path": None if status == "error" else f"sinteticos/{frame_id}.jpg",
        "image_sha256": None if status == "error" else HASH_CERO,
        "image_width": None if status == "error" else ancho,
        "image_height": None if status == "error" else alto,
        "model_sha256": HASH_CERO,
        "config_sha256": HASH_CERO,
        "status": status,
        "error_msg": error_msg,
        "synthetic": True,
        "detections": datos.get("detections", []),
    }
    return validar_evento(evento), t_capture


def _ruta_eventos(caso: Caso) -> Path:
    valor = caso.entrada.get("eventos")
    if valor is None:
        secuencia = _texto_requerido(caso.entrada, "secuencia", caso.ruta)
        valor = f"datos/eventos/{secuencia}.jsonl"
    if not isinstance(valor, str) or not valor.strip():
        raise CasoInvalidoError(f"{caso.ruta}: eventos debe ser una ruta no vacia")
    ruta = Path(valor)
    if not ruta.is_absolute():
        ruta = caso.ruta.parent.parent / ruta
    return ruta


def _cargar_eventos_reales(caso: Caso) -> list[PerceptionEvent]:
    ruta = _ruta_eventos(caso)
    if not ruta.is_file():
        raise InsumoFaltanteError(
            f"{caso.id}: falta {ruta}. Produce los eventos con el detector (P5-04) "
            "o con p5.recorrer (P5-14)."
        )
    eventos: list[PerceptionEvent] = []
    for numero, linea in enumerate(ruta.read_text(encoding="utf-8").splitlines(), 1):
        if not linea.strip():
            continue
        try:
            datos = json.loads(linea)
            eventos.append(validar_evento(datos))
        except (json.JSONDecodeError, ContratoError) as exc:
            raise InsumoFaltanteError(f"{ruta}:{numero}: evento invalido ({exc})") from exc
    if not eventos:
        raise InsumoFaltanteError(f"{ruta}: no tiene eventos")
    errores = validar_secuencia(eventos)
    if errores:
        raise InsumoFaltanteError(f"{ruta}: secuencia invalida: " + "; ".join(errores))
    secuencia = _texto_requerido(caso.entrada, "secuencia", caso.ruta)
    distintas = {ev.sequence_id for ev in eventos}
    if distintas != {secuencia}:
        raise InsumoFaltanteError(
            f"{ruta}: el caso espera la secuencia {secuencia!r} y el archivo trae "
            f"{sorted(distintas)!r}"
        )
    return eventos


def _pasos_sinteticos(caso: Caso, ejecutor: EjecutorCaso) -> list[Paso]:
    eventos = caso.entrada.get("eventos")
    if not isinstance(eventos, list) or not eventos:
        raise CasoInvalidoError(f"{caso.ruta}: un caso sintetico necesita entrada.eventos")
    pasos: list[Paso] = []
    for datos in eventos:
        if not isinstance(datos, dict):
            raise CasoInvalidoError(f"{caso.ruta}: cada evento debe ser un mapa")
        tipo = datos.get("tipo", "cuadro")
        if tipo == "cuadro":
            try:
                evento, t_ms = _evento_sintetico(caso, datos)
            except ContratoError as exc:
                frame_id = str(datos.get("frame_id", "cuadro_invalido"))
                t_ms = float(datos.get("t_capture_ms", 0))
                ejecutor.avanzar(t_ms)
                pasos.append(ejecutor.fallo(t_ms, f"evento_invalido: {exc}", frame_id))
                continue
            ejecutor.avanzar(t_ms)
            pasos.append(ejecutor.cuadro(evento))
        elif tipo in TIPOS_CONTROL:
            try:
                t_ms = float(datos["t_ms"])
            except (KeyError, TypeError, ValueError) as exc:
                raise CasoInvalidoError(f"{caso.ruta}: evento {tipo} sin t_ms numerico") from exc
            ejecutor.avanzar(t_ms)
            pasos.append(ejecutor.control(datos))
        else:
            raise CasoInvalidoError(f"{caso.ruta}: tipo de evento desconocido {tipo!r}")
    return pasos


def _pasos_reales(caso: Caso, ejecutor: EjecutorCaso, eventos: list[PerceptionEvent]) -> list[Paso]:
    pasos: list[Paso] = []
    for evento in eventos:
        ejecutor.avanzar(evento.t_capture_ms)
        pasos.append(ejecutor.cuadro(evento))
    return pasos


def _leer_cuadros(expectativa: Expectativa) -> list[dict[str, str]]:
    valor = expectativa.datos.get("acciones_por_cuadro")
    if not isinstance(valor, str) or not valor:
        raise CasoInvalidoError(f"{expectativa.ruta}: falta acciones_por_cuadro")
    ruta = (expectativa.ruta.parent / valor).resolve()
    if not ruta.is_file():
        raise InsumoFaltanteError(
            f"{expectativa.ruta}: falta {ruta}. Genera el CSV con p5.expectativas (P5-15)."
        )
    with ruta.open(encoding="utf-8", newline="") as archivo:
        return list(csv.DictReader(archivo))


def _permitidas(valor: Any, origen: Path) -> set[str]:
    if isinstance(valor, str):
        acciones = {parte.strip() for parte in valor.split("|") if parte.strip()}
    elif isinstance(valor, list) and all(isinstance(a, str) for a in valor):
        acciones = set(valor)
    else:
        raise CasoInvalidoError(f"{origen}: acciones_permitidas debe ser lista o texto con |")
    if not acciones:
        raise CasoInvalidoError(f"{origen}: acciones_permitidas esta vacio")
    return acciones


def _accion(paso: Paso | None) -> str | None:
    if paso is None or not isinstance(paso.comando, dict):
        return None
    valor = paso.comando.get("action")
    return valor if isinstance(valor, str) else None


def _es_movimiento(paso: Paso) -> bool:
    return _accion(paso) in MOVEMENT_ACTIONS


def _por_id(pasos: list[Paso], paso_id: str) -> Paso | None:
    return next((p for p in pasos if p.id == paso_id), None)


def _comparar_paso(
    esperado: dict[str, Any],
    paso: Paso | None,
    fallos: list[str],
    etiqueta: str,
    origen: Path,
) -> None:
    if paso is None:
        fallos.append(f"{etiqueta}: el caso no produjo ese paso")
        return
    acciones = _permitidas(esperado.get("acciones_permitidas"), origen)
    accion = _accion(paso)
    if accion is None:
        fallos.append(f"{etiqueta}: no hay comando observado")
        return
    if accion not in acciones:
        fallos.append(f"{etiqueta}: accion {accion} no permitida (esperaba {sorted(acciones)})")
    if paso.error and not esperado.get("permitir_error"):
        fallos.append(f"{etiqueta}: el paso reporto error: {paso.error}")
    if (
        isinstance(paso.comando, dict)
        and paso.comando.get("error")
        and not esperado.get("permitir_error")
    ):
        fallos.append(f"{etiqueta}: el adaptador rechazo el comando: {paso.comando['error']}")
    maximo = esperado.get("velocidad_max")
    if isinstance(maximo, int | float):
        velocidad = paso.comando.get("speed") if isinstance(paso.comando, dict) else None
        if not isinstance(velocidad, int | float) or velocidad > maximo:
            fallos.append(f"{etiqueta}: velocidad {velocidad!r} > maxima {maximo!r}")


def _comparar_cuadros_sinteticos(
    expectativa: Expectativa, pasos: list[Paso], fallos: list[str]
) -> None:
    cuadros = expectativa.datos.get("cuadros")
    if not isinstance(cuadros, list):
        raise CasoInvalidoError(f"{expectativa.ruta}: cuadros debe ser una lista")
    for esperado in cuadros:
        if not isinstance(esperado, dict):
            raise CasoInvalidoError(f"{expectativa.ruta}: cada cuadro debe ser un mapa")
        frame_id = _texto_requerido(esperado, "frame_id", expectativa.ruta)
        _comparar_paso(esperado, _por_id(pasos, frame_id), fallos, frame_id, expectativa.ruta)


def _comparar_pasos_sinteticos(
    expectativa: Expectativa, pasos: list[Paso], fallos: list[str]
) -> None:
    esperados = expectativa.datos.get("pasos")
    if not isinstance(esperados, list):
        raise CasoInvalidoError(f"{expectativa.ruta}: pasos debe ser una lista")
    for esperado in esperados:
        if not isinstance(esperado, dict):
            raise CasoInvalidoError(f"{expectativa.ruta}: cada paso debe ser un mapa")
        paso_id = _texto_requerido(esperado, "id", expectativa.ruta)
        _comparar_paso(esperado, _por_id(pasos, paso_id), fallos, paso_id, expectativa.ruta)


def _comparar_cuadros_reales(
    expectativa: Expectativa, pasos: list[Paso], fallos: list[str]
) -> None:
    filas = _leer_cuadros(expectativa)
    permitidas_por_id = {paso.id: paso for paso in pasos}
    vistos = set()
    for fila in filas:
        frame_id = fila.get("frame_id", "")
        if not frame_id:
            fallos.append(f"{expectativa.ruta}: fila de cuadros.csv sin frame_id")
            continue
        vistos.add(frame_id)
        esperado = {
            "acciones_permitidas": fila.get("acciones_permitidas", ""),
        }
        _comparar_paso(
            esperado, permitidas_por_id.get(frame_id), fallos, frame_id, expectativa.ruta
        )

    requeridos = set(expectativa.datos.get("estados_requeridos", []))
    estados = {fila.get("estado_via", "") for fila in filas}
    faltantes = requeridos - estados
    if faltantes:
        fallos.append(
            f"{expectativa.ruta}: no aparecen los estados requeridos {sorted(faltantes)} "
            f"(estados observados: {sorted(estados)})"
        )

    plazo = expectativa.datos.get("plazo_reaccion_cuadros", 0)
    if not isinstance(plazo, int) or plazo < 0:
        raise CasoInvalidoError(f"{expectativa.ruta}: plazo_reaccion_cuadros debe ser entero >= 0")
    for indice, fila in enumerate(filas):
        if fila.get("estado_via") not in ESTADOS_BLOQUEADOS:
            continue
        ventana = filas[indice : indice + plazo + 1]
        hay_stop = any(
            _accion(permitidas_por_id.get(f.get("frame_id", ""))) == "STOP" for f in ventana
        )
        if not hay_stop:
            fallos.append(
                f"{expectativa.ruta}: {fila.get('frame_id')} quedo bloqueado y no hubo STOP "
                f"en {plazo} cuadro(s)"
            )


def _indice_por_id(pasos: list[Paso], paso_id: str) -> int | None:
    return next((i for i, paso in enumerate(pasos) if paso.id == paso_id), None)


def _evaluar_requisitos(
    expectativa: Expectativa,
    pasos: list[Paso],
    filas: list[dict[str, str]] | None,
    fallos: list[str],
) -> None:
    requisitos = expectativa.datos.get("requisitos", [])
    if not isinstance(requisitos, list):
        raise CasoInvalidoError(f"{expectativa.ruta}: requisitos debe ser una lista")
    for requisito in requisitos:
        if not isinstance(requisito, dict):
            raise CasoInvalidoError(f"{expectativa.ruta}: cada requisito debe ser un mapa")
        tipo = requisito.get("tipo")
        if tipo == "movimiento_minimo":
            minimo = requisito.get("min_cuadros", 1)
            if not isinstance(minimo, int) or minimo < 1:
                raise CasoInvalidoError(f"{expectativa.ruta}: min_cuadros debe ser entero >= 1")
            movimientos = sum(1 for paso in pasos if _es_movimiento(paso))
            if movimientos < minimo:
                fallos.append(
                    f"{expectativa.ruta}: movimiento_minimo pide {minimo} y hubo {movimientos}"
                )
        elif tipo == "sin_movimiento_entre_obstaculos":
            if filas is None:
                fallos.append(f"{expectativa.ruta}: requisito solo para casos reales")
                continue
            indices = [
                i for i, fila in enumerate(filas) if fila.get("estado_via") in ESTADOS_BLOQUEADOS
            ]
            if not indices:
                fallos.append(f"{expectativa.ruta}: no hay cuadros bloqueados para evaluar")
                continue
            desde = _indice_por_id(pasos, filas[indices[0]].get("frame_id", ""))
            hasta = _indice_por_id(pasos, filas[indices[-1]].get("frame_id", ""))
            if desde is None or hasta is None:
                fallos.append(f"{expectativa.ruta}: faltan pasos entre los cuadros bloqueados")
                continue
            if any(_es_movimiento(paso) for paso in pasos[desde : hasta + 1]):
                fallos.append(
                    f"{expectativa.ruta}: hubo movimiento entre {pasos[desde].id} "
                    f"y {pasos[hasta].id}"
                )
        elif tipo == "reanuda_tras_despeje":
            if filas is None:
                fallos.append(f"{expectativa.ruta}: requisito solo para casos reales")
                continue
            maximo = requisito.get("max_cuadros", 5)
            if not isinstance(maximo, int) or maximo < 1:
                raise CasoInvalidoError(f"{expectativa.ruta}: max_cuadros debe ser entero >= 1")
            indices = [
                i for i, fila in enumerate(filas) if fila.get("estado_via") in ESTADOS_BLOQUEADOS
            ]
            if not indices:
                fallos.append(f"{expectativa.ruta}: no hay cuadros bloqueados para evaluar")
                continue
            despejados = 0
            reanudo = False
            for fila in filas[indices[-1] + 1 :]:
                if fila.get("estado_via") in ESTADOS_BLOQUEADOS:
                    continue
                despejados += 1
                paso = _por_id(pasos, fila.get("frame_id", ""))
                if paso is not None and _es_movimiento(paso):
                    reanudo = True
                    break
                if despejados >= maximo:
                    break
            if not reanudo:
                fallos.append(
                    f"{expectativa.ruta}: no reanudo en {maximo} cuadros despejados tras el bloqueo"
                )
        elif tipo == "stop_por_watchdog":
            paso_id = _texto_requerido(requisito, "evento", expectativa.ruta)
            paso = _por_id(pasos, paso_id)
            if paso is None or _accion(paso) != "STOP":
                fallos.append(f"{expectativa.ruta}: {paso_id} no produjo STOP de watchdog")
                continue
            plazo = requisito.get("plazo_ms")
            if isinstance(plazo, int | float) and isinstance(paso.comando, dict):
                t_command = paso.comando.get("t_command_ms")
                if isinstance(t_command, int | float) and t_command - paso.t_ms > plazo:
                    fallos.append(
                        f"{expectativa.ruta}: watchdog tardo {t_command - paso.t_ms:g} ms "
                        f"(maximo {plazo:g})"
                    )
        elif tipo == "sin_movimiento_despues_de":
            paso_id = _texto_requerido(requisito, "evento", expectativa.ruta)
            indice = _indice_por_id(pasos, paso_id)
            if indice is None:
                fallos.append(f"{expectativa.ruta}: no existe el paso {paso_id}")
            elif any(_es_movimiento(paso) for paso in pasos[indice + 1 :]):
                fallos.append(f"{expectativa.ruta}: hubo movimiento despues de {paso_id}")
        elif tipo == "cuadro_vencido_rechazado":
            frame_id = _texto_requerido(requisito, "frame_id", expectativa.ruta)
            paso = _por_id(pasos, frame_id)
            if paso is None or _accion(paso) != "STOP":
                fallos.append(f"{expectativa.ruta}: {frame_id} no termino en STOP")
            elif "vencido" not in str((paso.comando or {}).get("reason", "")):
                fallos.append(f"{expectativa.ruta}: {frame_id} no se marco como vencido")
        elif tipo == "stop_por_error":
            eventos = requisito.get("eventos")
            if not isinstance(eventos, list) or not eventos:
                raise CasoInvalidoError(f"{expectativa.ruta}: stop_por_error necesita eventos")
            for paso_id in eventos:
                paso = _por_id(pasos, str(paso_id))
                if paso is None or _accion(paso) != "STOP":
                    fallos.append(f"{expectativa.ruta}: {paso_id} no produjo STOP por error")
        elif tipo == "evento_invalido_rechazado":
            frame_id = _texto_requerido(requisito, "frame_id", expectativa.ruta)
            paso = _por_id(pasos, frame_id)
            if paso is None or paso.error is None or _accion(paso) != "STOP":
                fallos.append(
                    f"{expectativa.ruta}: {frame_id} no quedo registrado como invalido con STOP"
                )
        elif tipo == "rearme_requerido":
            emergencia = _texto_requerido(requisito, "emergencia", expectativa.ruta)
            rearme = _texto_requerido(requisito, "rearme", expectativa.ruta)
            maximo = requisito.get("max_cuadros", 3)
            if not isinstance(maximo, int) or maximo < 1:
                raise CasoInvalidoError(f"{expectativa.ruta}: max_cuadros debe ser entero >= 1")
            i_emergencia = _indice_por_id(pasos, emergencia)
            i_rearme = _indice_por_id(pasos, rearme)
            if i_emergencia is None or i_rearme is None or i_rearme <= i_emergencia:
                fallos.append(f"{expectativa.ruta}: faltan emergencia/rearme en orden")
                continue
            if any(_es_movimiento(paso) for paso in pasos[i_emergencia : i_rearme + 1]):
                fallos.append(f"{expectativa.ruta}: hubo movimiento con la emergencia enclavada")
                continue
            despejados = 0
            reanudo = False
            for paso in pasos[i_rearme + 1 :]:
                if paso.tipo != "cuadro":
                    continue
                despejados += 1
                if _es_movimiento(paso):
                    reanudo = True
                    break
                if despejados >= maximo:
                    break
            if not reanudo:
                fallos.append(f"{expectativa.ruta}: no reanudo en {maximo} cuadros tras el rearme")
        elif tipo == "stop_al_cerrar":
            cierres = [
                paso for paso in pasos if paso.tipo == "cierre" or paso.id.startswith("cierre")
            ]
            if not cierres:
                fallos.append(f"{expectativa.ruta}: no hay paso de cierre")
                continue
            cierre = cierres[-1]
            if _accion(cierre) != "STOP":
                fallos.append(f"{expectativa.ruta}: el cierre no produjo STOP")
            elif str((cierre.comando or {}).get("reason", "")) not in {"shutdown", "cierre"}:
                fallos.append(
                    f"{expectativa.ruta}: el STOP de cierre no tiene razon shutdown/cierre"
                )
        else:
            fallos.append(f"{expectativa.ruta}: requisito desconocido {tipo!r}")


def evaluar_expectativa(
    expectativa: Expectativa,
    pasos: list[Paso],
    *,
    es_real: bool,
) -> list[str]:
    """Devuelve la lista de fallos; vacia significa que el caso cumple."""
    fallos: list[str] = []
    if es_real:
        _comparar_cuadros_reales(expectativa, pasos, fallos)
    elif "pasos" in expectativa.datos:
        _comparar_pasos_sinteticos(expectativa, pasos, fallos)
    else:
        _comparar_cuadros_sinteticos(expectativa, pasos, fallos)
    filas = _leer_cuadros(expectativa) if es_real else None
    _evaluar_requisitos(expectativa, pasos, filas, fallos)
    return fallos


def correr_caso(
    caso: Caso,
    expectativa: Expectativa,
    ejecutor: EjecutorCaso,
) -> ResultadoCaso:
    if caso.estado_inicial != "INICIO":
        raise CasoInvalidoError(
            f"{caso.ruta}: estado_inicial {caso.estado_inicial!r}; el runner solo soporta INICIO"
        )
    try:
        if caso.tipo == "real":
            eventos = _cargar_eventos_reales(caso)
            pasos = _pasos_reales(caso, ejecutor, eventos)
        else:
            pasos = _pasos_sinteticos(caso, ejecutor)
    finally:
        ejecutor.cerrar()
    fallos = evaluar_expectativa(expectativa, pasos, es_real=caso.tipo == "real")
    ruta_expectativa = str(_ruta_visible(caso.expectativa_path))
    return ResultadoCaso(
        id=caso.id,
        nombre=caso.nombre,
        tipo=caso.tipo,
        estado="pass" if not fallos else "fail",
        fallos=fallos,
        pasos=pasos,
        expectativa=ruta_expectativa,
        expectativa_sha256=sha256_archivo(caso.expectativa_path),
    )


class _PoliticaGrabada:
    """Envuelve la politica para conservar cada `Decision` en `decisiones.jsonl`."""

    def __init__(self, politica: Any, registro: list[dict[str, Any]]) -> None:
        self._politica = politica
        self._registro = registro

    @property
    def estado(self) -> str:
        return self._politica.estado

    def decidir(self, evento: PerceptionEvent) -> Any:
        decision = self._politica.decidir(evento)
        self._registro.append(asdict(decision))
        return decision

    def detener(self, event: str, razon: str) -> Any:
        decision = self._politica.detener(event, razon)
        self._registro.append(asdict(decision))
        return decision


def _contar_lineas(log_path: Path) -> int:
    if not log_path.is_file():
        return 0
    return len([linea for linea in log_path.read_text(encoding="utf-8").splitlines() if linea])


def _comando_nuevo(log_path: Path, antes: int) -> dict[str, Any] | None:
    if not log_path.is_file():
        return None
    lineas = [linea for linea in log_path.read_text(encoding="utf-8").splitlines() if linea]
    if len(lineas) <= antes:
        return None
    try:
        datos = json.loads(lineas[-1])
    except json.JSONDecodeError:
        return None
    return datos if isinstance(datos, dict) else None


class EjecutorPolitica:
    """Ejecutor real: politica de P5-10, adaptador de P5-11 y watchdog de P5-12.

    El watchdog arma el `Command`, aplica vencimientos, enclava la emergencia y
    registra el cierre. El runner solo avanza el reloj y traduce cada accion a un
    `Paso` con el comando que quedo en la bitacora del adaptador.
    """

    def __init__(
        self,
        caso: Caso,
        config_path: Path,
        control_config: Path | None,
        log_path: Path,
        run_id: str,
    ) -> None:
        try:
            from p5.control import AdaptadorVirtual
            from p5.politica import Politica, cargar_config
            from p5.watchdog import RelojControlado, Watchdog
            from p5.watchdog import cargar_config as cargar_config_watchdog
        except ImportError as exc:
            raise RuntimeError(
                "faltan p5.politica, p5.control y/o p5.watchdog; mergea #73, #74 y #76 "
                "antes de usar el ejecutor real"
            ) from exc

        self._politica_base = Politica(cargar_config(config_path))
        self._decisiones: list[dict[str, Any]] = []
        self._politica = _PoliticaGrabada(self._politica_base, self._decisiones)
        self._reloj = RelojControlado()
        self._controlador = AdaptadorVirtual(log_path, run_id, reloj=self._reloj)
        self._log_path = log_path
        self._run_id = run_id
        self._watchdog = Watchdog(
            self._politica,
            self._controlador,
            self._reloj,
            cargar_config_watchdog(control_config or Path("config/watchdog.yaml")),
            run_id,
        )
        self._cerrado = False

    def avanzar(self, t_ms: float) -> None:
        delta = float(t_ms) - self._reloj()
        if delta < 0:
            raise CasoInvalidoError(
                f"el reloj no puede retroceder: {t_ms} ms despues de {self._reloj()} ms"
            )
        self._reloj.avanzar(delta)

    def _capturar(self, accion: Any, paso_id: str, tipo: str, t_ms: float) -> Paso:
        antes_comandos = _contar_lineas(self._log_path)
        antes_decisiones = len(self._decisiones)
        accion()
        comando = _comando_nuevo(self._log_path, antes_comandos)
        decision = (
            self._decisiones[antes_decisiones] if len(self._decisiones) > antes_decisiones else None
        )
        return Paso(
            id=paso_id,
            tipo=tipo,
            t_ms=t_ms,
            comando=comando,
            decision=decision,
        )

    def cuadro(self, evento: PerceptionEvent) -> Paso:
        return self._capturar(
            lambda: self._watchdog.procesar_evento(evento),
            evento.frame_id,
            "cuadro",
            evento.t_capture_ms,
        )

    def control(self, evento: dict[str, Any]) -> Paso:
        tipo = str(evento.get("tipo"))
        paso_id = str(evento.get("id", tipo))
        t_ms = float(evento.get("t_ms", 0))
        if tipo == "watchdog":
            return self._capturar(lambda: self._watchdog.tick(), paso_id, "watchdog", t_ms)
        if tipo == "emergencia":
            razon = str(evento.get("razon", "emergencia"))
            return self._capturar(
                lambda: self._watchdog.emergencia(razon), paso_id, "emergencia", t_ms
            )
        if tipo == "rearme":
            if evento.get("valido") is not True:
                return Paso(id=paso_id, tipo="rearme", t_ms=t_ms)
            return self._capturar(self._watchdog.rearme, paso_id, "rearme", t_ms)
        if tipo == "cierre":
            paso = self._capturar(self._watchdog.cerrar, paso_id, "cierre", t_ms)
            self._cerrado = True
            return paso
        raise CasoInvalidoError(f"evento de control desconocido: {tipo!r}")

    def fallo(self, t_ms: float, razon: str, paso_id: str) -> Paso:
        # El contrato no permite pasar un evento invalido: se representa como un
        # error de percepcion valido, conservando el frame_id para la trazabilidad.
        evento = PerceptionEvent(
            schema_version="1.0",
            run_id=self._run_id,
            sequence_id=paso_id.split("_")[0],
            frame_id=paso_id,
            t_capture_ms=t_ms,
            image_path=None,
            image_sha256=None,
            image_width=None,
            image_height=None,
            model_sha256=HASH_CERO,
            config_sha256=HASH_CERO,
            status="error",
            error_msg=razon,
            synthetic=True,
            detections=(),
        )
        paso = self._capturar(
            lambda: self._watchdog.procesar_evento(evento), paso_id, "cuadro_invalido", t_ms
        )
        paso.error = razon
        return paso

    def cerrar(self) -> None:
        if not self._cerrado:
            self._watchdog.cerrar()
            self._cerrado = True


def fabrica_real(
    caso: Caso,
    config_path: Path,
    control_config: Path | None,
    log_path: Path,
    run_id: str,
) -> EjecutorCaso:
    return EjecutorPolitica(caso, config_path, control_config, log_path, run_id)


def _resultado_dict(resultado: ResultadoCaso, carpeta_caso: Path, salida: Path) -> dict[str, Any]:
    try:
        comandos = str(carpeta_caso.relative_to(salida) / "comandos.jsonl")
    except ValueError:
        comandos = str(carpeta_caso / "comandos.jsonl")
    return {
        "id": resultado.id,
        "nombre": resultado.nombre,
        "tipo": resultado.tipo,
        "estado": resultado.estado,
        "expectativa": resultado.expectativa,
        "expectativa_sha256": resultado.expectativa_sha256,
        "pasos": len(resultado.pasos),
        "fallos": resultado.fallos,
        "error": resultado.error,
        "comandos": comandos,
    }


def _escribir_caso(resultado: ResultadoCaso, carpeta: Path) -> None:
    carpeta.mkdir(parents=True, exist_ok=True)
    with (carpeta / "comandos.jsonl").open("w", encoding="utf-8") as archivo:
        for paso in resultado.pasos:
            archivo.write(json.dumps(asdict(paso), ensure_ascii=False) + "\n")
    (carpeta / "resultado.json").write_text(
        json.dumps(
            _resultado_dict(resultado, carpeta, carpeta.parent), ensure_ascii=False, indent=2
        )
        + "\n",
        encoding="utf-8",
    )


def _imprimir_resumen(resultados: list[ResultadoCaso], codigo: int) -> None:
    for resultado in resultados:
        print(f"{resultado.id:>3}  {resultado.estado:<5}  {resultado.nombre}")
        for fallo in resultado.fallos:
            print(f"       - {fallo}")
        if resultado.error:
            print(f"       - error: {resultado.error}")
    pasan = sum(1 for r in resultados if r.estado == "pass")
    print(f"\nResultado: {pasan}/{len(resultados)} casos pasan (codigo de salida {codigo})")


def main(
    argv: list[str] | None = None,
    *,
    fabrica_ejecutor: Any = fabrica_real,
) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--casos", type=Path, required=True, help="carpeta con C01.yaml ... C10.yaml"
    )
    parser.add_argument("--config", type=Path, required=True, help="politica.yaml de P5-10")
    parser.add_argument("--salida", type=Path, required=True, help="carpeta nueva de resultados")
    parser.add_argument("--control-config", type=Path, help="config de tiempos de P5-12 (#64)")
    parser.add_argument("--caso", action="append", default=[], help="limita a un id, p. ej. C06")
    args = parser.parse_args(argv)

    try:
        rutas = descubrir_casos(args.casos)
    except CasoInvalidoError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    if args.caso:
        pedidos = {c.upper() for c in args.caso}
        rutas = [r for r in rutas if r.stem.upper() in pedidos]
    if not rutas:
        print(f"ERROR: no hay casos en {args.casos}", file=sys.stderr)
        return 1

    args.salida.mkdir(parents=True, exist_ok=True)
    config_sha = sha256_archivo(args.config) if args.config.is_file() else None
    resultados: list[ResultadoCaso] = []

    for ruta in rutas:
        carpeta = args.salida / ruta.stem
        try:
            caso = cargar_caso(ruta)
            expectativa = cargar_expectativa(caso)
            if caso.tipo == "real":
                eventos = _cargar_eventos_reales(caso)
                run_id = eventos[0].run_id
            else:
                eventos = []
                run_id = _run_id_sintetico(caso)
            ejecutor = fabrica_ejecutor(
                caso, args.config, args.control_config, carpeta / "comandos.jsonl", run_id
            )
            resultado = correr_caso(caso, expectativa, ejecutor)
        except (
            CasoInvalidoError,
            InsumoFaltanteError,
            ContratoError,
            RuntimeError,
            OSError,
        ) as exc:
            resultado = ResultadoCaso(
                id=ruta.stem,
                nombre=ruta.stem,
                tipo="desconocido",
                estado="error",
                error=str(exc),
            )
        except Exception as exc:
            resultado = ResultadoCaso(
                id=ruta.stem,
                nombre=ruta.stem,
                tipo="desconocido",
                estado="error",
                error=f"{type(exc).__name__}: {exc}",
            )
        _escribir_caso(resultado, carpeta)
        resultados.append(resultado)

    codigo = 0 if all(r.estado == "pass" for r in resultados) else 1
    resumen = {
        "schema_version": "1.0",
        "generado_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "config_sha256": config_sha,
        "casos": [_resultado_dict(r, args.salida / r.id, args.salida) for r in resultados],
        "resumen": {
            "total": len(resultados),
            "pass": sum(1 for r in resultados if r.estado == "pass"),
            "fail": sum(1 for r in resultados if r.estado == "fail"),
            "error": sum(1 for r in resultados if r.estado == "error"),
        },
        "resultado": "pass" if codigo == 0 else "fail",
        "codigo_salida": codigo,
    }
    (args.salida / "resumen.json").write_text(
        json.dumps(resumen, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    _imprimir_resumen(resultados, codigo)
    return codigo


if __name__ == "__main__":
    sys.exit(main())
