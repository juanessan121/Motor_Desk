"""Consulta paginada del catálogo maestro; independiente de la cola de revisión."""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Text, case, cast, exists, func, or_, select

from .catalog_models import (
    CatalogAlias, CatalogPartTerm, CatalogRecordMeta, CatalogSource,
    VehicleEngine, VehicleEngineSpec, VehicleGeneration, VehicleMake,
    VehicleModel, VehiclePart, VehiclePartFit,
)
from .catalog_routes import FACETS, _make_json, _part_json, _semantic
from .dependencies import Database, staff
from .embeddings import embedder
from .models import User
from .regional import normalize_text

router = APIRouter(prefix='/catalog', tags=['Consulta del catálogo'])
Entity = Literal['make', 'model', 'generation', 'engine', 'part']
Sort = Literal['name_asc', 'name_desc', 'code_asc', 'code_desc']


def visible(entity, model, user):
    """No difundir propuestas pendientes de personal de otro taller."""
    own_authors = select(User.id).where(User.workshop_id == user.workshop_id)
    hidden = select(CatalogRecordMeta.entity_id).where(
        CatalogRecordMeta.entity_type == entity,
        CatalogRecordMeta.origin == 'needs_review',
        or_(CatalogRecordMeta.created_by.is_(None), ~CatalogRecordMeta.created_by.in_(own_authors)))
    return ~model.id.in_(hidden)


def source_json(row):
    license_url = row.license_url
    if row.source_key == 'logos' and license_url.endswith('/LICENSE'):
        license_url = row.url.rstrip('/') + '/blob/master/package.json'
    return {'key': row.source_key, 'title': row.title, 'url': row.url,
            'license': row.license, 'license_url': license_url,
            'attribution': row.attribution, 'imported_at': row.fetched_at.isoformat(),
            'content_hash': row.content_hash, 'row_count': row.row_count}


def preferred_terms(db, ids):
    result = {}
    if not ids:
        return result
    rows = db.scalars(select(CatalogPartTerm).where(CatalogPartTerm.part_id.in_(ids)).order_by(
        case((CatalogPartTerm.source_key == 'manual', 0), (CatalogPartTerm.review_required.is_(False), 1), else_=2),
        CatalogPartTerm.source_key))
    for row in rows:
        result.setdefault(row.part_id, row)
    return result


def serialize_rows(db, entity, rows):
    ids = [row.id for row in rows]
    terms = preferred_terms(db, ids) if entity == 'part' else {}
    metas = {row.entity_id: row for row in db.scalars(select(CatalogRecordMeta).where(
        CatalogRecordMeta.entity_type == entity, CatalogRecordMeta.entity_id.in_(ids)))} if ids else {}
    fits = dict(db.execute(select(VehiclePartFit.part_id, func.count()).where(
        VehiclePartFit.part_id.in_(ids), VehiclePartFit.model_id.is_not(None)
    ).group_by(VehiclePartFit.part_id)).all()) if entity == 'part' and ids else {}
    result = []
    for row in rows:
        if entity == 'part':
            data = _part_json(row, terms.get(row.id))
            data['compatibilities_count'] = fits.get(row.id, 0)
        elif entity == 'make':
            data = _make_json(row, logo=True)
        else:
            data = FACETS[entity][1](row)
        meta = metas.get(row.id)
        data.update(origin=meta.origin if meta else 'unknown',
                    source_key=meta.source_key if meta else None)
        result.append(data)
    return result


