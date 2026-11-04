"""Runner de casos C01-C10: carga, replay, requisitos y codigo de salida."""

from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path

import pytest
import yaml

from p5.casos import (
    CasoInvalidoError,
    InsumoFaltanteError,
    Paso,
    cargar_caso,
    cargar_expectativa,
    main,
)
from p5.contrato import validar_evento

RAIZ = Path(__file__).resolve().parents[1]
CASOS = RAIZ / "casos"
CONFIG = RAIZ / "config" / "politica.yaml"
HASH = "0" * 64


class EjecutorGuionizado:
    """Ejecutor de prueba: devuelve las acciones del guion, sin politica real."""

    def __init__(self, guion: dict[str, str]) -> None:
        self.guion = guion
        self.t_ms = 0.0

    def avanzar(self, t_ms: float) -> None:
        self.t_ms = float(t_ms)

    def _comando(self, accion: str, razon: str = "prueba") -> dict:
        mueve = accion != "STOP"
        return {
            "action": accion,
            "speed": 0.4 if mueve else 0.0,
            "steering": 0.0,
            "reason": razon,
            "t_command_ms": self.t_ms,
            "valid_until_ms": self.t_ms + 300 if mueve else None,
            "error": None,
        }

    def cuadro(self, evento) -> Paso:
        accion = self.guion.get(evento.frame_id, "STOP")
        razon = "cuadro_vencido" if evento.status == "stale" else "prueba"
        return Paso(evento.frame_id, "cuadro", self.t_ms, self._comando(accion, razon))

    def control(self, evento: dict) -> Paso:
        tipo = evento["tipo"]
        paso_id = evento["id"]
        if tipo == "cierre":
            return Paso(
                paso_id,
                "cierre",
                self.t_ms,
                self._comando("STOP", "shutdown"),
            )
        return Paso(paso_id, tipo, self.t_ms, self._comando(self.guion.get(paso_id, "STOP"), tipo))

    def fallo(self, t_ms: float, razon: str, paso_id: str) -> Paso:
        self.t_ms = t_ms
        comando = self._comando("STOP", "error_percepcion")
        return Paso(paso_id, "cuadro_invalido", t_ms, comando, error=razon)

    def cerrar(self) -> None:
        return


def fabrica(guion: dict[str, str]):
    def crear(caso, config, control_config, log_path, run_id):
        return EjecutorGuionizado(guion)

    return crear


def _evento(frame_id: str, t_ms: float, *, status: str = "ok", detections=None) -> dict:
    error = None if status == "ok" else f"falla {status} de prueba"
    return {
        "schema_version": "1.0",
        "run_id": "run-seq01",
        "sequence_id": "seq01",
        "frame_id": frame_id,
        "t_capture_ms": t_ms,
        "image_path": None if status == "error" else f"cuadros/{frame_id}.jpg",
        "image_sha256": None if status == "error" else HASH,
        "image_width": None if status == "error" else 640,
        "image_height": None if status == "error" else 480,
        "model_sha256": HASH,
        "config_sha256": HASH,
        "status": status,
        "error_msg": error,
        "synthetic": False,
        "detections": detections or [],
    }


