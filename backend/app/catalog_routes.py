"""Consulta del catÃ¡logo de referencia: facetas exactas y bÃºsqueda semÃ¡ntica.

El catÃ¡logo no contiene datos del taller, pero se expone solo al personal
(`staff`): clientes y mecÃ¡nicos no necesitan el Ã¡rbol completo de vehÃ­culos.

La bÃºsqueda es hÃ­brida: significado (pgvector) mÃ¡s coincidencia textual. Si el
modelo de embeddings no estÃ¡ disponible, el endpoint sigue funcionando con la
parte textual en lugar de devolver un error.
"""
from __future__ import annotations

import math
import re
import unicodedata
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Text, cast, func, or_, select, text

from . import schemas
from .access_policy import audit
from .catalog_models import (
    EMBEDDED_ENTITIES, ENTITY_ENGINE, ENTITY_GENERATION, ENTITY_MAKE,
    ENTITY_MODEL, ENTITY_PART, ORIGIN_MANUAL, ORIGIN_NEEDS_REVIEW,
    CatalogAlias, CatalogEmbedding, CatalogPartTerm, CatalogRecordMeta,
    CatalogSource, VehicleEngine, VehicleGeneration, VehicleMake, VehicleModel,
    VehiclePart, VehiclePartFit,
)
from .dependencies import Database, admin, staff
from .embeddings import embedder
from .models import User
from .regional import normalize_text

router = APIRouter(prefix="/catalog", tags=["CatÃ¡logo de referencia"])


# PuntuaciÃ³n de la bÃºsqueda hÃ­brida. Ver `search`: lo textual ocupa la banda
# alta y lo semÃ¡ntico la baja, para que lo exacto nunca pierda.
TEXT_FLOOR = 0.5
SEMANTIC_CEILING = 0.45


def _text_match(query: str):
    pattern = f"%{query}%"
    return pattern


def _semantic(db: Database, entity_type: str, vector, limit: int) -> dict[int, float]:
    """Devuelve {entity_id: similitud 0..1}. pgvector si existe; numpy si no."""
    model_key = embedder().model_key
    dialect = db.get_bind().dialect.name
    if dialect == "postgresql":
        rows = db.execute(
            text(
                "SELECT entity_id, 1 - (vector <=> CAST(:v AS vector)) AS score "
                "FROM catalog_embeddings WHERE entity_type = :t AND model_key = :m "
                "ORDER BY vector <=> CAST(:v AS vector) LIMIT :l"
            ),
            {"v": "[" + ",".join(str(x) for x in vector) + "]", "t": entity_type,
             "m": model_key, "l": limit},
        ).fetchall()
        return {row[0]: float(row[1]) for row in rows}
    import numpy as np

    stored = db.execute(
        select(CatalogEmbedding.entity_id, CatalogEmbedding.vector).where(
            CatalogEmbedding.entity_type == entity_type,
            CatalogEmbedding.model_key == model_key)).all()
    target = np.asarray(vector, dtype=np.float32)
    scored = []
    for entity_id, blob in stored:
        value = np.frombuffer(blob, dtype=np.float32) if isinstance(blob, (bytes, bytearray)) else np.asarray(blob, dtype=np.float32)
        if value.shape != target.shape:
            continue
        scored.append((entity_id, float(np.dot(value, target))))
    scored.sort(key=lambda row: row[1], reverse=True)
    return dict(scored[:limit])


def _make_json(row, logo: bool = False) -> dict:
    # El logotipo viaja solo cuando se pide: son 165 filas y la lista se usa
    # para poblar selectores, donde la URL no aporta nada.
    return {"id": row.id, "slug": row.slug, "name": row.name, "country": row.country,
            "logo_url": row.logo_url if logo else None}


def _model_json(row) -> dict:
    return {"id": row.id, "slug": row.slug, "name": row.name, "make_id": row.make_id,
            "year_start": row.year_start, "year_end": row.year_end}


def _generation_json(row) -> dict:
    return {"id": row.id, "slug": row.slug, "name": row.name, "model_id": row.model_id,
            "year_start": row.year_start, "year_end": row.year_end, "body_type": row.body_type}


