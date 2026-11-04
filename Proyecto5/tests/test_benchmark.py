"""P5-08: resultados manuales y sesiones falsas, sin ONNX real ni fotografias."""

from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from types import SimpleNamespace

import numpy as np
import pytest
import yaml
from PIL import Image

from p5.benchmark import (
    ETAPAS,
    RAIZ,
    BenchmarkError,
    CadenaDetector,
    estadisticas,
    leer_filas,
    main,
    medir,
    recalcular,
    referencia,
)


class Reloj:
    def __init__(self):
        self.ahora = 0.0

    def __call__(self):
        return self.ahora

    def avanzar(self, ms):
        self.ahora += ms / 1000


class CadenaFalsa:
    def __init__(self, fallos=(), etapa="inferencia", interrumpir=False):
        self.reloj = Reloj()
        self.fallos = fallos
        self.etapa = etapa
        self.interrumpir = interrumpir
        self.cerrada = False
        self.avisos = []
        self.metadatos = {
            "synthetic": True,
            "evidencia": "SINTETICA",
            "plazos": {"plazo_reaccion_ms": 10, "max_edad_ms": 9, "vencimiento_ms": 8},
        }

    def abrir(self, salida):
        self.salida = salida

    def paso(self, nombre, ms):
        # El calentamiento es 100 veces mas lento; no debe contaminar percentiles.
        self.reloj.avanzar(ms * (100 if self.intento <= 10 else 1))
        if self.intento in self.fallos and nombre == self.etapa:
            if self.interrumpir:
                raise KeyboardInterrupt
            raise RuntimeError("fallo simulado")

    def preprocesar(self, intento):
        self.intento = intento
        self.paso("preprocesamiento", 1)

    def inferir(self, tensor):
        self.paso("inferencia", 2)

    def posprocesar(self, salida):
        self.paso("posprocesamiento", 3)

    def decidir(self, detecciones):
        self.paso("politica_adaptador", 4)

    def fallo(self, mensaje):
        self.avisos.append(mensaje)

    def cerrar(self):
        self.cerrada = True


def ejecutar(tmp_path, cadena=None, **kwargs):
    cadena = cadena or CadenaFalsa()
    salida = tmp_path / "mediciones"
    return cadena, salida, medir(cadena, salida, reloj=cadena.reloj, **kwargs)


def test_diez_calentamientos_excluidos_y_cien_validas(tmp_path):
    cadena, salida, r = ejecutar(tmp_path)
    filas = leer_filas(salida / "tiempos.csv")
    assert cadena.cerrada and len(filas) == r["intentos_totales"] == 110
    assert r["calentamientos_validos_excluidos"] == 10
    assert r["ejecuciones_validas"] == 100 and r["completa"]
    for campo, esperado in zip((*ETAPAS, "total_local_ms"), (1, 2, 3, 4, 10), strict=True):
        assert r["estadisticas"][campo]["n"] == 100
        assert r["estadisticas"][campo]["p95_ms"] == pytest.approx(esperado)
    assert len((salida / "fallos.csv").read_text().splitlines()) == 1
    assert recalcular(salida) == r


@pytest.mark.parametrize(
    "etapa", ["preprocesamiento", "inferencia", "posprocesamiento", "politica_adaptador"]
)
def test_fallos_separados_no_ocultan_intentos_y_no_entran_en_stats(tmp_path, etapa):
    cadena, salida, r = ejecutar(tmp_path, CadenaFalsa(fallos={11}, etapa=etapa))
    assert r["completa"] and r["intentos_totales"] == 111
    assert r["fallos"] == {"medicion": 1} and len(cadena.avisos) == 1
    with (salida / "fallos.csv").open(newline="") as archivo:
        filas = list(csv.DictReader(archivo))
    assert len(filas) == 1 and filas[0]["etapa_fallo"] == etapa + "_ms"
    assert filas[0]["estado"] == "error"
    assert r["estadisticas"]["total_local_ms"]["p50_ms"] == pytest.approx(10)
    assert recalcular(salida) == r