def _escribir_caso_real(base: Path, *, con_eventos: bool = True) -> Path:
    casos = base / "casos"
    (casos / "expectativas").mkdir(parents=True)
    (base / "datos" / "eventos").mkdir(parents=True)
    (casos / "C01.yaml").write_text(
        yaml.safe_dump(
            {
                "id": "C01",
                "nombre": "Via libre de prueba",
                "tipo": "real",
                "estado_inicial": "INICIO",
                "entrada": {
                    "secuencia": "seq01",
                    "manifiesto": "datos/manifiesto.csv",
                    "eventos": "datos/eventos/seq01.jsonl",
                },
                "expectativa": "expectativas/C01.yaml",
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (casos / "expectativas" / "C01.yaml").write_text(
        yaml.safe_dump(
            {
                "id": "C01",
                "secuencia": "seq01",
                "acciones_por_cuadro": "cuadros.csv",
                "estados_requeridos": ["libre", "centro"],
                "plazo_reaccion_cuadros": 0,
                "requisitos": [{"tipo": "movimiento_minimo", "min_cuadros": 1}],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    with (casos / "expectativas" / "cuadros.csv").open("w", encoding="utf-8", newline="") as f:
        escritor = csv.DictWriter(
            f, fieldnames=["frame_id", "estado_via", "zonas_en_riesgo", "acciones_permitidas"]
        )
        escritor.writeheader()
        escritor.writerow(
            {
                "frame_id": "seq01_f0001",
                "estado_via": "libre",
                "zonas_en_riesgo": "",
                "acciones_permitidas": "FORWARD|STEER_LEFT|STEER_RIGHT|STOP",
            }
        )
        escritor.writerow(
            {
                "frame_id": "seq01_f0002",
                "estado_via": "centro",
                "zonas_en_riesgo": "centro",
                "acciones_permitidas": "STOP",
            }
        )
        escritor.writerow(
            {
                "frame_id": "seq01_f0003",
                "estado_via": "libre",
                "zonas_en_riesgo": "",
                "acciones_permitidas": "FORWARD|STEER_LEFT|STEER_RIGHT|STOP",
            }
        )
    if con_eventos:
        eventos = [
            _evento("seq01_f0001", 0),
            _evento("seq01_f0002", 100),
            _evento("seq01_f0003", 200),
        ]
        (base / "datos" / "eventos" / "seq01.jsonl").write_text(
            "\n".join(json.dumps(e) for e in eventos) + "\n", encoding="utf-8"
        )
    return casos


@pytest.mark.parametrize(
    ("caso_id", "guion"),
    [
        (
            "C08",
            {
                "c08_f0001": "STOP",
                "c08_f0002": "STOP",
                "c08_f0003": "FORWARD",
                "watchdog_1": "STOP",
                "c08_f0004": "STOP",
                "watchdog_2": "STOP",
            },
        ),
        (
            "C09",
            {
                "c09_f0001": "STOP",
                "c09_f0002": "STOP",
                "c09_f0003": "FORWARD",
                "c09_f0004": "STOP",
                "c09_f0005": "STOP",
            },
        ),
        (
            "C10",
            {
                "c10_f0001": "STOP",
                "c10_f0002": "STOP",
                "c10_f0003": "FORWARD",
                "emergencia_1": "STOP",
                "c10_f0004": "STOP",
                "c10_f0005": "STOP",
                "c10_f0006": "STOP",
                "c10_f0007": "STOP",
                "c10_f0008": "FORWARD",
                "cierre_1": "STOP",
            },
        ),
    ],
)
def test_casos_sinteticos_del_repo_pasan(tmp_path, caso_id, guion):
    codigo = main(
        [
            "--casos",
            str(CASOS),
            "--config",
            str(CONFIG),
            "--salida",
            str(tmp_path),
            "--caso",
            caso_id,
        ],
        fabrica_ejecutor=fabrica(guion),
    )
    resumen = json.loads((tmp_path / "resumen.json").read_text(encoding="utf-8"))
    assert codigo == 0
    assert resumen["resultado"] == "pass"
    assert resumen["resumen"]["pass"] == 1
    assert resumen["casos"][0]["comandos"].endswith("comandos.jsonl")
    assert (tmp_path / caso_id / "comandos.jsonl").is_file()


def test_casos_sinteticos_con_politica_y_adaptador_reales(tmp_path):
    """Se salta mientras #73/#74 no estén mergeados; luego corre en el CI de P5."""
    pytest.importorskip("p5.politica")
    pytest.importorskip("p5.control")
    # Solo los casos sinteticos: los reales (C01-C05, C07) necesitan datos/eventos/<seq>.jsonl.
    casos = tmp_path / "casos"
    (casos / "expectativas").mkdir(parents=True)
    for ruta in sorted(CASOS.glob("C*.yaml")):
        datos = yaml.safe_load(ruta.read_text(encoding="utf-8"))
        if datos["tipo"] == "sintetico":
            shutil.copy(ruta, casos / ruta.name)
            shutil.copy(CASOS / datos["expectativa"], casos / datos["expectativa"])
    codigo = main(
        [
            "--casos",
            str(casos),
            "--config",
            str(CONFIG),
            "--salida",
            str(tmp_path / "salida"),
        ],
    )
    resumen = json.loads((tmp_path / "salida" / "resumen.json").read_text(encoding="utf-8"))
    assert codigo == 0
    assert resumen["resumen"]["pass"] == 4  # C06 (P5-15) y C08-C10


def test_caso_sintetico_estilo_c06_compara_cuadros_y_velocidad(tmp_path):
    casos = tmp_path / "casos"
    (casos / "expectativas").mkdir(parents=True)
    (casos / "C06.yaml").write_text(
        yaml.safe_dump(
            {
                "id": "C06",
                "nombre": "Estilo C06",
                "tipo": "sintetico",
                "estado_inicial": "INICIO",
                "entrada": {
                    "sequence_id": "c06",
                    "run_id": "run-c06",
                    "image_width": 640,
                    "image_height": 480,
                    "eventos": [
                        {"tipo": "cuadro", "frame_id": "c06_f0001", "t_capture_ms": 0},
                        {"tipo": "cuadro", "frame_id": "c06_f0002", "t_capture_ms": 100},
                    ],
                },
                "expectativa": "expectativas/C06.yaml",
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (casos / "expectativas" / "C06.yaml").write_text(
        yaml.safe_dump(
            {
                "id": "C06",
                "cuadros": [
                    {"frame_id": "c06_f0001", "acciones_permitidas": ["FORWARD", "STOP"]},
                    {
                        "frame_id": "c06_f0002",
                        "acciones_permitidas": ["FORWARD"],
                        "velocidad_max": 0.4,
                    },
                ],
                "requisitos": [{"tipo": "movimiento_minimo", "min_cuadros": 1}],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    codigo = main(
        ["--casos", str(casos), "--config", str(CONFIG), "--salida", str(tmp_path / "salida")],
        fabrica_ejecutor=fabrica({"c06_f0001": "STOP", "c06_f0002": "FORWARD"}),
    )
    resumen = json.loads((tmp_path / "salida" / "resumen.json").read_text(encoding="utf-8"))
    assert codigo == 0
    assert resumen["casos"][0]["estado"] == "pass"


def test_caso_real_reproduce_eventos_y_compara_csv(tmp_path):
    casos = _escribir_caso_real(tmp_path)
    codigo = main(
        ["--casos", str(casos), "--config", str(CONFIG), "--salida", str(tmp_path / "salida")],
        fabrica_ejecutor=fabrica(
            {"seq01_f0001": "STOP", "seq01_f0002": "STOP", "seq01_f0003": "FORWARD"}
        ),
    )
    resumen = json.loads((tmp_path / "salida" / "resumen.json").read_text(encoding="utf-8"))
    assert codigo == 0
    assert resumen["casos"][0]["tipo"] == "real"
    assert resumen["casos"][0]["pasos"] == 3


def test_caso_real_sin_eventos_falla_con_insumo_faltante(tmp_path):
    casos = _escribir_caso_real(tmp_path, con_eventos=False)
    codigo = main(
        ["--casos", str(casos), "--config", str(CONFIG), "--salida", str(tmp_path / "salida")],
        fabrica_ejecutor=fabrica({}),
    )
    resumen = json.loads((tmp_path / "salida" / "resumen.json").read_text(encoding="utf-8"))
    assert codigo == 1
    assert resumen["casos"][0]["estado"] == "error"
    assert "falta" in resumen["casos"][0]["error"]


def test_expectativa_cambiada_a_proposito_sale_con_codigo_1(tmp_path):
    casos = tmp_path / "casos"
    shutil.copytree(CASOS, casos)
    ruta = casos / "expectativas" / "C08.yaml"
    texto = ruta.read_text(encoding="utf-8")
    ruta.write_text(
        texto.replace(
            "{id: c08_f0004, acciones_permitidas: [STOP], motivo: cuadro_vencido}",
            "{id: c08_f0004, acciones_permitidas: [FORWARD], motivo: cuadro_vencido}",
        ),
        encoding="utf-8",
    )
    guion = {
        "c08_f0001": "STOP",
        "c08_f0002": "STOP",
        "c08_f0003": "FORWARD",
        "watchdog_1": "STOP",
        "c08_f0004": "STOP",
        "watchdog_2": "STOP",
    }
    codigo = main(
        [
            "--casos",
            str(casos),
            "--config",
            str(CONFIG),
            "--salida",
            str(tmp_path / "salida"),
            "--caso",
            "C08",
        ],
        fabrica_ejecutor=fabrica(guion),
    )
    resumen = json.loads((tmp_path / "salida" / "resumen.json").read_text(encoding="utf-8"))
    assert codigo == 1
    assert resumen["casos"][0]["estado"] == "fail"
    assert any("c08_f0004" in fallo for fallo in resumen["casos"][0]["fallos"])


def test_watchdog_que_no_para_falla(tmp_path):
    guion = {
        "c08_f0001": "STOP",
        "c08_f0002": "STOP",
        "c08_f0003": "FORWARD",
        "watchdog_1": "FORWARD",
        "c08_f0004": "STOP",
        "watchdog_2": "STOP",
    }
    codigo = main(
        [
            "--casos",
            str(CASOS),
            "--config",
            str(CONFIG),
            "--salida",
            str(tmp_path),
            "--caso",
            "C08",
        ],
        fabrica_ejecutor=fabrica(guion),
    )
    resumen = json.loads((tmp_path / "resumen.json").read_text(encoding="utf-8"))
    assert codigo == 1
    assert any("watchdog_1" in fallo for fallo in resumen["casos"][0]["fallos"])


def test_rearme_sin_movimiento_falla(tmp_path):
    guion = {
        "c10_f0001": "STOP",
        "c10_f0002": "STOP",
        "c10_f0003": "FORWARD",
        "emergencia_1": "STOP",
        "c10_f0004": "STOP",
        "c10_f0005": "STOP",
        "c10_f0006": "STOP",
        "c10_f0007": "STOP",
        "c10_f0008": "STOP",
        "cierre_1": "STOP",
    }
    codigo = main(
        [
            "--casos",
            str(CASOS),
            "--config",
            str(CONFIG),
            "--salida",
            str(tmp_path),
            "--caso",
            "C10",
        ],
        fabrica_ejecutor=fabrica(guion),
    )
    resumen = json.loads((tmp_path / "resumen.json").read_text(encoding="utf-8"))
    assert codigo == 1
    assert any("reanudo" in fallo for fallo in resumen["casos"][0]["fallos"])


def test_cargar_caso_exige_expectativa_existente(tmp_path):
    ruta = tmp_path / "C99.yaml"
    ruta.write_text(
        yaml.safe_dump(
            {
                "id": "C99",
                "nombre": "Sin expectativa",
                "tipo": "sintetico",
                "estado_inicial": "INICIO",
                "entrada": {"sequence_id": "c99", "eventos": []},
                "expectativa": "expectativas/C99.yaml",
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(CasoInvalidoError, match="no existe la expectativa"):
        cargar_caso(ruta)


def test_expectativa_usa_ruta_relativa_para_la_evidencia():
    caso = cargar_caso(CASOS / "C01.yaml")
    expectativa = cargar_expectativa(caso)

    assert not expectativa.ruta.is_absolute()
    assert expectativa.ruta == Path("casos/expectativas/C01.yaml")


def test_evento_sintetico_invalido_por_contrato_se_registra(tmp_path):
    casos = tmp_path / "casos"
    (casos / "expectativas").mkdir(parents=True)
    (casos / "C99.yaml").write_text(
        yaml.safe_dump(
            {
                "id": "C99",
                "nombre": "Evento invalido",
                "tipo": "sintetico",
                "estado_inicial": "INICIO",
                "entrada": {
                    "sequence_id": "c99",
                    "image_width": 640,
                    "image_height": 480,
                    "eventos": [
                        {
                            "tipo": "cuadro",
                            "frame_id": "c99_f0001",
                            "t_capture_ms": 0,
                            "detections": [
                                {
                                    "class_name": "person",
                                    "class_id": 0,
                                    "confidence": float("nan"),
                                    "bbox": [1, 2, 3, 4],
                                }
                            ],
                        }
                    ],
                },
                "expectativa": "expectativas/C99.yaml",
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (casos / "expectativas" / "C99.yaml").write_text(
        yaml.safe_dump(
            {
                "id": "C99",
                "pasos": [
                    {
                        "id": "c99_f0001",
                        "acciones_permitidas": ["STOP"],
                        "permitir_error": True,
                    }
                ],
                "requisitos": [{"tipo": "evento_invalido_rechazado", "frame_id": "c99_f0001"}],
            }
        ),
        encoding="utf-8",
    )
    codigo = main(
        ["--casos", str(casos), "--config", str(CONFIG), "--salida", str(tmp_path / "salida")],
        fabrica_ejecutor=fabrica({}),
    )
    resumen = json.loads((tmp_path / "salida" / "resumen.json").read_text(encoding="utf-8"))
    assert codigo == 0
    assert resumen["casos"][0]["estado"] == "pass"
    paso = json.loads((tmp_path / "salida" / "C99" / "comandos.jsonl").read_text(encoding="utf-8"))
    assert "no finito" in paso["error"] or "inv" in paso["error"]


def test_eventos_reales_invalidos_se_rechazan(tmp_path):
    casos = _escribir_caso_real(tmp_path)
    ruta = tmp_path / "datos" / "eventos" / "seq01.jsonl"
    ruta.write_text(
        json.dumps({"schema_version": "1.0", "run_id": "run-seq01"}) + "\n",
        encoding="utf-8",
    )
    codigo = main(
        ["--casos", str(casos), "--config", str(CONFIG), "--salida", str(tmp_path / "salida")],
        fabrica_ejecutor=fabrica({}),
    )
    resumen = json.loads((tmp_path / "salida" / "resumen.json").read_text(encoding="utf-8"))
    assert codigo == 1
    assert resumen["casos"][0]["estado"] == "error"
    assert "evento invalido" in resumen["casos"][0]["error"]


def test_validar_evento_del_fixture_real():
    evento = validar_evento(_evento("seq01_f0001", 0))
    assert evento.sequence_id == "seq01"
    assert evento.synthetic is False


def test_insumo_faltante_es_excepcion_propia():
    assert issubclass(InsumoFaltanteError, RuntimeError)
