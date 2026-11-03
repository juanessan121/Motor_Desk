"""Referencias al catálogo, no diagnósticos ni identificación por VIN.

Solo se enlazan nombres exactos normalizados o alias verificados. No se usan
prefijos ni similitud semántica para escribir una relación persistente.
El motor siempre requiere selección explícita; nunca se deduce del año.
"""
from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .catalog_models import (
    ORIGIN_NEEDS_REVIEW, CatalogAlias, CatalogRecordMeta, VehicleEngine,
    VehicleGeneration, VehicleMake, VehicleModel,
)
from .regional import normalize_text


@dataclass(frozen=True)
class CatalogMatch:
    """Resultado parcial: no encontrar un modelo no impide enlazar la marca."""

    make_id: int | None = None
    model_id: int | None = None
    generation_id: int | None = None
    engine_id: int | None = None
    make_name: str | None = None
    model_name: str | None = None
    generation_name: str | None = None
    reason: str = "sin coincidencias"

    @property
    def linked(self) -> bool:
        return self.make_id is not None


CATALOG_FIELDS = {
    'catalog_make_id', 'catalog_model_id', 'catalog_generation_id', 'catalog_engine_id',
}


def _name_matches(db, entity, row, value):
    key = normalize_text(value)
    if key in {normalize_text(row.name), normalize_text(row.slug)}:
        return True
    return any(normalize_text(alias) == key for alias in db.scalars(
        select(CatalogAlias.alias).where(
            CatalogAlias.entity_type == entity, CatalogAlias.entity_id == row.id,
            CatalogAlias.verified.is_(True))))


def _candidates(db, entity, rows, value):
    pending = set(db.scalars(select(CatalogRecordMeta.entity_id).where(
        CatalogRecordMeta.entity_type == entity,
        CatalogRecordMeta.origin == ORIGIN_NEEDS_REVIEW)))
    key = normalize_text(value)
    alias_ids = set(db.scalars(select(CatalogAlias.entity_id).where(
        CatalogAlias.entity_type == entity, CatalogAlias.normalized == key,
        CatalogAlias.verified.is_(True))))
    return [row for row in rows if row.id not in pending and (
        key in {normalize_text(row.name), normalize_text(row.slug)} or row.id in alias_ids)]


def resolve_vehicle(db: Session, brand: str, model: str,
                    year: int | None = None) -> CatalogMatch:
    """Resuelve marca y modelo contra el catálogo, sin adivinar."""
    key_brand = normalize_text(brand)
    key_model = normalize_text(model)
    if not key_brand:
        return CatalogMatch(reason='el vehículo no tiene marca escrita')

    makes = db.scalars(
        select(VehicleMake).where(VehicleMake.name != '')
    ).all()
    candidates = _candidates(db, 'make', makes, brand)
    if not candidates:
        return CatalogMatch(reason=f'la marca «{brand}» no está en el catálogo')
    if len(candidates) > 1:
        return CatalogMatch(
            reason=f'la marca «{brand}» coincide con {len(candidates)} fichas')

    make = candidates[0]
    if not key_model:
        return CatalogMatch(
            make_id=make.id, make_name=make.name,
            reason='marca enlazada; el modelo no se pudo resolver')

    models = db.scalars(
        select(VehicleModel).where(VehicleModel.make_id == make.id)
    ).all()
    matching = _candidates(db, 'model', models, model)
    if not matching:
        return CatalogMatch(
            make_id=make.id, make_name=make.name,
            reason=f'el modelo «{model}» no está en el catálogo de {make.name}')
    if len(matching) > 1:
        return CatalogMatch(
            make_id=make.id, make_name=make.name,
            reason=f'el modelo «{model}» coincide con {len(matching)} fichas')

    vehicle_model = matching[0]
    base = CatalogMatch(make_id=make.id, make_name=make.name,
                        model_id=vehicle_model.id, model_name=vehicle_model.name)

    if year is not None and not _covers_year(vehicle_model, year):
        return CatalogMatch(
            make_id=make.id, make_name=make.name,
            reason=f'{year} está fuera del rango documentado de «{vehicle_model.name}»',
        )

    generation = _best_generation(db, vehicle_model, year)
    if generation is None:
        return CatalogMatch(
            make_id=base.make_id, make_name=base.make_name,
            model_id=base.model_id, model_name=base.model_name,
            reason='marca y modelo enlazados; sin generación determinable')
    return CatalogMatch(
        make_id=base.make_id, make_name=base.make_name,
        model_id=base.model_id, model_name=base.model_name,
        generation_id=generation.id, generation_name=generation.name,
        reason='marca, modelo y generación enlazados')


