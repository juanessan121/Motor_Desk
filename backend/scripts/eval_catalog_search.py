"""Evalúa la relevancia de la búsqueda del catálogo con casos reales de taller.

Medir rendimiento sin medir relevancia no dice nada: una consulta puede ser muy
rápida y devolver basura. Este script comprueba, sobre el catálogo realmente
importado, si una batería de consultas encuentra lo que un técnico espera.

Uso:
    python -m scripts.eval_catalog_search            # texto vs híbrido
    python -m scripts.eval_catalog_search --verbose  # con las consultas falladas
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.catalog_routes import search  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.dependencies import Database  # noqa: F401,E402
from app.models import User  # noqa: E402

# (consulta, tipo de entidad, identificadores que DEBEN aparecer en el top-12)
CASOS = [
    # Coincidencia exacta: el catálogo relacional ya resuelve esto.
    ("toyota", "make", ["toyota"]),
    ("Corolla", "model", ["toyota--corolla"]),
    ("Chevrolet", "make", ["chevrolet"]),
    # Español: sin la capa de traducción esto no encuentra nada.
    ("amortiguador", "part", ["carapi:rear-shock-absorber"]),
    ("pastilla de freno", "part", ["carapi:brake-pad"]),
    ("kit de distribución", "part", ["carapi:timing-kit"]),
    ("filtro de aceite", "part", ["carapi:oil-filter"]),
    # Sinónimo coloquial: el que usaría un mecánico, no el catálogo.
    ("balata", "part", ["carapi:brake-pad"]),
    # Acentos: la búsqueda textual debe tolerarlos.
    ("correa de distribución", "part", ["carapi:timing-belt"]),
    ("generador", "part", ["carapi:alternator"]),
    ("bujía", "part", ["carapi:spark-plug"]),
    ("espejo lateral", "part", ["carapi:left-side-mirror"]),
    # La fuente llama al modelo con el nombre comercial delante. El mecánico
    # busca por el nombre que conoce.
    ("Grand Vitara", "model", ["suzuki--escudograndvitara"]),
    ("Cruze", "model", ["chevrolet--cruze"]),
]

# Casos donde el texto no encuentra nada y solo la semántica puede servir.
# Son los que demuestran que el índice vectorial aporta algo y no es decorativo.
SOLO_SEMANTICA = [
    ("pieza que carga la bateria", "part", "carapi:alternator"),
    ("evita que patine el vehiculo", "part", "carapi:abs-sensor"),
]

# Consultas cuyo resultado correcto NO está en las fuentes. No son un fallo de
# búsqueda: son huecos de datos que solo el registro manual puede cubrir.
HUECOS = [
    ("Sail", "model"),          # Chevrolet Sail, habitual en Ecuador
    ("Optra", "model"),
    ("Lanos", "model"),
    ("K5", "model"),
]


class _Admin:
    """El usuario solo se usa para la dependencia de rol de la ruta."""

    id, role, workshop_id, must_change_password = 1, "admin", 1, False


def evaluar(db, peso: float, verbose: bool) -> tuple[int, int]:
    aciertos, total = 0, 0
    for consulta, tipo, esperados in CASOS:
        inicio = time.perf_counter()
        resultado = search(db, _Admin(), q=consulta, type=tipo, limit=12,
                           semantic_weight=peso)
        milis = (time.perf_counter() - inicio) * 1000
        obtenidos = [row["slug"] if "slug" in row else row["sku"]
                     for row in resultado["results"].get(tipo, [])]
        faltan = [esperado for esperado in esperados if esperado not in obtenidos]
        total += len(esperados)
        aciertos += len(esperados) - len(faltan)
        estado = "OK " if not faltan else "FALLA"
        print(f"  [{estado}] {consulta:28} {tipo:10} {milis:6.1f} ms  "
              f"{len(obtenidos):2d} resultados  {resultado['mode']}")
        if faltan and verbose:
            print(f"          esperaba {faltan}; obtuvo {obtenidos[:6]}")
    return aciertos, total


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    with SessionLocal() as db:
        for etiqueta, peso in (("solo texto (peso 0)", 0.0),
                               ("hibrido por defecto (0,7)", 0.7)):
            print(f"\n== {etiqueta} ==")
            aciertos, total = evaluar(db, peso, args.verbose)
            porcentaje = aciertos / total * 100 if total else 0
            print(f"  acierto: {aciertos}/{total} ({porcentaje:.1f} %)")

        print("\n== Solo semantica (el texto no encuentra nada) ==")
        for consulta, tipo, esperado in SOLO_SEMANTICA:
            solo_texto = search(db, _Admin(), q=consulta, type=tipo, limit=12,
                                semantic_weight=0.0)
            hibrido = search(db, _Admin(), q=consulta, type=tipo, limit=12,
                             semantic_weight=0.7)
            texto_ids = [row.get("slug") or row.get("sku")
                         for row in solo_texto["results"].get(tipo, [])]
            hibrido_ids = [row.get("slug") or row.get("sku")
                           for row in hibrido["results"].get(tipo, [])]
            puesto = hibrido_ids.index(esperado) + 1 if esperado in hibrido_ids else 0
            print(f"  {consulta:32} texto={len(texto_ids)}  hibrido={len(hibrido_ids)}  "
                  f"'{esperado}' en posicion {puesto or 'no encontrado'}")

        print("\n== Huecos de datos (no son fallos de busqueda) ==")
        for consulta, tipo in HUECOS:
            resultado = search(db, _Admin(), q=consulta, type=tipo, limit=5,
                               semantic_weight=0.7)
            obtenidos = [row.get("slug") or row.get("sku")
                         for row in resultado["results"].get(tipo, [])]
            print(f"  {consulta:16} {tipo:8} -> {obtenidos or 'sin resultados'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())