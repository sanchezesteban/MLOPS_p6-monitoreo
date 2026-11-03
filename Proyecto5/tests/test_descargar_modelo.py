"""Descarga de pesos (P5-03): verifica SHA-256 y no deja archivo si no coincide. Sin red."""

from __future__ import annotations

import hashlib
from pathlib import Path

import certifi
import pytest
import yaml

import descargar_modelo
from descargar_modelo import DESCRIPTOR, contexto_tls, leer_descriptor, main

POLITICA = Path(__file__).resolve().parents[1] / "config" / "politica.yaml"
CONTENIDO = b"pesos-falsos-de-prueba" * 100


def _descriptor(tmp_path: Path, origen: Path, sha256: str, tamano: int) -> Path:
    ruta = tmp_path / "descriptor.yaml"
    data = {"archivo": "modelo.onnx", "url": origen.as_uri(), "bytes": tamano, "sha256": sha256}
    ruta.write_text(yaml.safe_dump(data), encoding="utf-8")
    return ruta


@pytest.fixture
def origen(tmp_path: Path) -> Path:
    ruta = tmp_path / "origen.onnx"
    ruta.write_bytes(CONTENIDO)
    return ruta


def test_descarga_y_verifica(tmp_path, origen, capsys):
    sha = hashlib.sha256(CONTENIDO).hexdigest()
    desc = _descriptor(tmp_path, origen, sha, len(CONTENIDO))
    destino = tmp_path / "destino"
    assert main(["--destino", str(destino), "--descriptor", str(desc)]) == 0
    assert (destino / "modelo.onnx").read_bytes() == CONTENIDO
    assert sha in capsys.readouterr().out


def test_hash_distinto_sale_con_1_y_no_deja_archivo(tmp_path, origen):
    desc = _descriptor(tmp_path, origen, "0" * 64, len(CONTENIDO))
    destino = tmp_path / "destino"
    assert main(["--destino", str(destino), "--descriptor", str(desc)]) == 1
    assert list(destino.iterdir()) == []


def test_tamano_distinto_sale_con_1(tmp_path, origen):
    sha = hashlib.sha256(CONTENIDO).hexdigest()
    desc = _descriptor(tmp_path, origen, sha, len(CONTENIDO) + 1)
    assert main(["--destino", str(tmp_path / "d"), "--descriptor", str(desc)]) == 1


def test_archivo_presente_con_hash_correcto_no_se_descarga(tmp_path, origen, capsys):
    sha = hashlib.sha256(CONTENIDO).hexdigest()
    desc = _descriptor(tmp_path, origen, sha, len(CONTENIDO))
    destino = tmp_path / "destino"
    destino.mkdir()
    (destino / "modelo.onnx").write_bytes(CONTENIDO)
    origen.unlink()  # si intentara descargar, fallaria
    assert main(["--destino", str(destino), "--descriptor", str(desc)]) == 0
    assert "ya presente" in capsys.readouterr().out


def test_archivo_presente_corrupto_se_reemplaza(tmp_path, origen):
    sha = hashlib.sha256(CONTENIDO).hexdigest()
    desc = _descriptor(tmp_path, origen, sha, len(CONTENIDO))
    destino = tmp_path / "destino"
    destino.mkdir()
    (destino / "modelo.onnx").write_bytes(b"corrupto")
    assert main(["--destino", str(destino), "--descriptor", str(desc)]) == 0
    assert (destino / "modelo.onnx").read_bytes() == CONTENIDO


def test_url_inexistente_sale_con_2(tmp_path):
    desc = _descriptor(tmp_path, tmp_path / "no-existe.onnx", "0" * 64, 1)
    assert main(["--destino", str(tmp_path / "d"), "--descriptor", str(desc)]) == 2


def test_descriptor_sin_sha_valido_sale_con_2(tmp_path, origen):
    desc = _descriptor(tmp_path, origen, "ABC", 1)
    assert main(["--destino", str(tmp_path / "d"), "--descriptor", str(desc)]) == 2


def test_descriptor_real_es_publico_y_tiene_80_clases_coco():
    d = leer_descriptor(DESCRIPTOR)
    assert d["url"].startswith("https://github.com/")
    assert d["licencia"] == "Apache-2.0"
    assert len(d["clases"]) == 80


def test_clases_obstaculo_coinciden_con_la_politica_y_con_su_indice_coco():
    d = leer_descriptor(DESCRIPTOR)
    politica = yaml.safe_load(POLITICA.read_text(encoding="utf-8"))
    obstaculos = {c["class_name"]: c["class_id"] for c in d["clases_obstaculo"]}
    assert set(obstaculos) == set(politica["clases_obstaculo"])
    for nombre, indice in obstaculos.items():
        assert d["clases"][indice] == nombre


@pytest.mark.parametrize(
    ("entorno", "esperado"),
    [
        ({}, "certifi"),
        ({"REQUESTS_CA_BUNDLE": "ca_requests.pem"}, "ca_requests.pem"),
        ({"SSL_CERT_FILE": "ca_ssl.pem", "REQUESTS_CA_BUNDLE": "ca_requests.pem"}, "ca_ssl.pem"),
    ],
)
def test_raices_tls_respetan_el_proxy(monkeypatch, entorno, esperado):
    for var in ("SSL_CERT_FILE", "REQUESTS_CA_BUNDLE"):
        monkeypatch.delenv(var, raising=False)
    for var, valor in entorno.items():
        monkeypatch.setenv(var, valor)
    usados = []
    monkeypatch.setattr(
        descargar_modelo.ssl, "create_default_context", lambda cafile: usados.append(cafile)
    )
    contexto_tls()
    assert usados == [certifi.where() if esperado == "certifi" else esperado]


def test_ca_del_entorno_inexistente_sale_con_2(tmp_path, origen, monkeypatch, capsys):
    monkeypatch.setenv("SSL_CERT_FILE", str(tmp_path / "no-existe.pem"))
    desc = _descriptor(tmp_path, origen, hashlib.sha256(CONTENIDO).hexdigest(), len(CONTENIDO))
    assert main(["--destino", str(tmp_path / "d"), "--descriptor", str(desc)]) == 2
    assert not (tmp_path / "d" / "modelo.onnx").exists()
    assert "no-existe.pem" in capsys.readouterr().err
