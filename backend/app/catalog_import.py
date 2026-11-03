"""Importador del catálogo de referencia vehicular.

Fuentes abiertas, cada una con su licencia registrada en `catalog_sources`:

- gor3a/vehicle-makes-models  (ODbL 1.0)  marcas, modelos, generaciones, motores
- filippofilip95/car-logos-dataset (MIT)   logotipos por marca
- ModelPartFinder open data   (CC BY 4.0) repuestos mecánicos y compatibilidad

Es idempotente: registra el hash de cada fuente y omite lo que no cambió. Los
identificadores se conservan estables para no invalidar los embeddings ya calculados.

Uso:
    python -m app.catalog_import                # importa y actualiza
    python -m app.catalog_import --offline      # reutiliza la caché local
    python -m app.catalog_import --no-embed     # solo catálogo relacional
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
import unicodedata
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from .catalog_models import (
    EMBEDDED_ENTITIES, ENTITY_ENGINE, ENTITY_GENERATION, ENTITY_MAKE,
    ENTITY_MODEL, ENTITY_PART, ORIGIN_IMPORTED, CatalogEmbedding,
    CatalogPartTerm, CatalogRecordMeta, CatalogSource, VehicleEngine,
    VehicleEngineSpec, VehicleGeneration, VehicleMake, VehicleModel,
    VehiclePart, VehiclePartFit,
)
from .database import SessionLocal
from .embeddings import embedder
from .parts_glossary import synonyms_for, translate

# `CATALOG_CACHE` es el volumen que compose.yaml monta en la imagen; sin él la
# ruta caía en `<WORKDIR>/../data`, que en Docker es `/srv` (de root) y hacía
# fallar el importador con PermissionError, y que en local no coincide con la
# imagen. Fallback único para desarrollo local.
CACHE_DIR = Path(
    os.environ.get("CATALOG_CACHE")
    or Path(__file__).resolve().parents[2] / "data" / "catalog_cache"
)

SOURCES = {
    "vehicles": {
        "title": "Vehicle makes, models, generations and engine specs",
        "url": "https://github.com/gor3a/vehicle-makes-models",
        "path": "data/vehicles.sqlite",
        "license": "ODbL-1.0",
        "license_url": "https://github.com/gor3a/vehicle-makes-models/blob/main/LICENSE-DATA",
        "attribution": "gor3a/vehicle-makes-models, datos bajo ODbL 1.0. Derivado de autoevolution.com.",
    },
    "logos": {
        "title": "Car logos dataset",
        "url": "https://github.com/filippofilip95/car-logos-dataset",
        "path": "logos/data.json",
        "branch": "master",
        "license": "MIT",
        # El repositorio declara MIT en package.json; no publica archivo LICENSE.
        "license_url": "https://github.com/filippofilip95/car-logos-dataset/blob/master/package.json",
        "attribution": "Logotipos: propiedad de sus respectivos titulares.",
    },
    "parts": {
        "title": "ModelPartFinder open cross-reference data (subconjunto Automotive)",
        "url": "https://modelpartfinder.com/data",
        "path": "api/open-data/cross-reference.json",
        "license": "CC-BY-4.0",
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "attribution": "ModelPartFinder (https://modelpartfinder.com) — se requiere enlace visible.",
    },
    # Aporta el nombre de la pieza en un idioma legible, con 1 530 entradas.
    # No trae categoría, ni compatibilidad, ni traducción al español: de eso se
    # ocupa `parts_glossary`. Se importa como fuente aparte para no mezclar
    # licencias ni Mixing con las compatibilidades de ModelPartFinder.
    "part_terms": {
        "title": "Car brands, models & parts database (auto-parts-db)",
        "url": "https://github.com/lifeofcapo/car-api",
        "path": "car-parts.json",
        "license": "MIT",
        "license_url": "https://github.com/lifeofcapo/car-api/blob/main/LICENSE",
        "attribution": "lifeofcapo/car-api (auto-parts-db) — MIT. Nombres originales en ruso.",
    },
}

RAW = {
    "vehicles": "https://raw.githubusercontent.com/gor3a/vehicle-makes-models/main/data/vehicles.sqlite",
    "logos": "https://raw.githubusercontent.com/filippofilip95/car-logos-dataset/master/logos/data.json",
    "parts": "https://modelpartfinder.com/api/open-data/cross-reference.json",
    "part_terms": "https://raw.githubusercontent.com/lifeofcapo/car-api/main/car-parts.json",
}

CHUNK = 2000


def normalize(value: str) -> str:
    """Minúsculas sin acentos ni separadores, para cruzar nombres de marca."""
    text = unicodedata.normalize("NFKD", value or "")
    return re.sub(r"[^a-z0-9]+", "", text.lower())


ATTEMPTS = 3
# Varias fuentes responden 403 al User-Agent por defecto de Python. Se envía
# uno identificable en lugar de uno vacío para poder trazar el consumo.
USER_AGENT = "MotorDesk-Catalog/1.0 (+https://github.com/gor3a/vehicle-makes-models)"


def fetch(key: str, offline: bool) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    target = CACHE_DIR / f"{key}{Path(SOURCES[key]['path']).suffix}"
    if target.exists() and target.stat().st_size:
        return target
    if offline:
        raise SystemExit(f"Falta la caché de {key} y --offline está activo.")
    print(f"  descargando {key} ...", flush=True)
    request = urllib.request.Request(RAW[key], headers={"User-Agent": USER_AGENT})
    partial = target.with_suffix(target.suffix + ".part")
    last: Exception | None = None
    for attempt in range(1, ATTEMPTS + 1):
        try:
            with urllib.request.urlopen(request, timeout=600) as response, \
                    partial.open("wb") as handle:
                while chunk := response.read(1 << 20):
                    handle.write(chunk)
            # Solo se promueve a caché un archivo completo: una descarga
            # interrumpida no debe pasar por buena en la siguiente ejecución.
            if partial.stat().st_size == 0:
                raise OSError("descarga vacía")
            partial.replace(target)
            return target
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            last = exc
            partial.unlink(missing_ok=True)
            if attempt < ATTEMPTS:
                print(f"    intento {attempt}/{ATTEMPTS} fallido: {exc}", flush=True)
    raise SystemExit(f"No se pudo descargar {key} desde {RAW[key]}: {last}")


def content_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def already_imported(db: Session, key: str, digest: str, force: bool) -> bool:
    if force:
        return False
    row = db.get(CatalogSource, key)
    return bool(row and row.content_hash == digest)


def record_source(db: Session, key: str, digest: str, rows: int) -> None:
    meta = SOURCES[key]
    row = db.get(CatalogSource, key)
    if row is None:
        row = CatalogSource(source_key=key)
        db.add(row)
    row.title, row.url = meta["title"], meta["url"]
    row.license, row.license_url = meta["license"], meta["license_url"]
    row.attribution, row.content_hash, row.row_count = meta["attribution"], digest, rows


def register_meta(db: Session, entity_type: str, entity_ids, source_key: str,
                  origin: str = ORIGIN_IMPORTED) -> int:
    """Deja constancia de qué fuente trajo cada registro.

    Solo escribe lo que falta: un registro ya presente conserva su origen, de
    modo que una reimportación no convierte en `imported` algo que una persona
    añadió a mano o corrigió.
    """
    ids = [value for value in dict.fromkeys(entity_ids) if value is not None]
    if not ids:
        return 0
    existing = set()
    for start in range(0, len(ids), CHUNK):
        chunk = ids[start : start + CHUNK]
        existing.update(db.execute(
            select(CatalogRecordMeta.entity_id).where(
                CatalogRecordMeta.entity_type == entity_type,
                CatalogRecordMeta.entity_id.in_(chunk))).scalars())
    pending = [value for value in ids if value not in existing]
    now = datetime.now(timezone.utc)
    for start in range(0, len(pending), CHUNK):
        db.execute(CatalogRecordMeta.__table__.insert(),
                   [{"entity_type": entity_type, "entity_id": value,
                     "source_key": source_key, "origin": origin,
                     "created_at": now} for value in pending[start : start + CHUNK]])
    return len(pending)


def search_text(*parts) -> str:
    return " · ".join(str(part).strip() for part in parts if part not in (None, ""))


# --------------------------------------------------------------------------- #
# Importadores
# --------------------------------------------------------------------------- #

def import_vehicles(db: Session, path: Path, with_specs: bool = True) -> int:
    source = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    # Sin row_factory las filas son tuplas y `row["group"]` revienta con
    # TypeError; el importador nunca se había ejecutado hasta ahora.
    source.row_factory = sqlite3.Row
    try:
        makes = {row["group"]: (row["name"], row["country"])
                 for row in source.execute("SELECT \"group\", name, country FROM makes")}
        make_ids = upsert(db, VehicleMake,
                          [{"slug": group, "name": name, "country": country}
                           for group, (name, country) in sorted(makes.items())],
                          "slug")
        model_ids = upsert_linked(db, VehicleModel, [
            {"make_id": make_ids[row["group"]], "slug": f"{row['group']}--{normalize(row['name'])}",
             "name": row["name"], "year_start": row["year_start"], "year_end": row["year_end"],
             "source_id": row["id"]}
            for row in source.execute(
                "SELECT m.\"group\", mo.id, mo.name, mo.year_start, mo.year_end "
                "FROM models mo JOIN makes m ON m.id = mo.make_id")
        ], "slug", "source_id")
        generation_ids = upsert_linked(db, VehicleGeneration, [
            {"model_id": model_ids[row["model_id"]],
             "slug": f"{row['group']}--{normalize(row['model_name'])}--{normalize(row['name'])}--{row['year_start']}",
             "name": row["name"], "year_start": row["year_start"],
             "year_end": row["year_end"], "body_type": row["body_type"],
             "source_id": row["generation_id"]}
            for row in source.execute(
                "SELECT m.\"group\", mo.name AS model_name, mo.id AS model_id, "
                "g.id AS generation_id, g.name, g.year_start, g.year_end, g.body_type "
                "FROM generations g JOIN models mo ON mo.id = g.model_id "
                "JOIN makes m ON m.id = mo.make_id")
        ], "slug", "source_id")
        engine_ids = upsert_linked(db, VehicleEngine, [
            {"generation_id": generation_ids[row["source_generation_id"]], "slug": row["slug"],
             "label": row["label"], "fuel_type": row["fuel_type"], "cylinders": row["cylinders"],
             "displacement_cc": row["displacement_cc"], "power_hp": row["power_hp"],
             "torque_nm": row["torque_nm"], "transmission": row["transmission"],
             "drivetrain": row["drivetrain"], "zero_to_100_s": row["zero_to_100_s"],
             "top_speed_kmh": row["top_speed_kmh"],
             "fuel_economy_l100": row["fuel_economy_combined_l100"],
             "length_mm": row["length_mm"], "width_mm": row["width_mm"],
             "height_mm": row["height_mm"], "wheelbase_mm": row["wheelbase_mm"],
             "curb_weight_kg": row["curb_weight_kg"],
             "source_id": row["id"]}
            for row in engine_rows(source, generation_ids)
        ], "slug", "source_id")
        if with_specs and engine_ids:
            db.execute(delete(VehicleEngineSpec))
            batch = []
            for row in source.execute("SELECT engine_id, key, value FROM engine_specs"):
                mapped = engine_ids.get(row["engine_id"])
                if mapped:
                    batch.append({"engine_id": mapped, "key": row["key"], "value": row["value"]})
                if len(batch) >= CHUNK:
                    db.execute(VehicleEngineSpec.__table__.insert(), batch)
                    batch = []
            if batch:
                db.execute(VehicleEngineSpec.__table__.insert(), batch)
    finally:
        source.close()
    register_meta(db, ENTITY_MAKE, make_ids.values(), "vehicles")
    register_meta(db, ENTITY_MODEL, model_ids.values(), "vehicles")
    register_meta(db, ENTITY_GENERATION, generation_ids.values(), "vehicles")
    register_meta(db, ENTITY_ENGINE, engine_ids.values(), "vehicles")
    db.flush()
    return len(makes)


def engine_rows(source, generation_ids):
    """Slug estable por motor: la etiqueta se repite dentro de una generación.

    El contador va por generación **del catálogo**, no por generación de origen.
    Varias generaciones de la fuente pueden acabar fusionadas en una sola del
    catálogo; si el contador fuera por origen, dos fuentes distintas generarían
    el mismo slug (`G--0`) y `upsert` las fusionaría, perdiendo 1 067
    variantes de motor de un total de 30 535.
    """
    counters = {}
    for row in source.execute(
            "SELECT g.id AS source_generation_id, e.* FROM engines e "
            "JOIN generations g ON g.id = e.generation_id ORDER BY e.id"):
        catalog_id = generation_ids[row["source_generation_id"]]
        index = counters.get(catalog_id, 0)
        counters[catalog_id] = index + 1
        yield {**dict(row), "slug": f"{catalog_id}--{index}"}


# Campos que se combinan cuando dos filas comparten la misma clave natural:
# el rango de años se widen, nunca se descarta informacion.
YEAR_FIELDS = {"year_start": min, "year_end": max}


def merge_row(target: dict, other: dict) -> None:
    for key, value in other.items():
        if key not in target or target[key] is None:
            target[key] = value
        elif key in YEAR_FIELDS and value is not None:
            current = target[key]
            target[key] = YEAR_FIELDS[key](current, value)


def upsert(db: Session, model, rows: list[dict], key: str) -> dict:
    """Inserta por clave natural y devuelve {clave_natural: id}.

    La fuente repite claves: `datsun--go` aparece dos veces para la misma marca
    con años distintos, porque el slug ignora el rango. Sin deduplicar, el lote
    violaba `ix_catalog_models_slug` a mitad de la importacion y se perdia
    todo. Aqui las filas con la misma clave se combinan y los años se ensanchan.

    Solo inserta. Una fila ya presente no se sobrescribe: por eso un registro
    anadido a mano sobrevive a una reimportacion (ver `record_source`).
    """
    column = getattr(model, key)
    merged: dict = {}
    for row in rows:
        identity = row[key]
        if identity in merged:
            merge_row(merged[identity], row)
        else:
            merged[identity] = dict(row)
    wanted = list(merged)

    def read_ids(keys):
        found = {}
        for start in range(0, len(keys), CHUNK):
            chunk = keys[start : start + CHUNK]
            for value, row_id in db.execute(select(column, model.id).where(column.in_(chunk))):
                found[value] = row_id
        return found

    mapping = read_ids(wanted)
    pending = [merged[identity] for identity in wanted if identity not in mapping]
    for start in range(0, len(pending), CHUNK):
        db.execute(model.__table__.insert(), pending[start : start + CHUNK])
    if pending:
        mapping.update(read_ids(wanted))
    db.flush()
    return mapping


def upsert_linked(db: Session, model, rows: list[dict], key: str,
                  source_key: str) -> dict:
    """Como `upsert`, pero devuelve {identificador_en_fuente: id_del_catalogo}.

    El importador encadena foreign keys usando los identificadores de la fuente
    (los `id` de `vehicles.sqlite`), no los slugs. `upsert` devuelveva el mapa
    por slug y `model_ids[row["model_id"]]` reventaba con KeyError.
    """
    by_key = upsert(db, model, rows, key)
    linked: dict = {}
    for row in rows:
        catalog_id = by_key.get(row[key])
        if catalog_id is not None:
            linked[row[source_key]] = catalog_id
    return linked


def import_logos(db: Session, path: Path) -> int:
    payload = json.loads(path.read_text(encoding="utf-8"))
    by_name = {normalize(item["name"]): item for item in payload}
    by_name.update({normalize(item["slug"]): item for item in payload})
    # Alias para marcas cuyo logotipo usa otro nombre comercial. Son
    # equivalencias comprobadas una por una, no una coincidencia aproximada:
    # KGM es el nombre que SsangYong adoptó en 2023 y el dataset de logos
    # todavía publica el anterior.
    aliases = {"samsung": "samsungmotors", "gordonmurrayautomotive": "gma",
               "marutisuzuki": "suzuki", "bmwgroup": "bmw",
               "kgm": "ssangyong"}
    updated = 0
    unmatched = []
    for make in db.scalars(select(VehicleMake)):
        item = by_name.get(normalize(make.name))
        if item is None:
            for alias, target in aliases.items():
                if alias in normalize(make.name) and target in by_name:
                    item = by_name[target]
                    break
        if item:
            images = item.get("image") or {}
            make.logo_url = images.get("optimized") or images.get("thumb")
            updated += 1
        else:
            # Sin logo: la interfaz usa un placeholder, no un archivo inventado.
            unmatched.append(make.name)
    db.flush()
    # Sin coincidencia exacta se reportan para revisión, no se asocian a ojo.
    print(f"  logos asociados: {updated}; sin coincidencia: {len(unmatched)}", flush=True)
    if unmatched:
        print(f"    {', '.join(sorted(unmatched))}", flush=True)
    return updated


YEAR = re.compile(r"^(.*?)((?:19|20)\d{2})((?:19|20)\d{2})?$")

# La fuente de repuestos escribe la marca concatenada en mayusculas; se corrigen
# variantes ortograficas habituales antes de buscar la marca en el catalogo.
BRAND_ALIASES = {
    "mercedesbenze": "mercedesbenz",
    "mercedezbenz": "mercedesbenz",
    "mercedesbence": "mercedesbenz",
}


def split_vehicle_key(value: str):
    match = YEAR.match(value)
    if not match:
        return value, None, None
    tail, first, second = match.group(1), match.group(2), match.group(3)
    if not tail:
        return value, None, None
    return tail, int(first), int(second) if second else None


def slugify(text: str) -> str:
    """`Wideband oxygen sensor` -> `wideband-oxygen-sensor`."""
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def system_of(text: str) -> str | None:
    """Clasifica un nombre en inglés dentro de un sistema del vehículo."""
    return translate(slugify(text))[1]


def import_parts(db: Session, path: Path) -> tuple[int, int]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    items = [item for item in payload.get("items", []) if item.get("vertical") == "Automotive"]
    # `category` recibía el título en minúsculas, que no es una categoría: era
    # el nombre otra vez y hacía la faceta inservible. Ahora guarda el sistema
    # mecánico deducido del título en inglés por el glosario.
    part_ids = upsert(db, VehiclePart, [
        {"sku": item["sku"], "mpn": item.get("mpn"), "title": item["title"],
         "brand": item.get("brand"), "category": system_of(item["title"])}
        for item in items
    ], "sku")
    register_meta(db, ENTITY_PART, list(part_ids.values()), "parts")

    makes = [(normalize(row.name), row.id, row.name) for row in db.scalars(select(VehicleMake))]
    models = {}
    for row in db.execute(
            select(VehicleModel.id, VehicleModel.name, VehicleMake.name)
            .join(VehicleMake, VehicleMake.id == VehicleModel.make_id)):
        models.setdefault(normalize(row[2]), []).append((normalize(row[1]), row[0]))

    fits, resolved = [], 0
    for item in items:
        part_id = part_ids.get(item["sku"])
        if not part_id:
            continue
        for raw in item.get("compatible_models") or []:
            token, year_from, year_to = split_vehicle_key(raw)
            needle = normalize(token)
            model_id = resolve_model(needle, makes, models)
            if model_id is None:
                continue
            resolved += 1
            fits.append({"part_id": part_id, "model_id": model_id, "source_key": raw,
                         "year_from": year_from, "year_to": year_to})
    db.execute(delete(VehiclePartFit))
    for start in range(0, len(fits), CHUNK):
        db.execute(VehiclePartFit.__table__.insert(), fits[start : start + CHUNK])
    db.flush()
    return len(items), resolved


def import_part_terms(db: Session, path: Path) -> tuple[int, int, int]:
    """Importa el catálogo de nombres de `car-api` y su capa en español.

    La fuente trae 1 530 entradas con `slug` en inglés y `name` en ruso. No
    declara categoría ni compatibilidad, así que aquí solo se añade:

    - la pieza en `catalog_parts`, con `sku` `carapi:<slug>` para que conviva
      con las de ModelPartFinder sin colisionar (son catálogos distintos);
    - la traducción al español en `catalog_part_terms`, marcada para revisión
      cuando el glosario no resolvió alguna palabra;
    - las palabras clave en inglés, para que buscar "shock absorber" encuentre
      la pieza aunque la interfaz esté en español.

    Devuelve `(piezas, traducidas, pendientes_de_revision)`.
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    seen, rows = set(), []
    for item in payload:
        slug = (item.get("slug") or "").strip()
        name_es, system, review = translate(slug)
        if not slug or slug in seen:
            continue
        seen.add(slug)
        rows.append({
            "sku": f"carapi:{slug}",
            "mpn": None,
            "title": (item.get("name") or slug).strip()[:200],
            "brand": None,
            "category": system,
            "name_es": name_es,
            "system": system,
            "review": review,
            "keywords": sorted({token for token in slug.split("-") if len(token) > 2}),
        })

    part_ids = upsert(db, VehiclePart, [
        {"sku": row["sku"], "mpn": row["mpn"], "title": row["title"],
         "brand": row["brand"], "category": row["category"]}
        for row in rows
    ], "sku")

    now = datetime.now(timezone.utc)
    terms, pending = [], 0
    for row in rows:
        part_id = part_ids.get(row["sku"])
        if part_id is None or not row["name_es"]:
            continue
        pending += bool(row["review"])
        terms.append({
            "part_id": part_id, "source_key": "part_terms",
            "name_es": row["name_es"], "system": row["system"],
            "synonyms": synonyms_for(row["name_es"]),
            "keywords": row["keywords"],
            "review_required": bool(row["review"]),
            "translated_by": "glosario-v1", "translated_at": now,
        })
    if terms:
        db.execute(delete(CatalogPartTerm).where(
            CatalogPartTerm.source_key == "part_terms"))
        for start in range(0, len(terms), CHUNK):
            db.execute(CatalogPartTerm.__table__.insert(), terms[start : start + CHUNK])
    register_meta(db, ENTITY_PART, list(part_ids.values()), "part_terms")
    db.flush()
    print(f"  piezas: {len(rows)} · traducidas: {len(terms)} · "
          f"pendientes de revisión: {pending}", flush=True)
    return len(rows), len(terms), pending


