"""P5-08: benchmark por etapas; modo simulado predeterminado, nunca mueve motores."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import json
import math
import os
import platform
import subprocess
import sys
import time
from collections import Counter
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path
from typing import Any, Protocol

import numpy as np
import yaml

from p5.contrato import validar_evento
from p5.control import AdaptadorVirtual
from p5.detector_onnx import cargar_config as cargar_detector
from p5.detector_onnx import decodificar, leer_imagen, letterbox, sha256_archivo
from p5.politica import Politica
from p5.politica import cargar_config as cargar_politica
from p5.watchdog import Watchdog
from p5.watchdog import cargar_config as cargar_watchdog

RAIZ = Path(__file__).resolve().parents[2]
ETAPAS = ("preprocesamiento_ms", "inferencia_ms", "posprocesamiento_ms", "politica_adaptador_ms")
COLUMNAS = ("intento", "fase", "estado", "etapa_fallo", "error", *ETAPAS, "total_local_ms")
VERSION = "p5-08/1.0"


class BenchmarkError(ValueError):
    """Datos o parametros del benchmark inconsistentes."""


def exigir(condicion: bool, mensaje: str) -> None:
    if not condicion:
        raise BenchmarkError(mensaje)


def referencia(ruta: Path) -> dict:
    return {"archivo": ruta.name, "bytes": ruta.stat().st_size, "sha256": sha256_archivo(ruta)}


def escribir_json(ruta: Path, datos: dict) -> None:
    with ruta.open("x", encoding="utf-8", newline="\n") as archivo:
        json.dump(datos, archivo, indent=2, ensure_ascii=False, sort_keys=True, allow_nan=False)
        archivo.write("\n")


def estadisticas(valores: list[float]) -> dict:
    """Misma interpolacion lineal que P4/recursos/medir_recursos.py, sin redondear."""
    exigir(all(math.isfinite(v) and v >= 0 for v in valores), "tiempos invalidos")
    if not valores:
        return {"n": 0, "p50_ms": None, "p95_ms": None, "max_ms": None}
    p50, p95 = np.percentile(valores, [50, 95], method="linear")
    return {"n": len(valores), "p50_ms": float(p50), "p95_ms": float(p95), "max_ms": max(valores)}


def _salida_comando(comando: list[str]) -> str:
    try:
        return subprocess.check_output(
            comando,
            text=True,
            encoding="utf-8",
            errors="replace",
            stderr=subprocess.DEVNULL,
            timeout=5,
        ).strip()
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return ""


def _modelo_especifico(nombre: str) -> bool:
    genericos = {"arm", "arm64", "arm64e", "aarch64", "x86", "x86_64", "amd64", "i386", "i686"}
    normalizado = nombre.strip().lower()
    return (
        bool(normalizado)
        and normalizado not in genericos
        and not normalizado.startswith(("armv", "intel64 family", "amd64 family"))
    )


def identificar_cpu() -> dict:
    """Modelo del procesador; nunca confunde una arquitectura con un modelo medido."""
    sistema = platform.system()
    nombre = fuente = ""
    if sistema == "Darwin":
        nombre = _salida_comando(["sysctl", "-n", "machdep.cpu.brand_string"])
        fuente = "sysctl machdep.cpu.brand_string"
        if not _modelo_especifico(nombre):
            try:
                hardware = json.loads(
                    _salida_comando(["system_profiler", "SPHardwareDataType", "-json"])
                )
                datos = hardware["SPHardwareDataType"][0]
                nombre = datos.get("chip_type") or datos.get("cpu_type") or ""
                fuente = "system_profiler SPHardwareDataType (chip_type/cpu_type)"
            except (ValueError, KeyError, IndexError, TypeError):
                nombre = ""
    elif sistema == "Windows":
        try:
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0"
            ) as clave:
                nombre = winreg.QueryValueEx(clave, "ProcessorNameString")[0].strip()
            fuente = "registro Windows ProcessorNameString"
        except (ImportError, OSError):
            pass
    elif sistema == "Linux":
        try:
            for linea in Path("/proc/cpuinfo").read_text(encoding="utf-8").splitlines():
                clave, separador, valor = linea.partition(":")
                if (
                    separador
                    and clave.strip() in ("model name", "Hardware")
                    and _modelo_especifico(valor)
                ):
                    nombre, fuente = valor.strip(), f"/proc/cpuinfo: {clave.strip()}"
                    break
        except OSError:
            pass
    if not _modelo_especifico(nombre):
        nombre, fuente = platform.processor().strip(), "platform.processor"
    confirmado = _modelo_especifico(nombre)
    return {
        "cpu": nombre if confirmado else None,
        "cpu_fuente": fuente if confirmado else None,
        "cpu_modelo_confirmado": confirmado,
        "cpu_advertencia": None
        if confirmado
        else "Modelo no disponible; arquitectura no es modelo.",
    }


def condiciones() -> dict:
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=RAIZ, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        commit = None
    return {
        **identificar_cpu(),
        "cpu_logicos": os.cpu_count(),
        "arquitectura": platform.machine(),
        "sistema_operativo": platform.platform(),
        "python": platform.python_version(),
        "onnxruntime": importlib.metadata.version("onnxruntime"),
        "numpy": np.__version__,
        "commit": commit,
        "reloj": "time.perf_counter",
        "unidad": "ms",
        "adaptador": "p5.control.AdaptadorVirtual (JSONL + flush, sin motores)",
        "pausas_reproduccion": False,
        "carga_y_decodificacion_imagen_fuera_del_cronometro": True,
        "inicializacion_sesion_fuera_del_cronometro": True,
        "network_durante_medicion": False,
        "variables_hilos": {
            k: os.environ.get(k)
            for k in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS")
        },
        "referencia_metodologica_P4": referencia(
            RAIZ.parent / "Proyecto4/recursos/medir_recursos.py"
        ),
    }


class Cadena(Protocol):
    metadatos: dict

    def abrir(self, salida: Path) -> None: ...
    def preprocesar(self, intento: int) -> Any: ...
    def inferir(self, tensor: Any) -> Any: ...
    def posprocesar(self, salida: Any) -> Any: ...
    def decidir(self, detecciones: Any) -> None: ...
    def fallo(self, mensaje: str) -> None: ...
    def cerrar(self) -> None: ...


class CadenaDetector:
    """Etapas publicas de P5-04 + politica/watchdog/adaptador existentes, sin replay."""

    def __init__(
        self,
        *,
        modo: str,
        detector: Path,
        politica: Path,
        watchdog: Path,
        imagen: Path | None = None,
        hilos: int | None = None,
    ) -> None:
        exigir(modo in ("simulado", "real"), "modo desconocido")
        exigir(
            hilos is None or (type(hilos) is int and hilos > 0), "hilos debe ser entero positivo"
        )
        exigir(modo != "real" or imagen is not None, "modo real requiere --imagen explicita")
        exigir(modo != "simulado" or imagen is None, "modo simulado no lee fotografias")
        self.config = cargar_detector(detector)
        self.cfg_politica = cargar_politica(politica)
        self.cfg_watchdog = cargar_watchdog(watchdog)
        descriptor = yaml.safe_load(self.config.descriptor.read_text(encoding="utf-8"))
        self.clases = descriptor["clases"]
        self.synthetic = modo == "simulado"
        self.model_sha256 = "0" * 64  # Convencion del detector simulado de P5-14.
        self.sesion = None
        self.nombre_entrada = "images"
        self.control = None
        self.watchdog = None
        self.run_id = "benchmark-local"
        opciones_sesion = None
        if self.synthetic:
            self.rgb = np.random.default_rng(42).integers(0, 256, (296, 400, 3), dtype=np.uint8)
            entrada = {
                "origen": "RGB sintetico seed=42",
                "sha256_rgb": hashlib.sha256(self.rgb.tobytes()).hexdigest(),
                "archivo": None,
            }
            pesos = {"cargados": False, "bytes": None, "sha256": None}
        else:
            # Solo se abre ONNX al solicitar explicitamente modo real. Nunca en pruebas simuladas.
            assert imagen is not None
            self.rgb = leer_imagen(imagen)
            entrada = {"origen": "imagen explicita", **referencia(imagen)}
            pesos = {"cargados": True, **referencia(self.config.modelo)}
            exigir(
                pesos["sha256"] == descriptor["sha256"], "SHA-256 de pesos distinto del descriptor"
            )
            import onnxruntime as ort

            opciones = {}
            if hilos is not None:
                personalizadas = ort.SessionOptions()
                personalizadas.intra_op_num_threads = hilos
                personalizadas.inter_op_num_threads = hilos
                opciones["sess_options"] = personalizadas
            self.sesion = ort.InferenceSession(
                str(self.config.modelo), providers=["CPUExecutionProvider"], **opciones
            )
            opciones_sesion = self.sesion.get_session_options()
            exigir(
                list(self.sesion.get_inputs()[0].shape)
                == [1, 3, self.config.tamano_entrada, self.config.tamano_entrada],
                "forma de entrada ONNX incompatible",
            )
            self.model_sha256 = pesos["sha256"]
            self.nombre_entrada = self.sesion.get_inputs()[0].name
        alto, ancho = self.rgb.shape[:2]
        self.metadatos = {
            **condiciones(),
            "modo": modo,
            "synthetic": self.synthetic,
            "evidencia": "SINTETICA_NO_MIDE_DETECTOR_REAL"
            if self.synthetic
            else "DETECTOR_CPU_LOCAL",
            "entrada": {**entrada, "ancho": ancho, "alto": alto, "bytes_rgb": self.rgb.nbytes},
            "pesos": pesos,
            "runtime_inferencia": "numpy: salida fabricada para pruebas"
            if self.synthetic
            else "onnxruntime CPUExecutionProvider",
            "hilos": {
                "modo": "no_aplica"
                if self.synthetic
                else "predeterminado"
                if hilos is None
                else "explicito",
                "solicitados": hilos,
                "intra_op": None if self.synthetic else opciones_sesion.intra_op_num_threads,
                "inter_op": None if self.synthetic else opciones_sesion.inter_op_num_threads,
                "misma_configuracion_que_detector": None if self.synthetic else hilos is None,
                "nota": "ONNX no ejecutado"
                if self.synthetic
                else (
                    "Sin SessionOptions, igual que DetectorONNX; "
                    "0 significa automatico, no un hilo."
                    if hilos is None
                    else "Experimento con hilos explicitos; no comparacion directa."
                ),
            },
            "providers_sesion": None if self.synthetic else self.sesion.get_providers(),
            "configuraciones": {
                "detector": referencia(detector),
                "politica": referencia(politica),
                "watchdog": referencia(watchdog),
                "descriptor": referencia(self.config.descriptor),
            },
            "implementaciones": {
                p: referencia(Path(__file__).with_name(p))
                for p in (
                    "benchmark.py",
                    "detector_onnx.py",
                    "contrato.py",
                    "politica.py",
                    "control.py",
                    "watchdog.py",
                )
            },
            "plazos": asdict(self.cfg_watchdog),
            "estado_politica": "continuo desde calentamiento; misma instancia en toda la corrida",
        }

    def abrir(self, salida: Path) -> None:
        inicio = time.perf_counter()
        self.reloj = lambda: (time.perf_counter() - inicio) * 1000
        self.control = AdaptadorVirtual(salida / "comandos.jsonl", self.run_id, self.reloj)
        self.watchdog = Watchdog(
            Politica(self.cfg_politica), self.control, self.reloj, self.cfg_watchdog, self.run_id
        )

    def preprocesar(self, intento: int) -> np.ndarray:
        self.intento = intento
        self.t_capture = self.reloj()
        tensor, self.escala = letterbox(self.rgb, self.config.tamano_entrada, self.config.relleno)
        return tensor

    def inferir(self, tensor: np.ndarray) -> np.ndarray:
        if self.sesion is not None:
            return np.asarray(self.sesion.run(None, {self.nombre_entrada: tensor})[0])
        anclas = sum((self.config.tamano_entrada // s) ** 2 for s in (8, 16, 32))
        salida = np.zeros((1, anclas, 5 + len(self.clases)), dtype=np.float32)
        if self.intento % 2:  # Alterna person central fabricada y negativa, nunca GT real.
            salida[0, 0, :5] = [26, 28, math.log(10), math.log(12), 0.9]
            salida[0, 0, 5] = 0.9
        return salida

    def posprocesar(self, salida: np.ndarray) -> list:
        alto, ancho = self.rgb.shape[:2]
        return decodificar(salida, self.escala, ancho, alto, self.config, self.clases)

    def _evento(self, detecciones: list, error: str | None = None):
        alto, ancho = self.rgb.shape[:2]
        return validar_evento(
            {
                "schema_version": "1.0",
                "run_id": self.run_id,
                "sequence_id": "BENCH",
                "frame_id": f"BENCH_f{self.intento:06d}",
                "t_capture_ms": self.t_capture,
                "image_path": self.metadatos["entrada"].get("archivo") or "sintetico_seed42.rgb",
                "image_sha256": self.metadatos["entrada"].get("sha256")
                or self.metadatos["entrada"].get("sha256_rgb"),
                "image_width": ancho,
                "image_height": alto,
                "model_sha256": self.model_sha256,
                "config_sha256": self.config.config_sha256,
                "synthetic": self.synthetic,
                "status": "error" if error else "ok",
                "error_msg": error,
                "detections": [{**asdict(d), "bbox": list(d.bbox)} for d in detecciones],
            }
        )

    def decidir(self, detecciones: list) -> None:
        evento = self._evento(detecciones)
        self.watchdog.tick()
        self.watchdog.procesar_evento(evento)

    def fallo(self, mensaje: str) -> None:
        self.watchdog.procesar_evento(self._evento([], error=mensaje))

    def cerrar(self) -> None:
        if self.control is not None:
            self.control.cerrar()


def resumir(filas: list[dict], contexto: dict) -> dict:
    """Recalculo sin modelo, imagen, reloj ni configuraciones externas mutables."""
    exigir(contexto.get("version") == VERSION, "version de contexto incompatible")
    parametros = contexto["parametros"]
    for clave in ("calentamientos", "ejecuciones", "max_intentos"):
        exigir(type(parametros[clave]) is int and parametros[clave] > 0, "conteos invalidos")
    exigir(len(filas) <= parametros["max_intentos"], "demasiados intentos")
    vistos = 0
    for fila in filas:
        fase = "calentamiento" if vistos < parametros["calentamientos"] else "medicion"
        exigir(fila["fase"] == fase, "orden de fases incompatible con calentamientos")
        if fila["fase"] == "calentamiento" and fila["estado"] == "ok":
            vistos += 1
    validas = [f for f in filas if f["fase"] == "medicion" and f["estado"] == "ok"]
    calentamientos = sum(f["fase"] == "calentamiento" and f["estado"] == "ok" for f in filas)
    exigir(calentamientos <= parametros["calentamientos"], "calentamientos sobrantes")
    exigir(len(validas) <= parametros["ejecuciones"], "mediciones sobrantes")
    completa = (
        calentamientos == parametros["calentamientos"] and len(validas) == parametros["ejecuciones"]
    )
    stats = {c: estadisticas([float(f[c]) for f in validas]) for c in (*ETAPAS, "total_local_ms")}
    total = stats["total_local_ms"]
    contraste = {}
    for nombre, plazo in contexto["condiciones"]["plazos"].items():
        contraste[nombre] = {"plazo_ms": plazo}
        for medida in ("p95_ms", "max_ms"):
            valor = total[medida]
            contraste[nombre][medida] = {
                "valor_ms": valor,
                "dentro_del_plazo": None if valor is None else valor <= plazo,
                "margen_ms": None if valor is None else plazo - valor,
            }
    return {
        "version": VERSION,
        "condiciones": contexto["condiciones"],
        "parametros": parametros,
        "completa": completa,
        "intentos_totales": len(filas),
        "calentamientos_validos_excluidos": calentamientos,
        "ejecuciones_validas": len(validas),
        "fallos": dict(Counter(f["fase"] for f in filas if f["estado"] == "error")),
        "fallos_totales": sum(f["estado"] == "error" for f in filas),
        "intentos_por_fase": dict(Counter(f["fase"] for f in filas)),
        "metodo_percentiles": "numpy.percentile(method='linear'); indice=(n-1)*q",
        "estadisticas": stats,
        "contraste_watchdog": contraste,
        "advertencias": [
            "Presupuesto local: no prueba seguridad fisica ni latencia de red/camara/motores.",
            "La etapa politica incluye evento, validacion, watchdog y adaptador virtual con flush.",
            "No se incluyen en estadisticas calentamientos ni fallos; consultar ambos registros.",
        ]
        + (
            ["SINTETICO: estos tiempos no son mediciones del detector ONNX."]
            if contexto["condiciones"]["synthetic"]
            else []
        )
        + (
            [
                "HILOS EXPLICITOS: sesion distinta de DetectorONNX; "
                "no comparacion directa con recorrido."
            ]
            if contexto["condiciones"].get("hilos", {}).get("misma_configuracion_que_detector")
            is False
            else []
        )
        + ([] if completa else ["INCOMPLETO: no se alcanzaron las ejecuciones requeridas."]),
    }


def medir(
    cadena: Cadena,
    salida: Path,
    *,
    calentamientos: int = 10,
    ejecuciones: int = 100,
    max_intentos: int = 1000,
    reloj: Callable[[], float] | None = None,
) -> dict:
    for valor in (calentamientos, ejecuciones, max_intentos):
        exigir(type(valor) is int and valor > 0, "conteos deben ser enteros positivos")
    exigir(max_intentos >= calentamientos + ejecuciones, "limite de intentos insuficiente")
    exigir(
        not salida.exists() or all(p.name in (".gitkeep", "README.md") for p in salida.iterdir()),
        "la salida debe estar vacia; no se sobrescriben corridas",
    )
    salida.mkdir(parents=True, exist_ok=True)
    clock = reloj or time.perf_counter
    contexto = {
        "version": VERSION,
        "condiciones": cadena.metadatos,
        "parametros": {
            "calentamientos": calentamientos,
            "ejecuciones": ejecuciones,
            "max_intentos": max_intentos,
            "regla": "se requieren calentamientos validos; todo intento fallido se conserva",
        },
    }
    escribir_json(salida / "contexto.json", contexto)
    filas = []
    calentadas = medidas = 0
    interrumpido = False
    try:
        cadena.abrir(salida)
        with (
            (salida / "tiempos.csv").open("x", encoding="utf-8", newline="") as tiempos,
            (salida / "fallos.csv").open("x", encoding="utf-8", newline="") as fallos,
        ):
            writers = [csv.DictWriter(f, COLUMNAS, lineterminator="\n") for f in (tiempos, fallos)]
            for w in writers:
                w.writeheader()
            while medidas < ejecuciones and len(filas) < max_intentos:
                fase = "calentamiento" if calentadas < calentamientos else "medicion"
                fila = dict.fromkeys(COLUMNAS, "")
                fila.update(intento=len(filas) + 1, fase=fase, estado="ok")
                valor = fila["intento"]
                inicio = previo = clock()
                for columna, funcion in zip(
                    ETAPAS,
                    (
                        cadena.preprocesar,
                        cadena.inferir,
                        cadena.posprocesar,
                        cadena.decidir,
                    ),
                    strict=True,
                ):
                    try:
                        valor = funcion(valor)
                    except (Exception, KeyboardInterrupt) as exc:
                        fila.update(
                            estado="error",
                            etapa_fallo=columna,
                            error=f"{type(exc).__name__}: {exc}",
                        )
                        interrumpido = isinstance(exc, KeyboardInterrupt)
                    fin = clock()
                    exigir(math.isfinite(fin) and fin >= previo, "reloj no finito o retrocede")
                    fila[columna] = (fin - previo) * 1000
                    previo = fin
                    if fila["estado"] == "error":
                        break
                fila["total_local_ms"] = (previo - inicio) * 1000
                writers[0].writerow(fila)
                tiempos.flush()
                filas.append(fila)
                if fila["estado"] == "error":
                    writers[1].writerow(fila)
                    fallos.flush()
                    cadena.fallo(fila["error"])
                elif fase == "calentamiento":
                    calentadas += 1
                else:
                    medidas += 1
                if interrumpido:
                    break
    finally:
        cadena.cerrar()
    informe = resumir(filas, contexto)
    informe["archivos"] = {
        p: referencia(salida / p) for p in ("contexto.json", "tiempos.csv", "fallos.csv")
    }
    escribir_json(salida / "resumen.json", informe)
    return informe


def leer_filas(ruta: Path) -> list[dict]:
    with ruta.open(encoding="utf-8", newline="") as archivo:
        reader = csv.DictReader(archivo)
        exigir(tuple(reader.fieldnames or ()) == COLUMNAS, "cabecera CSV incompatible")
        filas = list(reader)
    for n, f in enumerate(filas, 1):
        exigir(None not in f and all(v is not None for v in f.values()), "fila CSV incompleta")
        exigir(f["intento"] == str(n), "intentos no consecutivos")
        exigir(f["fase"] in ("calentamiento", "medicion"), "fase desconocida")
        exigir(f["estado"] in ("ok", "error"), "estado desconocido")
        fallo = f["estado"] == "error"
        exigir(bool(f["error"]) == fallo, "error/estado incoherentes")
        exigir(f["etapa_fallo"] in ETAPAS if fallo else not f["etapa_fallo"], "etapa invalida")
        ultimo = ETAPAS.index(f["etapa_fallo"]) if fallo else len(ETAPAS) - 1
        valores = []
        for i, c in enumerate(ETAPAS):
            if i > ultimo:
                exigir(f[c] == "", "tiempo inventado tras el fallo")
                continue
            valor = float(f[c])
            exigir(math.isfinite(valor) and valor >= 0, "tiempo invalido")
            valores.append(valor)
        total = float(f["total_local_ms"])
        exigir(
            math.isfinite(total) and math.isclose(sum(valores), total, abs_tol=1e-7),
            "total inconsistente con etapas",
        )
    return filas


def recalcular(carpeta: Path) -> dict:
    original = json.loads((carpeta / "resumen.json").read_text(encoding="utf-8"))
    for nombre, ref in original["archivos"].items():
        exigir(nombre in ("contexto.json", "tiempos.csv", "fallos.csv"), "referencia ajena")
        exigir(referencia(carpeta / nombre) == ref, f"archivo alterado: {nombre}")
    exigir(
        set(original["archivos"]) == {"contexto.json", "tiempos.csv", "fallos.csv"},
        "referencias incompletas",
    )
    filas = leer_filas(carpeta / "tiempos.csv")
    with (carpeta / "fallos.csv").open(encoding="utf-8", newline="") as archivo:
        lector = csv.DictReader(archivo)
        exigir(tuple(lector.fieldnames or ()) == COLUMNAS, "cabecera de fallos invalida")
        exigir(list(lector) == [f for f in filas if f["estado"] == "error"], "fallos no coinciden")
    contexto = json.loads((carpeta / "contexto.json").read_text(encoding="utf-8"))
    resultado = resumir(filas, contexto)
    resultado["archivos"] = original["archivos"]
    return resultado


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--modo", choices=("simulado", "real"), default="simulado")
    parser.add_argument("--imagen", type=Path)
    parser.add_argument("--detector-config", type=Path, default=RAIZ / "config/detector.yaml")
    parser.add_argument("--politica-config", type=Path, default=RAIZ / "config/politica.yaml")
    parser.add_argument("--watchdog-config", type=Path, default=RAIZ / "config/watchdog.yaml")
    parser.add_argument(
        "--hilos",
        type=int,
        help="Hilos intra/inter explicitos; sin opcion usa los valores de DetectorONNX",
    )
    parser.add_argument("--calentamientos", type=int, default=10)
    parser.add_argument("--ejecuciones", type=int, default=100)
    parser.add_argument("--max-intentos", type=int, default=1000)
    parser.add_argument("--salida", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        cadena = CadenaDetector(
            modo=args.modo,
            detector=args.detector_config,
            politica=args.politica_config,
            watchdog=args.watchdog_config,
            imagen=args.imagen,
            hilos=args.hilos,
        )
        informe = medir(
            cadena,
            args.salida,
            calentamientos=args.calentamientos,
            ejecuciones=args.ejecuciones,
            max_intentos=args.max_intentos,
        )
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(
        f"{informe['condiciones']['evidencia']}: {informe['ejecuciones_validas']} validas; "
        f"{informe['intentos_totales']} intentos -> {args.salida}"
    )
    return 0 if informe["completa"] else 1


if __name__ == "__main__":
    sys.exit(main())