def test_fallo_calentamiento_se_registra_y_se_reponen_diez_validos(tmp_path):
    _, salida, r = ejecutar(tmp_path, CadenaFalsa(fallos={2}))
    assert r["intentos_totales"] == 111 and r["fallos"] == {"calentamiento": 1}
    assert r["calentamientos_validos_excluidos"] == 10
    assert recalcular(salida) == r


def test_limite_de_intentos_guarda_informe_incompleto_y_cierra(tmp_path):
    cadena, salida, r = ejecutar(
        tmp_path, CadenaFalsa(fallos=set(range(11, 111))), max_intentos=110
    )
    assert cadena.cerrada and not r["completa"]
    assert r["ejecuciones_validas"] == 0 and r["intentos_totales"] == 110
    assert r["estadisticas"]["total_local_ms"]["p95_ms"] is None
    assert r["contraste_watchdog"]["max_edad_ms"]["p95_ms"]["dentro_del_plazo"] is None
    assert recalcular(salida) == r


def test_ctrl_c_conserva_fallo_parcial_y_cierra(tmp_path):
    cadena, salida, r = ejecutar(tmp_path, CadenaFalsa(fallos={11}, interrumpir=True))
    assert cadena.cerrada and not r["completa"] and r["intentos_totales"] == 11
    assert "KeyboardInterrupt" in (salida / "fallos.csv").read_text()


@pytest.mark.parametrize(
    "datos,p50,p95,maximo",
    [
        ([10], 10, 10, 10),
        ([0, 10], 5, 9.5, 10),
        (list(range(1, 101)), 50.5, 95.05, 100),
        ([4, 1, 3, 2], 2.5, 3.85, 4),
    ],
)
def test_percentiles_calculados_a_mano(datos, p50, p95, maximo):
    r = estadisticas(datos)
    assert r["p50_ms"] == pytest.approx(p50)
    assert r["p95_ms"] == pytest.approx(p95) and r["max_ms"] == maximo


@pytest.mark.parametrize("dato", [-1, float("nan"), float("inf")])
def test_estadisticas_invalidas(dato):
    with pytest.raises(BenchmarkError):
        estadisticas([dato])


def test_comparacion_plazos_inclusiva_y_excesos_visibles(tmp_path):
    _, _, r = ejecutar(tmp_path)
    c = r["contraste_watchdog"]
    assert c["plazo_reaccion_ms"]["p95_ms"]["valor_ms"] == pytest.approx(10)
    assert c["max_edad_ms"]["p95_ms"]["dentro_del_plazo"] is False
    assert c["vencimiento_ms"]["max_ms"]["margen_ms"] == pytest.approx(-2)


@pytest.mark.parametrize("nombre", ["tiempos.csv", "fallos.csv", "contexto.json"])
def test_recalculo_detecta_ediciones_de_entradas(tmp_path, nombre):
    _, salida, _ = ejecutar(tmp_path)
    with (salida / nombre).open("a") as archivo:
        archivo.write(" ")
    with pytest.raises(BenchmarkError, match="alterado"):
        recalcular(salida)


def test_recalculo_no_confia_en_estadisticas_del_resumen(tmp_path):
    _, salida, esperado = ejecutar(tmp_path)
    reporte = json.loads((salida / "resumen.json").read_text())
    reporte["estadisticas"]["total_local_ms"]["p95_ms"] = 999
    (salida / "resumen.json").write_text(json.dumps(reporte))
    assert recalcular(salida) == esperado


def test_no_sobrescribe_corridas_existentes(tmp_path):
    cadena, salida, _ = ejecutar(tmp_path)
    antes = (salida / "tiempos.csv").read_bytes()
    with pytest.raises(BenchmarkError, match="vacia"):
        medir(cadena, salida)
    assert (salida / "tiempos.csv").read_bytes() == antes


def test_mediciones_admite_readme_sin_modificarlo(tmp_path):
    salida = tmp_path / "mediciones"
    salida.mkdir()
    (salida / "README.md").write_text("Documentacion existente", encoding="utf-8")
    _, _, r = ejecutar(tmp_path)
    assert r["completa"]
    assert (salida / "README.md").read_text(encoding="utf-8") == "Documentacion existente"