def resolve_model(needle: str, makes, models):
    """`VOLKSWAGENJETTA` -> marca Volkswagen + modelo Jetta."""
    for alias, canonical in BRAND_ALIASES.items():
        if needle.startswith(alias):
            needle = canonical + needle[len(alias) :]
            break
    for make_norm, _make_id, make_name in sorted(makes, key=lambda row: -len(row[0])):
        if needle.startswith(make_norm) and len(needle) > len(make_norm):
            remainder = needle[len(make_norm) :]
            for model_norm, model_id in models.get(normalize(make_name), []):
                if model_norm == remainder:
                    return model_id
            for model_norm, model_id in models.get(normalize(make_name), []):
                if remainder.startswith(model_norm) or model_norm.startswith(remainder):
                    return model_id
    return None


# --------------------------------------------------------------------------- #
# Embeddings
# --------------------------------------------------------------------------- #

def collect_texts(db: Session):
    rows = []
    for make, model in db.execute(select(VehicleMake, VehicleModel).join(
            VehicleModel, VehicleModel.make_id == VehicleMake.id)):
        rows.append((ENTITY_MODEL, model.id, search_text(
            make.name, model.name, "modelo de vehiculo",
            f"{model.year_start or ''}-{model.year_end or ''}")))
    for make, model, generation in db.execute(
            select(VehicleMake, VehicleModel, VehicleGeneration)
            .join(VehicleModel, VehicleModel.make_id == VehicleMake.id)
            .join(VehicleGeneration, VehicleGeneration.model_id == VehicleModel.id)):
        rows.append((ENTITY_GENERATION, generation.id, search_text(
            make.name, model.name, generation.name, generation.body_type,
            f"{generation.year_start or ''}-{generation.year_end or ''}", "generacion")))
    for make, model, generation, engine in db.execute(
            select(VehicleMake, VehicleModel, VehicleGeneration, VehicleEngine)
            .join(VehicleModel, VehicleModel.make_id == VehicleMake.id)
            .join(VehicleGeneration, VehicleGeneration.model_id == VehicleModel.id)
            .join(VehicleEngine, VehicleEngine.generation_id == VehicleGeneration.id)):
        rows.append((ENTITY_ENGINE, engine.id, search_text(
            make.name, model.name, generation.name, engine.label, engine.fuel_type,
            f"{engine.cylinders} cilindros" if engine.cylinders else None,
            f"{int(engine.displacement_cc)} cc" if engine.displacement_cc else None,
            f"{int(engine.power_hp)} hp" if engine.power_hp else None,
            f"{int(engine.torque_nm)} nm" if engine.torque_nm else None,
            engine.transmission, engine.drivetrain, "motor")))
    for make in db.scalars(select(VehicleMake)):
        rows.append((ENTITY_MAKE, make.id, search_text(make.name, make.country, "marca de vehiculos")))
    terms = {row.part_id: row for row in db.scalars(select(CatalogPartTerm))}
    for part in db.scalars(select(VehiclePart)):
        term = terms.get(part.id)
        if term is None:
            continue
        # Solo el nombre en español y sus sinónimos. Medido sobre consultas
        # reales de taller: mezclar el título original (ruso en car-api) y el
        # inglés baja el acierto top-1 de 3/8 a 0/8 y el top-10 de 4/8 a 2/8.
        # El idioma del texto debe ser el de quien busca.
        rows.append((ENTITY_PART, part.id, search_text(
            term.name_es, " ".join(term.synonyms) if term.synonyms else None)))
    # Las piezas de ModelPartFinder no tienen traducción: se usa su título.
    for part in db.scalars(select(VehiclePart)):
        if part.id not in terms:
            rows.append((ENTITY_PART, part.id, search_text(part.title, part.brand)))
    return rows


