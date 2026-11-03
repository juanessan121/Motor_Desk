"""Revisión de propuestas manuales, limitada al taller de su autor.

El catálogo es compartido; esta cola no lo convierte en un listado de usuarios
de otros talleres. Conservar pendiente nunca elimina ni archiva la ficha.
"""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, update

from . import schemas
from .access_policy import audit
from .catalog_models import (
    ORIGIN_NEEDS_REVIEW, ORIGIN_VERIFIED, CatalogAlias, CatalogPartTerm,
    CatalogRecordMeta, VehicleEngine, VehicleGeneration, VehicleModel,
)
from .catalog_routes import FACETS
from .dependencies import Database, admin, invalidate
from .models import AuditEvent, User, utcnow

router = APIRouter(prefix='/catalog', tags=['Revisión del catálogo'])
Entity = Literal['make', 'model', 'generation', 'engine', 'part']


def _scope(user):
    return (
        CatalogRecordMeta.source_key == 'manual',
        CatalogRecordMeta.created_by.in_(select(User.id).where(User.workshop_id == user.workshop_id)),
    )


def _review_json(db, meta):
    model, serialize, _ = FACETS[meta.entity_type]
    record = db.get(model, meta.entity_id)
    author = db.get(User, meta.created_by) if meta.created_by else None
    creation = db.scalar(select(AuditEvent).where(
        AuditEvent.resource_type == f'catalog_{meta.entity_type}',
        AuditEvent.resource_id == meta.entity_id,
        AuditEvent.action == f'catalog.{meta.entity_type}_created',
        AuditEvent.actor_id == meta.created_by,
    ).order_by(AuditEvent.id).limit(1))
    parents = []
    current, kind = record, meta.entity_type
    parent_fields = {'model': ('make', 'make_id'), 'generation': ('model', 'model_id'),
                     'engine': ('generation', 'generation_id')}
    while current is not None and kind in parent_fields:
        kind, field = parent_fields[kind]
        current = db.get(FACETS[kind][0], getattr(current, field))
        if current is not None:
            parents.insert(0, {'entity_type': kind, 'id': current.id, 'name': current.name})
    terms = list(db.scalars(select(CatalogPartTerm).where(
        CatalogPartTerm.part_id == meta.entity_id, CatalogPartTerm.source_key == 'manual'))
    ) if meta.entity_type == 'part' else []
    return {
        'entity_type': meta.entity_type, 'entity_id': meta.entity_id,
        'record': serialize(record) if record is not None else None,
        'parents': parents,
        'origin': meta.origin, 'source_key': meta.source_key, 'revision': meta.revision,
        'created_by': meta.created_by, 'created_by_name': author.username if author else None,
        'created_at': meta.created_at.isoformat(),
        'proposal_note': (creation.payload.get('note', '') if creation else ''),
        'reviewed_by': meta.reviewed_by,
        'reviewed_at': meta.reviewed_at.isoformat() if meta.reviewed_at else None,
        'review_note': meta.review_note,
        'terms': [{'name_es': term.name_es, 'synonyms': term.synonyms or [],
                   'system': term.system, 'review_required': term.review_required} for term in terms],
    }


@router.get('/review-queue')
def review_queue(db: Database, user: User = Depends(admin),
                 entity_type: Entity | None = None,
                 state: Literal['needs_review', 'verified'] = 'needs_review',
                 limit: int = Query(30, ge=1, le=100), offset: int = Query(0, ge=0)):
    query = select(CatalogRecordMeta).where(*_scope(user), CatalogRecordMeta.origin == state)
    if entity_type is not None:
        query = query.where(CatalogRecordMeta.entity_type == entity_type)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.scalars(query.order_by(CatalogRecordMeta.created_at, CatalogRecordMeta.entity_type,
                                    CatalogRecordMeta.entity_id).offset(offset).limit(limit))
    return {'items': [_review_json(db, row) for row in rows], 'total': total,
            'offset': offset, 'limit': limit}


@router.post('/review-queue/{entity_type}/{entity_id}')
def review_record(entity_type: Entity, entity_id: int, data: schemas.CatalogReviewInput,
                  db: Database, user: User = Depends(admin)):
    meta = db.scalar(select(CatalogRecordMeta).where(
        *_scope(user), CatalogRecordMeta.entity_type == entity_type,
        CatalogRecordMeta.entity_id == entity_id).with_for_update())
    if meta is None:
        raise HTTPException(404, 'Propuesta manual no encontrada en este taller')
    if meta.origin != ORIGIN_NEEDS_REVIEW or meta.revision != data.expected_revision:
        raise HTTPException(409, 'El registro cambió; actualice la cola antes de revisarlo')
    model, _, _ = FACETS[entity_type]
    record = db.get(model, entity_id)
    if record is None:
        raise HTTPException(404, 'La ficha del catálogo ya no existe')
    if data.decision == 'verify':
        parent = None
        if isinstance(record, VehicleModel):
            parent = ('make', record.make_id)
        elif isinstance(record, VehicleGeneration):
            parent = ('model', record.model_id)
        elif isinstance(record, VehicleEngine):
            parent = ('generation', record.generation_id)
        parent_meta = db.get(CatalogRecordMeta, parent) if parent else None
        if parent_meta is not None and parent_meta.origin == ORIGIN_NEEDS_REVIEW:
            raise HTTPException(409, 'Primero debe verificarse la ficha superior del catálogo')
    before = _review_json(db, meta)
    now = utcnow()
    result = db.execute(update(CatalogRecordMeta).where(
        CatalogRecordMeta.entity_type == entity_type, CatalogRecordMeta.entity_id == entity_id,
        CatalogRecordMeta.origin == ORIGIN_NEEDS_REVIEW,
        CatalogRecordMeta.revision == data.expected_revision,
    ).values(origin=ORIGIN_VERIFIED if data.decision == 'verify' else ORIGIN_NEEDS_REVIEW,
             revision=data.expected_revision + 1, reviewed_by=user.id, reviewed_at=now,
             review_note=data.note, updated_at=now))
    if result.rowcount != 1:
        raise HTTPException(409, 'Otro administrador revisó el registro; actualice la cola')
    if data.decision == 'verify':
        db.execute(update(CatalogAlias).where(
            CatalogAlias.entity_type == entity_type, CatalogAlias.entity_id == entity_id,
            CatalogAlias.source_key == 'manual').values(verified=True))
        if entity_type == 'part':
            # No certifica traducciones importadas de otras fuentes.
            db.execute(update(CatalogPartTerm).where(
                CatalogPartTerm.part_id == entity_id, CatalogPartTerm.source_key == 'manual'
            ).values(review_required=False))
    audit(db, user, 'catalog.record_reviewed', f'catalog_{entity_type}', entity_id,
          {'decision': data.decision, 'note': data.note,
           'previous_revision': data.expected_revision, 'before': before})
    invalidate(db)
    db.flush()
    db.refresh(meta)
    return _review_json(db, meta)
