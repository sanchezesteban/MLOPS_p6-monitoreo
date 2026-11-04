"""Casi duplicados por hash perceptual (pHash) para el conteo informativo de P5-06 (#58).

Adaptado de `Proyecto2/src/dataset_quality/analyzers/duplicates.py` (P2, analizador de
duplicados): mismas funciones `perceptual_hash`, `hamming` y `duplicate_groups` (union-find
sobre pares con distancia de Hamming <= umbral) y el mismo umbral por defecto de
`Proyecto2/quality.yaml` (`phash_hamming_distance: 5`). No se importa el modulo de P2 porque
arrastra sus modelos pydantic y su `CocoDataset`; aqui se trabaja con rutas.

Requiere `ImageHash` (`requirements-datos.txt`), que no esta en `requirements.txt`: el
detector, la politica y el recorrido no lo necesitan. La meta oficial de cuadros unicos se
cuenta por SHA-256; este pHash es informativo.
"""

from __future__ import annotations

from itertools import combinations
from pathlib import Path

UMBRAL_P2 = 5  # Proyecto2/quality.yaml: duplicates.phash_hamming_distance


def perceptual_hash(ruta: Path) -> int:
    """pHash de 64 bits como entero (igual que P2)."""
    import imagehash
    from PIL import Image

    with Image.open(ruta) as im:
        return int(str(imagehash.phash(im)), 16)


def hamming(a: int, b: int) -> int:
    return (a ^ b).bit_count()


def pares(hashes: dict[str, int], umbral: int = UMBRAL_P2) -> list[tuple[str, str, int]]:
    """Pares `(a, b, distancia)` con distancia <= umbral, en orden de clave."""
    return [
        (a, b, d)
        for a, b in combinations(sorted(hashes), 2)
        if (d := hamming(hashes[a], hashes[b])) <= umbral
    ]


def grupos(hashes: dict[str, int], umbral: int = UMBRAL_P2) -> list[list[str]]:
    """Componentes conexas de casi duplicados (transitivas, como en P2), ordenadas."""
    padre = {k: k for k in hashes}

    def raiz(x: str) -> str:
        while padre[x] != x:
            padre[x] = padre[padre[x]]
            x = padre[x]
        return x

    for a, b, _ in pares(hashes, umbral):
        ra, rb = raiz(a), raiz(b)
        if ra != rb:
            padre[max(ra, rb)] = min(ra, rb)
    por_raiz: dict[str, list[str]] = {}
    for k in sorted(hashes):
        por_raiz.setdefault(raiz(k), []).append(k)
    return sorted(por_raiz.values())