def embed_catalog(db: Session, batch_size: int = 32,
                  reindex: str | None = None) -> int:
    """Vuelca vectores para lo que aún no está indexado.

    Solo hace `flush`, nunca `commit`: la sesión la gobierna `run()` dentro de
    `SessionLocal.begin()`, y un `commit()` intermedio cerraba esa transacción
    y abortaba la importación a mitad (`Can't operate on closed transaction`).
    El corte por lotes se hace con flush, que agrupa los INSERT en la base sin
    cerrar el contexto.

    `reindex` borra los vectores de una entidad y la vuelve a generar. Hace
    falta cuando cambia la receta del texto embebido: como la clave es
    modelo@revisión, un texto distinto no invalidaría nada por sí solo.
    """
    engine = embedder()
    if not engine.available():
        print(f"  embeddings no disponibles: {engine.status()['reason']}", flush=True)
        return 0
    model_key = engine.model_key
    if reindex:
        borrados = db.execute(
            delete(CatalogEmbedding).where(CatalogEmbedding.entity_type == reindex))
        print(f"  {reindex}: {borrados.rowcount} vectores anteriores eliminados", flush=True)
    rows = collect_texts(db)
    # La clave es (tipo, id): si solo se guardara el tipo, la presencia de un
    # solo embedding de una entidad omitiría para siempre las entidades nuevas
    # de ese mismo tipo.
    done = {
        (row.entity_type, row.entity_id)
        for row in db.execute(
            select(CatalogEmbedding.entity_type, CatalogEmbedding.entity_id)
            .where(CatalogEmbedding.model_key == model_key))
    }
    pending = [row for row in rows if (row[0], row[1]) not in done]
    if not pending:
        print(f"  embeddings al día ({len(rows)} entidades con {model_key})", flush=True)
        return 0
    print(f"  incrustando {len(pending)} entidades con {model_key}", flush=True)
    written = 0
    for start in range(0, len(pending), batch_size):
        chunk = pending[start : start + batch_size]
        vectors = engine.encode([text for _type, _id, text in chunk], batch_size=batch_size)
        db.execute(CatalogEmbedding.__table__.insert(),
                   [{"entity_type": t, "entity_id": i, "model_key": model_key, "vector": v}
                    for (t, i, _text), v in zip(chunk, vectors)])
        written += len(chunk)
        if written % 10000 < batch_size:
            db.flush()
            print(f"    {written}/{len(pending)}", flush=True)
    db.flush()
    return written