def _engine_json(row) -> dict:
    return {"id": row.id, "slug": row.slug, "label": row.label, "fuel_type": row.fuel_type,
            "cylinders": row.cylinders, "displacement_cc": row.displacement_cc,
            "power_hp": row.power_hp, "torque_nm": row.torque_nm,
            "transmission": row.transmission, "drivetrain": row.drivetrain,
            "zero_to_100_s": row.zero_to_100_s, "top_speed_kmh": row.top_speed_kmh,
            "fuel_economy_l100": row.fuel_economy_l100}


def _part_json(row, term=None) -> dict:
    # `title` es el nombre original de la fuente (inglÃ©s o ruso) y nunca se
    # sustituye. `name_es` es un atributo adicional, marcado como pendiente
    # cuando el glosario no pudo resolverlo con respaldo.
    result = {"id": row.id, "sku": row.sku, "mpn": row.mpn, "title": row.title,
              "brand": row.brand, "category": row.category}
    if term is not None:
        result |= {"name_es": term.name_es, "system": term.system,
                   "synonyms": term.synonyms or [], "keywords": term.keywords or [],
                   "review_required": term.review_required}
    return result


def _part_terms(db) -> dict[int, CatalogPartTerm]:
    return {row.part_id: row for row in db.scalars(select(CatalogPartTerm))}


# El serializador va como funciÃ³n, no como tupla de un elemento: `(f,)`
# convertÃ­a `to_json(row)` en una llamada sobre una tupla y rompÃ­a la bÃºsqueda
# entera. Este endpoint no se habÃ­a ejecutado nunca, asÃ­ que el fallo llevaba
# meses sin manifestarse.
FACETS = {
    ENTITY_MAKE: (VehicleMake, _make_json, (VehicleMake.name,)),
    ENTITY_MODEL: (VehicleModel, _model_json, (VehicleModel.name,)),
    ENTITY_GENERATION: (VehicleGeneration, _generation_json, (VehicleGeneration.name,)),
    ENTITY_ENGINE: (VehicleEngine, _engine_json, (VehicleEngine.label, VehicleEngine.fuel_type)),
    ENTITY_PART: (VehiclePart, _part_json, (VehiclePart.title, VehiclePart.brand, VehiclePart.category)),
}


def _text_ids(db, model, columns, query: str, limit: int) -> list[int]:
    return [row.id for row in db.scalars(
        select(model).where(or_(*[column.ilike(_text_match(query)) for column in columns])).limit(limit))]


def _part_text_ids(db, query: str, limit: int) -> list[int]:
    """Busca un repuesto por tÃ­tulo, categorÃ­a y tambiÃ©n por su nombre en
    espaÃ±ol, sinÃ³nimos y palabras clave. Un tÃ©cnico escribe "pastillas"; el
    tÃ­tulo original es `Brake pad` y la traducciÃ³n es `Pastilla de freno`.

    `synonyms` y `keywords` son columnas JSON: `ILIKE` no tiene operador sobre
    `json`, hay que castear a texto explÃ­citamente.
    """
    ids = _text_ids(db, VehiclePart, FACETS[ENTITY_PART][2], query, limit)
    if len(ids) >= limit:
        return ids
    pattern = _text_match(query)
    synonyms = cast(CatalogPartTerm.synonyms, Text)
    keywords = cast(CatalogPartTerm.keywords, Text)
    rows = db.execute(
        select(CatalogPartTerm.part_id).where(
            CatalogPartTerm.name_es.ilike(pattern)
            | synonyms.ilike(pattern)
            | keywords.ilike(pattern)
        ).limit(limit))
    for (part_id,) in rows:
        if part_id not in ids:
            ids.append(part_id)
    return ids


@router.get("/sources")
def sources(db: Database, _: User = Depends(admin)):
    """Procedencia y licencias: el import deja constancia de cada fuente."""
    return [{"source_key": row.source_key, "title": row.title, "url": row.url,
             "license": row.license, "license_url": row.license_url,
             "attribution": row.attribution, "row_count": row.row_count,
             "fetched_at": row.fetched_at.isoformat()}
            for row in db.scalars(select(CatalogSource).order_by(CatalogSource.source_key))]