@pytest.mark.parametrize(
    "cambio",
    [{"calentamientos": 0}, {"ejecuciones": -1}, {"max_intentos": 109}, {"ejecuciones": True}],
)
def test_conteos_invalidos_no_crean_salida(tmp_path, cambio):
    with pytest.raises(BenchmarkError):
        ejecutar(tmp_path, **cambio)
    assert not (tmp_path / "mediciones").exists()


def test_reloj_erroneo_cierra_recursos(tmp_path):
    cadena = CadenaFalsa()
    ticks = iter([1, 0])
    with pytest.raises(BenchmarkError, match="reloj"):
        medir(cadena, tmp_path / "mediciones", reloj=lambda: next(ticks))
    assert cadena.cerrada


def test_simulacion_integra_etapas_publicas_politica_y_control_sin_onnx(tmp_path, monkeypatch):
    import onnxruntime

    def prohibido(*args, **kwargs):
        pytest.fail("No se debe abrir una sesion ONNX en modo simulado")

    monkeypatch.setattr(onnxruntime, "InferenceSession", prohibido)
    cadena = CadenaDetector(
        modo="simulado",
        detector=RAIZ / "config/detector.yaml",
        politica=RAIZ / "config/politica.yaml",
        watchdog=RAIZ / "config/watchdog.yaml",
    )
    r = medir(cadena, tmp_path / "mediciones")
    assert r["completa"] and r["ejecuciones_validas"] == 100
    assert r["intentos_totales"] == 110 and r["fallos_totales"] == 0
    assert r["condiciones"]["synthetic"] and not r["condiciones"]["pesos"]["cargados"]
    assert r["condiciones"]["hilos"]["intra_op"] is None
    assert r["condiciones"]["plazos"] == {
        "plazo_reaccion_ms": 100,
        "max_edad_ms": 300,
        "vencimiento_ms": 250,
    }
    comandos = [
        json.loads(linea)
        for linea in (tmp_path / "mediciones/comandos.jsonl").read_text().splitlines()
    ]
    assert len(comandos) >= 111 and comandos[-1]["action"] == "STOP"
    assert comandos[-1]["event"] == "shutdown"
    assert all(c["synthetic"] for c in comandos[:-1])
    assert any(c["reason"] == "obstaculo_centro_riesgo" for c in comandos)
    assert recalcular(tmp_path / "mediciones") == r


def test_cli_simulada_y_script_recalculo(tmp_path, monkeypatch):
    salida = tmp_path / "mediciones"
    assert main(["--salida", str(salida)]) == 0
    script = RAIZ / "scripts/recalcular_benchmark.py"
    copia = tmp_path / "recalculado.json"
    r = subprocess.run(
        [sys.executable, str(script), "--mediciones", str(salida), "--salida", str(copia)],
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
    )
    assert r.returncode == 0, r.stderr
    assert json.loads(copia.read_text()) == json.loads((salida / "resumen.json").read_text())
    assert main(["--salida", str(salida)]) == 2


def test_real_sin_entrada_explicita_no_carga_modelo(tmp_path):
    assert main(["--modo", "real", "--salida", str(tmp_path / "x")]) == 2
    assert not (tmp_path / "x").exists()


def test_csv_invalido_rechazado_aun_si_se_actualiza_su_hash(tmp_path):
    _, salida, _ = ejecutar(tmp_path)
    ruta = salida / "tiempos.csv"
    filas = list(csv.DictReader(ruta.open()))
    filas[0]["total_local_ms"] = "9999"
    with ruta.open("w", newline="") as f:
        writer = csv.DictWriter(f, filas[0].keys(), lineterminator="\n")
        writer.writeheader()
        writer.writerows(filas)
    reporte = json.loads((salida / "resumen.json").read_text())
    reporte["archivos"]["tiempos.csv"] = referencia(ruta)
    (salida / "resumen.json").write_text(json.dumps(reporte))
    with pytest.raises(BenchmarkError, match="total"):
        recalcular(salida)


def test_salida_simulada_cruda_cumple_forma_y_finitud():
    cadena = CadenaDetector(
        modo="simulado",
        detector=RAIZ / "config/detector.yaml",
        politica=RAIZ / "config/politica.yaml",
        watchdog=RAIZ / "config/watchdog.yaml",
    )
    cadena.intento = 1
    salida = cadena.inferir(np.zeros((1, 3, 416, 416)))
    assert salida.shape == (1, 3549, 85) and np.isfinite(salida).all()