def browse_records(db, user, *, entity, q='', make_id=None, model_id=None,
                   generation_id=None, year=None, category=None, system=None,
                   manufacturer=None, source=None, sort='name_asc', semantic=False,
                   limit=20, offset=0):
    model = FACETS[entity][0]
    query = select(model).where(visible(entity, model, user))
    available = db.scalar(select(func.count()).select_from(query.subquery()))
    if source:
        query = query.where(exists().where(CatalogRecordMeta.entity_type == entity,
            CatalogRecordMeta.entity_id == model.id, CatalogRecordMeta.source_key == source))
    if entity == 'model' and make_id is not None:
        query = query.where(VehicleModel.make_id == make_id)
    if entity == 'generation':
        if model_id is not None:
            query = query.where(VehicleGeneration.model_id == model_id)
        if make_id is not None:
            query = query.where(VehicleGeneration.model_id.in_(select(VehicleModel.id).where(VehicleModel.make_id == make_id)))
    if entity == 'engine':
        if generation_id is not None:
            query = query.where(VehicleEngine.generation_id == generation_id)
        if model_id is not None:
            query = query.where(VehicleEngine.generation_id.in_(select(VehicleGeneration.id).where(VehicleGeneration.model_id == model_id)))
        if make_id is not None:
            query = query.where(VehicleEngine.generation_id.in_(select(VehicleGeneration.id).join(VehicleModel).where(VehicleModel.make_id == make_id)))
    if year is not None and entity in ('model', 'generation'):
        query = query.where(or_(model.year_start.is_(None), model.year_start <= year),
                            or_(model.year_end.is_(None), model.year_end >= year))
    if year is not None and entity == 'engine':
        query = query.where(VehicleEngine.generation_id.in_(select(VehicleGeneration.id).where(
            or_(VehicleGeneration.year_start.is_(None), VehicleGeneration.year_start <= year),
            or_(VehicleGeneration.year_end.is_(None), VehicleGeneration.year_end >= year))))
    if entity == 'part':
        if category:
            query = query.where(VehiclePart.category == category)
        if manufacturer:
            query = query.where(VehiclePart.brand == manufacturer)
        if system:
            query = query.where(exists().where(CatalogPartTerm.part_id == VehiclePart.id, CatalogPartTerm.system == system))
        if model_id is not None or make_id is not None:
            fit = select(VehiclePartFit.id).where(VehiclePartFit.part_id == VehiclePart.id, VehiclePartFit.model_id.is_not(None))
            if model_id is not None:
                fit = fit.where(VehiclePartFit.model_id == model_id)
            if make_id is not None:
                fit = fit.where(VehiclePartFit.model_id.in_(select(VehicleModel.id).where(VehicleModel.make_id == make_id)))
            if year is not None:
                fit = fit.where(or_(VehiclePartFit.year_from.is_(None), VehiclePartFit.year_from <= year),
                                or_(VehiclePartFit.year_to.is_(None), VehiclePartFit.year_to >= year))
            query = query.where(fit.exists())
    name = model.title if entity == 'part' else model.label if entity == 'engine' else model.name
    if entity == 'part':
        translated_name = select(CatalogPartTerm.name_es).where(CatalogPartTerm.part_id == model.id).order_by(
            case((CatalogPartTerm.source_key == 'manual', 0), else_=1), CatalogPartTerm.review_required,
            CatalogPartTerm.source_key).limit(1).scalar_subquery()
        name = func.coalesce(translated_name, name)
    mode = 'text'
    if q.strip():
        pattern = '%' + q.strip().replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'
        columns = FACETS[entity][2]
        if entity == 'part':
            columns = (*columns, VehiclePart.sku, VehiclePart.mpn)
        match = or_(*[column.ilike(pattern, escape='\\') for column in columns])
        if entity == 'part':
            match = or_(match, exists().where(CatalogPartTerm.part_id == model.id, or_(
                CatalogPartTerm.name_es.ilike(pattern, escape='\\'),
                CatalogPartTerm.system.ilike(pattern, escape='\\'),
                cast(CatalogPartTerm.synonyms, Text).ilike(pattern, escape='\\'),
                cast(CatalogPartTerm.keywords, Text).ilike(pattern, escape='\\'))))
        match = or_(match, exists().where(CatalogAlias.entity_type == entity,
            CatalogAlias.entity_id == model.id, CatalogAlias.verified.is_(True),
            CatalogAlias.normalized == normalize_text(q)))
        scores = {}
        if semantic and len(q.strip()) >= 2:
            engine = embedder()
            if engine.available():
                try:
                    scores = _semantic(db, entity, engine.encode_one(q.strip()), 1000)
                    mode = 'hybrid'
                except (RuntimeError, OSError, ValueError):
                    pass
        query = query.where(or_(match, model.id.in_(scores)) if scores else match)
        # Todos los filtros relacionales se mantienen: similitud no significa compatibilidad.
        query = query.order_by(case((match, 0), else_=1))
        if scores:
            query = query.order_by(case(scores, value=model.id, else_=0).desc())
    total = db.scalar(select(func.count()).select_from(query.order_by(None).subquery()))
    order = model.sku if entity == 'part' and sort.startswith('code') else name
    query = query.order_by(order.desc() if sort.endswith('desc') else order.asc(), model.id)
    rows = list(db.scalars(query.offset(offset).limit(limit)))
    return {'items': serialize_rows(db, entity, rows), 'total': total, 'available': available,
            'offset': offset, 'limit': limit, 'mode': mode,
            'empty_reason': ('empty_catalog' if not available else 'no_documented_fits' if entity == 'part' and (make_id or model_id) else 'no_matches') if not total else None}


@router.get('/overview')
def overview(db: Database, user: User = Depends(staff)):
    counts = {entity: db.scalar(select(func.count(model.id)).where(visible(entity, model, user)))
              for entity, (model, _, _) in FACETS.items()}
    return {'counts': counts, 'logos': db.scalar(select(func.count(VehicleMake.id)).where(VehicleMake.logo_url.is_not(None))),
            'sources': [source_json(row) for row in db.scalars(select(CatalogSource).order_by(CatalogSource.source_key))]}