@router.get("/status")
def status(db: Database, _: User = Depends(staff)):
    info = embedder().status()
    counts = {}
    for entity in EMBEDDED_ENTITIES:
        counts[entity] = db.scalar(
            select(func.count(CatalogEmbedding.entity_id)).where(
                CatalogEmbedding.entity_type == entity,
                CatalogEmbedding.model_key == info["model"]))
    return {"embeddings": info, "indexed": counts,
            "makes": db.scalar(select(func.count(VehicleMake.id))),
            "models": db.scalar(select(func.count(VehicleModel.id))),
            "engines": db.scalar(select(func.count(VehicleEngine.id))),
            "parts": db.scalar(select(func.count(VehiclePart.id))),
            "part_fits": db.scalar(select(func.count(VehiclePartFit.id)))}


@router.get("/makes")
def makes(db: Database, _: User = Depends(staff), q: str = "", logo: bool = False, limit: int = Query(200, ge=1, le=1000)):
    query = select(VehicleMake)
    if q:
        query = query.where(VehicleMake.name.ilike(_text_match(q)))
    rows = db.scalars(query.order_by(VehicleMake.name).limit(limit)).all()
    return [_make_json(row, logo) for row in rows]


@router.get("/models")
def models(db: Database, _: User = Depends(staff), make_id: int | None = None,
           year: int | None = None, q: str = "", limit: int = Query(200, ge=1, le=1000)):
    query = select(VehicleModel)
    if make_id:
        query = query.where(VehicleModel.make_id == make_id)
    if year:
        query = query.where(
            (VehicleModel.year_start.is_(None)) | (VehicleModel.year_start <= year),
            (VehicleModel.year_end.is_(None)) | (VehicleModel.year_end >= year))
    if q:
        query = query.where(VehicleModel.name.ilike(_text_match(q)))
    rows = db.scalars(query.order_by(VehicleModel.name).limit(limit)).all()
    return [_model_json(row) for row in rows]


@router.get("/generations")
def generations(db: Database, model_id: int, _: User = Depends(staff)):
    rows = db.scalars(
        select(VehicleGeneration).where(VehicleGeneration.model_id == model_id)
        .order_by(VehicleGeneration.year_start.desc())).all()
    return [_generation_json(row) for row in rows]


@router.get("/engines")
def engines(db: Database, generation_id: int, limit: int = Query(200, ge=1, le=1000),
            _: User = Depends(staff)):
    rows = db.scalars(
        select(VehicleEngine).where(VehicleEngine.generation_id == generation_id)
        .order_by(VehicleEngine.power_hp.desc()).limit(limit)).all()
    return [_engine_json(row) for row in rows]


@router.get("/parts/for-model/{model_id}")
def parts_for_model(db: Database, model_id: int, year: int | None = None,
                    limit: int = Query(100, ge=1, le=500), _: User = Depends(staff)):
    """Repuestos declarados como compatibles con un modelo del catÃ¡logo."""
    query = (
        select(VehiclePart, VehiclePartFit)
        .join(VehiclePartFit, VehiclePartFit.part_id == VehiclePart.id)
        .where(VehiclePartFit.model_id == model_id)
    )
    if year:
        query = query.where(
            or_(VehiclePartFit.year_from.is_(None), VehiclePartFit.year_from <= year),
            or_(VehiclePartFit.year_to.is_(None), VehiclePartFit.year_to >= year))
    seen, out = set(), []
    terms = _part_terms(db)
    for part, fit in db.execute(query.limit(limit * 4)):
        if part.id in seen:
            continue
        seen.add(part.id)
        out.append({**_part_json(part, terms.get(part.id)),
                    "year_from": fit.year_from, "year_to": fit.year_to})
        if len(out) >= limit:
            break
    return out