def _covers_year(model: VehicleModel, year: int) -> bool:
    """El rango del catálogo cubre el año, si el catálogo declara rango."""
    inicio = model.year_start
    fin = model.year_end
    if inicio is None and fin is None:
        return True
    if inicio is not None and year < inicio:
        return False
    if fin is not None and year > fin:
        return False
    return True


def _best_generation(db: Session, model: VehicleModel,
                     year: int | None) -> VehicleGeneration | None:
    """Generación del modelo, solo si se puede elegir sin ambigüedad.

    Incluso con una sola generación hay que comprobar las fechas. Si faltan
    fechas o varias generaciones cubren el año, no se elige ninguna.
    """
    generations = db.scalars(
        select(VehicleGeneration).where(VehicleGeneration.model_id == model.id)
    ).all()
    if not generations or year is None:
        return None
    # Una generación sin fechas también podría corresponder al vehículo: no
    # se descarta silenciosamente para forzar que quede una sola candidata.
    if any(g.year_start is None and g.year_end is None for g in generations):
        return None
    pending = set(db.scalars(select(CatalogRecordMeta.entity_id).where(
        CatalogRecordMeta.entity_type == 'generation',
        CatalogRecordMeta.origin == ORIGIN_NEEDS_REVIEW)))
    compatible = [g for g in generations if _covers_generation(g, year)]
    if len(compatible) == 1:
        return compatible[0] if compatible[0].id not in pending else None
    return None


def _covers_generation(generation: VehicleGeneration, year: int) -> bool:
    inicio = generation.year_start
    fin = generation.year_end
    if inicio is None and fin is None:
        return False
    if inicio is not None and year < inicio:
        return False
    if fin is not None and year > fin:
        return False
    return True


def explicit_match(db, data) -> CatalogMatch:
    """Valida la cadena seleccionada sin aceptar IDs de otras ramas."""
    def get(model, record_id, label):
        row = db.get(model, record_id) if record_id is not None else None
        if record_id is not None and row is None:
            raise HTTPException(422, f'{label} del catálogo no encontrado')
        return row

    engine = get(VehicleEngine, data.catalog_engine_id, 'Motor')
    generation = get(VehicleGeneration, data.catalog_generation_id, 'Generación')
    model = get(VehicleModel, data.catalog_model_id, 'Modelo')
    make = get(VehicleMake, data.catalog_make_id, 'Marca')
    if engine is not None:
        if generation is not None and generation.id != engine.generation_id:
            raise HTTPException(422, 'El motor no pertenece a la generación seleccionada')
        generation = generation or db.get(VehicleGeneration, engine.generation_id)
    if generation is not None:
        if model is not None and model.id != generation.model_id:
            raise HTTPException(422, 'La generación no pertenece al modelo seleccionado')
        model = model or db.get(VehicleModel, generation.model_id)
    if model is not None:
        if make is not None and make.id != model.make_id:
            raise HTTPException(422, 'El modelo no pertenece a la marca seleccionada')
        make = make or db.get(VehicleMake, model.make_id)
        if not _covers_year(model, data.year):
            raise HTTPException(422, 'El año está fuera del rango documentado del modelo')
        if not _name_matches(db, 'model', model, data.model):
            raise HTTPException(422, 'El modelo escrito no coincide con la ficha seleccionada')
    if make is not None and not _name_matches(db, 'make', make, data.brand):
        raise HTTPException(422, 'La marca escrita no coincide con la ficha seleccionada')
    if generation is not None and not _covers_year(generation, data.year):
        raise HTTPException(422, 'El año está fuera del rango documentado de la generación')
    for entity, row in (('make', make), ('model', model), ('generation', generation), ('engine', engine)):
        meta = db.get(CatalogRecordMeta, (entity, row.id)) if row is not None else None
        if meta is not None and meta.origin == ORIGIN_NEEDS_REVIEW:
            raise HTTPException(409, 'La ficha seleccionada está pendiente de revisión; verifíquela antes de vincularla')
    return CatalogMatch(
        make_id=make.id if make else None, model_id=model.id if model else None,
        generation_id=generation.id if generation else None,
        engine_id=engine.id if engine else None, reason='selección explícita')


def apply_catalog_match(db, vehicle, match):
    # Asignar solo las FK deja relaciones ya cargadas con datos viejos en la
    # respuesta del PUT. Se actualizan ambas representaciones en la sesión.
    for name, model, value in (
        ('make', VehicleMake, match.make_id), ('model', VehicleModel, match.model_id),
        ('generation', VehicleGeneration, match.generation_id),
        ('engine', VehicleEngine, match.engine_id),
    ):
        setattr(vehicle, f'catalog_{name}_id', value)
        setattr(vehicle, f'catalog_{name}', db.get(model, value) if value is not None else None)