@router.get('/browse')
def browse(db: Database, user: User = Depends(staff), entity: Entity = 'make',
           q: str = Query('', max_length=120), make_id: int | None = Query(None, gt=0),
           model_id: int | None = Query(None, gt=0), generation_id: int | None = Query(None, gt=0),
           year: int | None = Query(None, ge=1900, le=2200), sort: Sort = 'name_asc',
           limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0)):
    return browse_records(db, user, entity=entity, q=q, make_id=make_id, model_id=model_id,
                          generation_id=generation_id, year=year, sort=sort, limit=limit, offset=offset)


@router.get('/parts/filters')
def part_filters(db: Database, user: User = Depends(staff)):
    allowed = select(VehiclePart.id).where(visible('part', VehiclePart, user))
    def values(column, model):
        key = model.part_id if model == CatalogPartTerm else model.id
        return list(db.scalars(select(column).where(column.is_not(None), column != '', key.in_(allowed)).distinct().order_by(column)))
    return {'categories': values(VehiclePart.category, VehiclePart),
            'manufacturers': values(VehiclePart.brand, VehiclePart),
            'systems': values(CatalogPartTerm.system, CatalogPartTerm),
            'sources': list(db.scalars(select(CatalogRecordMeta.source_key).where(
                CatalogRecordMeta.entity_type == 'part', CatalogRecordMeta.entity_id.in_(allowed)
            ).distinct().order_by(CatalogRecordMeta.source_key)))}


@router.get('/parts')
def parts(db: Database, user: User = Depends(staff), q: str = Query('', max_length=120),
          category: str | None = None, system: str | None = None, manufacturer: str | None = None,
          source: str | None = None, make_id: int | None = Query(None, gt=0),
          model_id: int | None = Query(None, gt=0), year: int | None = Query(None, ge=1900, le=2200),
          semantic: bool = False, sort: Sort = 'name_asc',
          limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0)):
    return browse_records(db, user, entity='part', q=q, category=category, system=system,
        manufacturer=manufacturer, source=source, make_id=make_id, model_id=model_id,
        year=year, semantic=semantic, sort=sort, limit=limit, offset=offset)


@router.get('/records/{entity}/{record_id}')
def record_detail(entity: Entity, record_id: int, db: Database, user: User = Depends(staff),
                  offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200)):
    model = FACETS[entity][0]
    row = db.scalar(select(model).where(model.id == record_id, visible(entity, model, user)))
    if row is None:
        raise HTTPException(404, 'Ficha de catálogo no encontrada')
    record = serialize_rows(db, entity, [row])[0]
    record.update({column.name: getattr(row, column.name) for column in model.__table__.columns})
    meta = db.get(CatalogRecordMeta, (entity, record_id))
    source = db.get(CatalogSource, meta.source_key) if meta else None
    parents, current, kind = [], row, entity
    fields = {'model': ('make', 'make_id'), 'generation': ('model', 'model_id'), 'engine': ('generation', 'generation_id')}
    while kind in fields:
        kind, field = fields[kind]
        current = db.get(FACETS[kind][0], getattr(current, field))
        if current is None:
            break
        parents.insert(0, {'entity': kind, 'id': current.id, 'name': current.name})
    details, total = [], 0
    if entity == 'engine':
        query = select(VehicleEngineSpec).where(VehicleEngineSpec.engine_id == record_id)
        total = db.scalar(select(func.count()).select_from(query.subquery()))
        details = [{'key': item.key, 'value': item.value} for item in db.scalars(query.order_by(VehicleEngineSpec.id).offset(offset).limit(limit))]
    elif entity == 'part':
        query = select(VehiclePartFit, VehicleModel, VehicleMake).join(VehicleModel, VehicleModel.id == VehiclePartFit.model_id).join(VehicleMake, VehicleMake.id == VehicleModel.make_id).where(VehiclePartFit.part_id == record_id)
        total = db.scalar(select(func.count()).select_from(query.subquery()))
        details = [{'make': make.name, 'model': car.name, 'model_id': car.id,
                    'year_from': fit.year_from, 'year_to': fit.year_to, 'source_key': fit.source_key}
                   for fit, car, make in db.execute(query.order_by(VehiclePartFit.id).offset(offset).limit(limit))]
    return {'record': record, 'parents': parents, 'source': source_json(source) if source else None,
            'details': details, 'details_total': total, 'offset': offset, 'limit': limit,
            'notice': 'Información de catálogo global; no certifica un vehículo concreto ni disponibilidad en Ecuador.'}