@router.get("/search")
def search(db: Database, _: User = Depends(staff), q: str = Query(min_length=2, max_length=120),
           type: str | None = None, limit: int = Query(12, ge=1, le=50),
           semantic_weight: float = Query(0.7, ge=0, le=1)):
    """BÃºsqueda hÃ­brida: significado + coincidencia textual."""
    wanted = [type] if type else list(FACETS)
    for entity in wanted:
        if entity not in FACETS:
            raise HTTPException(422, f"Tipo de catÃ¡logo desconocido: {entity}")

    semantic = {}
    mode = "text"
    engine = embedder()
    if engine.available():
        try:
            vector = engine.encode_one(q)
            semantic = {entity: _semantic(db, entity, vector, limit * 4) for entity in wanted}
            mode = "hybrid" if semantic else "text"
        except RuntimeError:
            semantic = {}

    results = {}
    terms = _part_terms(db) if ENTITY_PART in wanted else {}
    for entity in wanted:
        model, to_json, columns = FACETS[entity]
        if entity == ENTITY_PART:
            text_ids = _part_text_ids(db, q, limit * 4)
        else:
            text_ids = _text_ids(db, model, columns, q, limit * 4)
        sem = semantic.get(entity, {})
        merged = {}
        # Bandas separadas y deliberadamente solapadas por poco: una
        # coincidencia textual nunca puntÃºa por debajo de TEXT_FLOOR, y una
        # semÃ¡ntica nunca supera SEMANTIC_CEILING. Con el reparto anterior
        # (texto por `(1-peso)*...`, semÃ¡ntica por `peso*similitud`) cualquier
        # coincidencia semÃ¡ntica desplazaba a todas las textuales, y se midiÃ³
        # que la bÃºsqueda hÃ­brida era PEOR que la textual: 63,6 % frente a
        # 90,9 %. Ahora lo textual manda y lo semÃ¡ntico solo amplÃ­a el
        #_recuperado_ con lo que el texto no encontrÃ³.
        for rank, entity_id in enumerate(text_ids):
            merged[entity_id] = 1.0 - TEXT_FLOOR * (rank / max(len(text_ids), 1))
        for entity_id, score in sem.items():
            if semantic_weight <= 0:
                # Con peso 0 el usuario pide solo texto. AÃ±adir los candidatos
                # semÃ¡nticos con puntuaciÃ³n 0 los colaba en el ranking.
                continue
            merged[entity_id] = max(
                merged.get(entity_id, 0.0),
                semantic_weight * SEMANTIC_CEILING * max(score, 0.0))
        ranked = sorted(merged.items(), key=lambda row: row[1], reverse=True)[:limit]
        if not ranked:
            results[entity] = []
            continue
        by_id = {row.id: row for row in db.scalars(
            select(model).where(model.id.in_([entity_id for entity_id, _ in ranked])))}

        def serialize(row):
            return (to_json(row, terms.get(row.id)) if entity == ENTITY_PART
                    else to_json(row))

        results[entity] = [{**serialize(by_id[entity_id]), "score": round(score, 4)}
                           for entity_id, score in ranked if entity_id in by_id]
    return {"query": q, "mode": mode, "weight": semantic_weight, "results": results}
# --------------------------------------------------------------------------- #
# Registro manual
# --------------------------------------------------------------------------- #
# El catálogo de fuentes es global y no cubre todo el mercado ecuatoriano: se
# comprobó que Chevrolet Sail, Optra y Lanos no aparecen en ninguna. Estas
# rutas permiten registrar lo que falta, de verdad en la base, con autor y
# procedencia, y sin crear duplicados por ignorancia.

def _slug_for(name: str, taken: set[str]) -> str:
    """Slug estable a partir del nombre, sin colisionar con lo existente."""
    base = re.sub(r"[^a-z0-9]+", "-", unicodedata.normalize("NFKD", name or "").lower()).strip("-")
    base = base or "sin-nombre"
    if base not in taken:
        return base
    for suffix in range(2, 1000):
        candidate = f"{base}-{suffix}"
        if candidate not in taken:
            return candidate
    raise HTTPException(409, "No se pudo generar un identificador único")