# --------------------------------------------------------------------------- #

def run(force: bool = False, offline: bool = False, with_specs: bool = True,
        with_embeddings: bool = True, reindex: str | None = None) -> dict:
    summary = {}
    with SessionLocal.begin() as db:
        for key in ("vehicles", "logos", "parts", "part_terms"):
            path = fetch(key, offline)
            digest = content_hash(path)
            if already_imported(db, key, digest, force):
                print(f"{key}: sin cambios", flush=True)
                summary[key] = db.get(CatalogSource, key).row_count
                continue
            print(f"{key}: importando ...", flush=True)
            if key == "vehicles":
                rows = import_vehicles(db, path, with_specs)
            elif key == "logos":
                rows = import_logos(db, path)
            elif key == "part_terms":
                rows, translated, pending = import_part_terms(db, path)
                summary["traducciones"] = translated
                summary["pendientes_revision"] = pending
            else:
                rows, resolved = import_parts(db, path)
                summary["compatibilidades"] = resolved
                print(f"  compatibilidades resueltas: {resolved}", flush=True)
            record_source(db, key, digest, rows)
            summary[key] = rows
        if with_embeddings:
            summary["embeddings"] = embed_catalog(db, reindex=reindex)
        # `SessionLocal.begin()` confirma al salir del bloque: un `commit()`
        # explícito aquí cerraría la transacción antes de tiempo.
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Importa el catálogo vehicular de referencia.")
    parser.add_argument("--force", action="store_true", help="Reimporta aunque no haya cambios.")
    parser.add_argument("--offline", action="store_true", help="Urea solo la caché local.")
    parser.add_argument("--no-embed", action="store_true", help="No calcula embeddings.")
    parser.add_argument("--no-specs", action="store_true", help="Omite engine_specs (muchas filas).")
    parser.add_argument("--reindex", choices=list(EMBEDDED_ENTITIES), metavar="ENTIDAD",
                        help="Regenera los vectores de una entidad: make, model, "
                             "generation, engine o part. Útil cuando cambia el "
                             "texto que se embebe.")
    args = parser.parse_args()
    summary = run(force=args.force, offline=args.offline,
                  with_specs=not args.no_specs, with_embeddings=not args.no_embed,
                  reindex=args.reindex)
    for key, value in summary.items():
        print(f"  {key}: {value}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
