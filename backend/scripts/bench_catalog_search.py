"""Mide la búsqueda del catálogo antes y después de indexar vectores.

Responde a tres preguntas con números, no con suposiciones:

1. ¿Cuánto cuesta la búsqueda textual exacta y con acentos?
2. ¿Qué gana la búsqueda semántica sobre la textual, y cuánto cuesta?
3. ¿Cuánto tarda en generarse un embedding por entidad?

Uso:
    python -m scripts.bench_catalog_search              # mide
    python -m scripts.bench_catalog_search --embed 500  # cronometra N
"""
from __future__ import annotations

import argparse
import statistics
import sys
import time
from pathlib import Path

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.database import engine  # noqa: E402
from app.embeddings import embedder  # noqa: E402

# Consultas reales de taller: una es literal, otra usa un término colloquial.
CASOS = [
    ("toyota", "marca exacta"),
    ("Corolla", "modelo exacto"),
    ("pastilla de freno", "nombre en espanol"),
    ("balata", "sinonimo coloquial"),
    ("amortiguador", "nombre en espanol"),
    ("filtro de aceite", "nombre en espanol"),
    ("correa de distribución", "componente con tilde"),
    ("Toyota Corolla", "marca + modelo"),
    ("chevrolet sail", "modelo del mercado ecuatoriano"),
    ("pieza que carga la bateria", "lenguaje natural (debe usar semantica)"),
]

TIMING_SQL = {
    "marcas por prefijo": """
        SELECT id FROM catalog_makes WHERE name ILIKE 'toy%' ORDER BY name LIMIT 12""",
    "modelos por marca (filtro estructurado)": """
        SELECT mo.id FROM catalog_models mo JOIN catalog_makes mk ON mk.id = mo.make_id
        WHERE mk.slug = 'toyota' ORDER BY mo.name LIMIT 200""",
    "generaciones por modelo": """
        SELECT id FROM catalog_generations WHERE model_id = 1 ORDER BY year_start DESC LIMIT 200""",
    "motores por generacion": """
        SELECT id FROM catalog_engines WHERE generation_id = 1 ORDER BY power_hp DESC LIMIT 200""",
    "repuesto por nombre en espanol (trigram)": """
        SELECT part_id FROM catalog_part_terms WHERE name_es ILIKE '%pastilla de freno%' LIMIT 12""",
    "repuesto por sinonimo (JSONB como texto)": """
        SELECT part_id FROM catalog_part_terms WHERE synonyms::text ILIKE '%balata%' LIMIT 12""",
    "vecinos mas cercanos (HNSW, si hay embeddings)": """
        SELECT entity_id FROM catalog_embeddings
        WHERE entity_type = 'part' AND model_key = :key
        ORDER BY vector <=> CAST(:vec AS vector) LIMIT 12""",
}


def measure(connection, sql: str, repeats: int = 12, **params) -> dict | None:
    try:
        connection.execute(text(sql), params)
    except Exception as exc:  # noqa: BLE001 - una consulta no disponible no invalida el resto
        return {"error": str(exc).splitlines()[0][:90]}
    samples = []
    for _ in range(repeats):
        start = time.perf_counter()
        connection.execute(text(sql), params)
        samples.append((time.perf_counter() - start) * 1000)
    samples.sort()
    return {"min": samples[0], "mediana": statistics.median(samples),
            "p95": samples[int(len(samples) * 0.95) - 1], "max": samples[-1]}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--embed", type=int, default=0,
                        help="Cronometra la generacion de N embeddings y extrapola.")
    args = parser.parse_args()

    print("Motor:", engine.dialect.name)
    with engine.connect() as connection:
        print("\n== Volumen ==")
        for tabla in ("catalog_makes", "catalog_models", "catalog_generations",
                      "catalog_engines", "catalog_parts", "catalog_part_terms",
                      "catalog_embeddings"):
            print(f"  {tabla:24} {connection.execute(text(f'SELECT count(*) FROM {tabla}')).scalar():>8,}")

        indexed = connection.execute(
            text("SELECT count(*) FROM catalog_embeddings")).scalar()
        vector = None
        if indexed:
            info = embedder()
            if info.available():
                vector = "[" + ",".join(str(x) for x in info.encode_one("pastilla de freno")) + "]"

        print("\n== Tiempos de consulta (ms) ==")
        print(f"  {'consulta':52} {'min':>7} {'mediana':>8} {'p95':>7} {'max':>7}")
        for nombre, sql in TIMING_SQL.items():
            params = {}
            if "vector" in sql:
                if not vector:
                    print(f"  {nombre:52} {'sin embeddings':>8}")
                    continue
                params = {"key": embedder().model_key, "vec": vector}
            result = measure(connection, sql, **params)
            if result and "error" in result:
                print(f"  {nombre:52} ERROR {result['error']}")
            else:
                print(f"  {nombre:52} {result['min']:7.2f} {result['mediana']:8.2f} "
                      f"{result['p95']:7.2f} {result['max']:7.2f}")

    if args.embed:
        info = embedder()
        if not info.available():
            print("\nEmbeddings no disponibles:", info.status()["reason"])
            return 1
        print(f"\n== Cronometraje de embeddings ({info.model_key}) ==")
        with engine.connect() as connection:
            sql = ("SELECT make.name || ' ' || mo.name FROM catalog_models mo "
                   "JOIN catalog_makes make ON make.id = mo.make_id LIMIT :n")
            textos = [row[0] for row in connection.execute(text(sql), {"n": args.embed})]
        total = 0.0
        for inicio in range(0, len(textos), 32):
            lote = textos[inicio : inicio + 32]
            t0 = time.perf_counter()
            info.encode(lote)
            total += time.perf_counter() - t0
        por_lote = len(textos) / total if total else 0
        pendientes = 164 + 2644 + 6790 + 30535 + 1802
        print(f"  {len(textos)} textos en {total:.2f} s -> {por_lote:.1f} textos/s")
        print(f"  proyeccion para ~{pendientes:,} entidades: "
              f"{pendientes / por_lote / 60:.1f} min")
    return 0


if __name__ == "__main__":
    sys.exit(main())