def _register(db: Database, entity_type: str, entity_id: int, user) -> CatalogRecordMeta:
    """Deja constancia del origen: lo que propone un mecánico queda pendiente de
    revisión y lo que registra un administrador se da por bueno. Nada entra en
    el catálogo compartido sin que alguien del taller lo asuma."""
    origin = (ORIGIN_MANUAL if user.role == "admin" else ORIGIN_NEEDS_REVIEW)
    meta = CatalogRecordMeta(entity_type=entity_type, entity_id=entity_id,
                             source_key="manual", origin=origin,
                             created_by=user.id)
    db.add(meta)
    return meta


def _similar(db: Database, model, column, value: str, exclude_id: int | None = None, limit: int = 6):
    """Coincidencias por normalización, para no duplicar por diferencia de
    acentos, mayúsculas o separadores."""
    needle = normalize_text(value)
    if not needle:
        return []
    found = []
    for row in db.scalars(select(model).where(column.ilike(f"%{value}%")).limit(limit * 4)):
        if exclude_id is not None and row.id == exclude_id:
            continue
        candidate = normalize_text(getattr(row, column.key))
        if candidate == needle or needle in candidate or candidate in needle:
            found.append(row)
        if len(found) >= limit:
            break
    return found


@router.get("/suggest")
def suggest(db: Database, _: User = Depends(staff),
            q: str = Query(min_length=2, max_length=120), limit: int = Query(8, ge=1, le=20)):
    """Posibles coincidencias antes de crear. Se llama antes de registrar algo
    para ofrecer reutilizar en lugar de duplicar."""
    out = {"makes": [], "models": [], "generations": [], "parts": [], "aliases": []}
    for make in _similar(db, VehicleMake, VehicleMake.name, q, limit=limit):
        out["makes"].append(_make_json(make))
    for model_row in _similar(db, VehicleModel, VehicleModel.name, q, limit=limit):
        make = db.get(VehicleMake, model_row.make_id)
        out["models"].append({**_model_json(model_row), "make_name": make.name if make else None})
    for generation in _similar(db, VehicleGeneration, VehicleGeneration.name, q, limit=limit):
        out["generations"].append(_generation_json(generation))
    for alias in db.scalars(select(CatalogAlias).where(CatalogAlias.alias.ilike(f"%{q}%")).limit(limit)):
        out["aliases"].append({"alias": alias.alias, "entity_type": alias.entity_type,
                               "entity_id": alias.entity_id, "verified": alias.verified})
    for part in _similar(db, VehiclePart, VehiclePart.title, q, limit=limit):
        out["parts"].append(_part_json(part, _part_terms(db).get(part.id)))
    return out


@router.post("/makes", status_code=201)
def create_make(data: schemas.ManualMakeInput, db: Database, user: User = Depends(admin)):
    """Registra una marca que no está en las fuentes. Requiere administrador:
    la marca es la raíz del catálogo compartido."""
    taken = set(db.scalars(select(VehicleMake.slug)))
    slug = _slug_for(data.name, taken)
    make = VehicleMake(slug=slug, name=data.name.strip(), country=(data.country or "").strip() or None)
    db.add(make)
    db.flush()
    _register(db, ENTITY_MAKE, make.id, user)
    for alias in data.aliases:
        key = alias.strip()[:120]
        if normalize_text(key) == normalize_text(make.name):
            continue
        db.add(CatalogAlias(alias=key, normalized=normalize_text(key),
                            entity_type=ENTITY_MAKE, entity_id=make.id,
                            verified=user.role == "admin", source_key="manual"))
    db.flush()
    audit(db, user, "catalog.make_created", "catalog_make", make.id,
          {"slug": slug, "note": data.note})
    return {**_make_json(make), "origin": "manual", "aliases": data.aliases}


