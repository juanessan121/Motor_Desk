"""Compara variantes del texto embebido con consultas en lenguaje natural.

Responde a una pregunta concreta: ¿el sufijo genérico que se añade al texto
de cada repuesto ("repuesto mecanico para vehiculo") ayuda o estorba? Un
sufijo común a todos los vectores los acerca entre sí y reduce el contraste.

Mide la posición que alcanza el repuesto esperado, no una anecdotal.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.catalog_models import CatalogPartTerm, VehiclePart  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.embeddings import embedder  # noqa: E402
from sqlalchemy import select  # noqa: E402

SUFIJO = " · repuesto mecanico para vehiculo"

# (consulta en lenguaje natural, slug esperado)
CONSULTAS = [
    ("pieza que carga la bateria", "carapi:alternator"),
    ("como hago que el coche no patine", "carapi:abs-sensor"),
    ("parte que enfria el motor", "carapi:main-radiator"),
    ("lo que disipa el calor del motor", "carapi:oil-cooler"),
    ("elemento que hace chirriar al frenar", "carapi:brake-pad"),
    ("componente que cambia las velocidades", "carapi:clutch"),
    ("lo que da fuerza a las ruedas", "carapi:drive-shaft"),
    ("pieza que enciende el coche", "carapi:starter-motor"),
    ("elemento que tira del coche hacia atras", "carapi:brake-fluid-reservoir"),
    ("componente que va entre el motor y la caja", "carapi:clutch"),
]


def main() -> int:
    engine = embedder()
    if not engine.available():
        print("Embeddings no disponibles:", engine.status()["reason"])
        return 1

    with SessionLocal() as db:
        terms = {row.part_id: row for row in db.scalars(select(CatalogPartTerm))}
        piezas = []
        for part in db.scalars(select(VehiclePart)):
            term = terms.get(part.id)
            if term is None:
                continue
            base = " · ".join(value for value in (
                term.name_es, " ".join(term.synonyms or []),
                part.title, part.brand, term.system) if value)
            piezas.append((part.sku, base))
    print(f"repuestos evaluados: {len(piezas)}")

    variantes = {
        "con sufijo generico": [base + SUFIJO for _sku, base in piezas],
        "sin sufijo generico": [base for _sku, base in piezas],
    }
    objetivo = [sku for sku, _ in piezas]
    for etiqueta, textos in variantes.items():
        vectores = np.asarray(engine.encode(textos), dtype=np.float32)
        posiciones, aciertos = [], 0
        for consulta, esperado in CONSULTAS:
            consulta_vec = np.asarray(engine.encode_one(consulta), dtype=np.float32)
            orden = np.argsort(-(vectores @ consulta_vec))
            puesto = next((n + 1 for n, idx in enumerate(orden)
                           if objetivo[idx] == esperado), None)
            posiciones.append(puesto)
            aciertos += puesto is not None and puesto <= 10
        top1 = sum(1 for p in posiciones if p == 1)
        top10 = sum(1 for p in posiciones if p and p <= 10)
        dentro = [p for p in posiciones if p]
        print(f"\n{etiqueta}")
        print(f"  esperado entre los 10 primeros : {top10}/{len(CONSULTAS)}")
        print(f"  en la posicion 1               : {top1}/{len(CONSULTAS)}")
        print(f"  encontrado en algun puesto     : {len(dentro)}/{len(CONSULTAS)}")
        print(f"  puesto medio cuando aparece    : "
              f"{np.mean(dentro):.1f}" if dentro else "  puesto medio: n/a")
    return 0


if __name__ == "__main__":
    sys.exit(main())