def insumos_falsos(tmp_path):
    """Solo archivos sinteticos de prueba; no pesos ni fotografias del proyecto."""
    modelo = tmp_path / "simulacion.onnx"
    modelo.write_bytes(b"NO ES UN MODELO; sesion falsa para probar el adaptador")
    descriptor = yaml.safe_load((RAIZ / "modelo/descriptor.yaml").read_text(encoding="utf-8"))
    descriptor["sha256"] = hashlib.sha256(modelo.read_bytes()).hexdigest()
    desc = tmp_path / "descriptor.yaml"
    desc.write_text(yaml.safe_dump(descriptor), encoding="utf-8")
    config = yaml.safe_load((RAIZ / "config/detector.yaml").read_text(encoding="utf-8"))
    config.update(modelo=str(modelo), descriptor=str(desc))
    ruta = tmp_path / "detector.yaml"
    ruta.write_text(yaml.safe_dump(config), encoding="utf-8")
    imagen = tmp_path / "entrada_sintetica.png"
    Image.new("RGB", (400, 296)).save(imagen)
    return ruta, imagen, modelo


def test_conexion_futura_cpu_hilos_y_etapas_solo_con_sesion_falsa(tmp_path, monkeypatch):
    import onnxruntime

    cfg, imagen, _ = insumos_falsos(tmp_path)
    usadas = {}

    class SesionFalsa:
        def __init__(self, ruta, *, sess_options, providers):
            usadas.update(
                hilos=sess_options.intra_op_num_threads,
                inter=sess_options.inter_op_num_threads,
                providers=providers,
            )

        def get_inputs(self):
            return [SimpleNamespace(name="images", shape=[1, 3, 416, 416])]

        def run(self, nombres, entrada):
            usadas["tensor"] = entrada["images"].shape
            return [np.zeros((1, 3549, 85), dtype=np.float32)]

    monkeypatch.setattr(onnxruntime, "InferenceSession", SesionFalsa)
    cadena = CadenaDetector(
        modo="real",
        detector=cfg,
        imagen=imagen,
        hilos=2,
        politica=RAIZ / "config/politica.yaml",
        watchdog=RAIZ / "config/watchdog.yaml",
    )
    cadena.abrir(tmp_path / "sesion_falsa")
    try:
        cadena.decidir(cadena.posprocesar(cadena.inferir(cadena.preprocesar(1))))
    finally:
        cadena.cerrar()
    assert usadas == {
        "hilos": 2,
        "inter": 2,
        "providers": ["CPUExecutionProvider"],
        "tensor": (1, 3, 416, 416),
    }
    assert cadena.metadatos["pesos"]["sha256"] == referencia(tmp_path / "simulacion.onnx")["sha256"]


def test_pesos_alterados_se_rechazan_antes_de_crear_sesion(tmp_path, monkeypatch):
    import onnxruntime

    cfg, imagen, modelo = insumos_falsos(tmp_path)
    modelo.write_bytes(b"alterado")
    monkeypatch.setattr(
        onnxruntime, "InferenceSession", lambda *a, **kw: pytest.fail("No abrir ONNX")
    )
    with pytest.raises(BenchmarkError, match="SHA-256"):
        CadenaDetector(
            modo="real",
            detector=cfg,
            imagen=imagen,
            politica=RAIZ / "config/politica.yaml",
            watchdog=RAIZ / "config/watchdog.yaml",
        )


def test_recalculo_no_permite_mediciones_antes_del_calentamiento(tmp_path):
    _, salida, _ = ejecutar(tmp_path)
    contexto = json.loads((salida / "contexto.json").read_text())
    contexto["parametros"]["calentamientos"] = 11
    (salida / "contexto.json").write_text(json.dumps(contexto))
    resumen = json.loads((salida / "resumen.json").read_text())
    resumen["archivos"]["contexto.json"] = referencia(salida / "contexto.json")
    (salida / "resumen.json").write_text(json.dumps(resumen))
    with pytest.raises(BenchmarkError, match="orden de fases"):
        recalcular(salida)