@router.post("/models", status_code=201)
def create_model(data: schemas.ManualModelInput, db: Database, user: User = Depends(staff)):
    make = db.get(VehicleMake, data.make_id)
    if make is None:
        raise HTTPException(404, "Marca no encontrada")
    slug = _slug_for(f"{make.slug}--{data.name}",
                     set(db.scalars(select(VehicleModel.slug))))
    model_row = VehicleModel(make_id=make.id, slug=slug, name=data.name.strip(),
                             year_start=data.year_start, year_end=data.year_end)
    db.add(model_row)
    db.flush()
    meta = _register(db, ENTITY_MODEL, model_row.id, user)
    audit(db, user, "catalog.model_created", "catalog_model", model_row.id,
          {"make_id": make.id, "note": data.note})
    return {**_model_json(model_row), "make_name": make.name, "origin": meta.origin}


@router.post("/generations", status_code=201)
def create_generation(data: schemas.ManualGenerationInput, db: Database, user: User = Depends(staff)):
    model_row = db.get(VehicleModel, data.model_id)
    if model_row is None:
        raise HTTPException(404, "Modelo no encontrado")
    slug = _slug_for(f"{model_row.slug}--{data.name}--{data.year_start or ''}",
                     set(db.scalars(select(VehicleGeneration.slug))))
    generation = VehicleGeneration(model_id=model_row.id, slug=slug, name=data.name.strip(),
                                   year_start=data.year_start, year_end=data.year_end,
                                   body_type=(data.body_type or "").strip() or None)
    db.add(generation)
    db.flush()
    meta = _register(db, ENTITY_GENERATION, generation.id, user)
    audit(db, user, "catalog.generation_created", "catalog_generation", generation.id,
          {"model_id": model_row.id, "note": data.note})
    return {**_generation_json(generation), "origin": meta.origin}


@router.post("/engines", status_code=201)
def create_engine(data: schemas.ManualEngineInput, db: Database, user: User = Depends(staff)):
    generation = db.get(VehicleGeneration, data.generation_id)
    if generation is None:
        raise HTTPException(404, "Generación no encontrada")
    slug = _slug_for(f"{generation.slug}--manual",
                     set(db.scalars(select(VehicleEngine.slug))))
    engine = VehicleEngine(
        generation_id=generation.id, slug=slug, label=data.label.strip(),
        fuel_type=data.fuel_type, cylinders=data.cylinders,
        displacement_cc=data.displacement_cc, power_hp=data.power_hp,
        torque_nm=data.torque_nm, transmission=data.transmission, drivetrain=data.drivetrain)
    db.add(engine)
    db.flush()
    meta = _register(db, ENTITY_ENGINE, engine.id, user)
    audit(db, user, "catalog.engine_created", "catalog_engine", engine.id,
          {"generation_id": generation.id, "note": data.note})
    return {**_engine_json(engine), "origin": meta.origin,
            "aviso": "Datos introducidos manualmente: verifíquelos antes de publicarlos"}


@router.post("/parts", status_code=201)
def create_part(data: schemas.ManualPartInput, db: Database, user: User = Depends(staff)):
    sku = (data.sku or "").strip() or f"manual:{_slug_for(data.title, set())}"
    existing = db.scalar(select(VehiclePart).where(VehiclePart.sku == sku))
    if existing is not None:
        raise HTTPException(409, f"Ya existe un repuesto con el código {sku}")
    name_es = (data.name_es or "").strip() or None
    part = VehiclePart(sku=sku[:80], title=data.title.strip(),
                       brand=(data.brand or "").strip() or None,
                       category=(data.system or "").strip() or None)
    db.add(part)
    db.flush()
    meta = _register(db, ENTITY_PART, part.id, user)
    if name_es:
        db.add(CatalogPartTerm(
            part_id=part.id, source_key="manual", name_es=name_es[:200],
            system=data.system, synonyms=[item for item in data.synonyms if item] or None,
            keywords=[item for item in data.keywords if item] or None,
            review_required=user.role != "admin",
            translated_by=f"usuario:{user.id}",
            translated_at=datetime.now(timezone.utc)))
        db.flush()
    audit(db, user, "catalog.part_created", "catalog_part", part.id,
          {"sku": sku, "note": data.note})
    # Se lee lo realmente guardado en lugar de reconstruirlo en memoria: así
    # la respuesta no puede contradecir la base.
    return {**_part_json(part, db.get(CatalogPartTerm, (part.id, "manual"))),
            "origin": meta.origin}
