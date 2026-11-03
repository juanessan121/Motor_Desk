from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from . import schemas
from .access_policy import accessible_order, audit, order_load_options, scoped_record
from .dependencies import Database, admin, staff, invalidate
from .models import BayOccupancy, ChecklistItem, Inspection, User, WorkAssignment, Workshop, WorkshopBay, WorkshopZone, WorkOrder, utcnow
from .maintenance_service import stage

router = APIRouter(tags=["Plano y ocupación real"])


def occupancy_query():
    return select(BayOccupancy).where(BayOccupancy.exited_at.is_(None))


def geometry_json(row):
    return {"id": row.id, "name": row.name, "kind": row.kind, "capacity": row.capacity,
        "x": float(row.x), "y": float(row.y), "width": float(row.width), "height": float(row.height),
        "revision": row.revision, "active": row.active}


def order_context(db, order_ids):
    context = {order_id: {'mechanics': [], 'attention_required': False} for order_id in order_ids}
    if not order_ids:
        return context
    for order_id in db.scalars(select(ChecklistItem.order_id).where(ChecklistItem.order_id.in_(order_ids), ChecklistItem.status == 'attention').distinct()):
        context[order_id]['attention_required'] = True
    for grant, mechanic in db.execute(select(WorkAssignment, User).join(User, User.id == WorkAssignment.mechanic_id).where(
        WorkAssignment.order_id.in_(order_ids), WorkAssignment.revoked_at.is_(None))):
        context[grant.order_id]['mechanics'].append({'id': mechanic.id, 'username': mechanic.username})
    # Solo observaciones revisadas, tomando la última por componente de orden.
    seen = set()
    reports = db.scalars(select(Inspection).options(selectinload(Inspection.findings)).where(
        Inspection.order_id.in_(order_ids), Inspection.review_status == 'reviewed'
    ).order_by(Inspection.reviewed_at.desc(), Inspection.id.desc()))
    for report in reports:
        for finding in report.findings:
            key = (report.order_id, finding.component_id)
            if finding.active and key not in seen:
                seen.add(key)
                if finding.condition == 'issue':
                    context[report.order_id]['attention_required'] = True
    return context


def occupancy_json(db, row, context=None):
    order = db.get(WorkOrder, row.order_id)
    bay = db.get(WorkshopBay, row.bay_id)
    context = context if context is not None else order_context(db, [order.id])
    return {"id": row.id, "order_id": row.order_id, "bay_id": row.bay_id, "bay_name": bay.name,
        "vehicle_id": order.vehicle_id, "plate": order.vehicle.plate, "status": order.status,
        'operational_stage': stage(order),
        "title": order.title, **context.get(order.id, {}),
        "entered_at": row.entered_at.isoformat(), "exited_at": row.exited_at.isoformat() if row.exited_at else None,
        "reason": row.reason, "actor": db.get(User, row.entered_by).username}


def layout_lock(db, user):
    return db.scalar(select(Workshop).where(Workshop.id == user.workshop_id).with_for_update())


def ensure_zone_bounds(zone, data):
    tolerance = .00000001
    if data.x < float(zone.x) - tolerance or data.y < float(zone.y) - tolerance or data.x + data.width > float(zone.x + zone.width) + tolerance or data.y + data.height > float(zone.y + zone.height) + tolerance:
        raise HTTPException(422, "La bahía debe estar dentro de la geometría de su zona")


@router.get("/workshop/layout")
def layout(db: Database, user: User = Depends(admin), include_inactive: bool = False):
    workshop = db.get(Workshop, user.workshop_id)
    zones = list(db.scalars(select(WorkshopZone).where(WorkshopZone.workshop_id == user.workshop_id, WorkshopZone.active.is_(True)).order_by(WorkshopZone.id)))
    bays_query = select(WorkshopBay).where(WorkshopBay.workshop_id == user.workshop_id)
    if not include_inactive:
        bays_query = bays_query.where(WorkshopBay.active.is_(True))
    bays = list(db.scalars(bays_query.order_by(WorkshopBay.id)))
    occupancies = list(db.scalars(occupancy_query().join(WorkshopBay).where(WorkshopBay.workshop_id == user.workshop_id)))
    orders = list(db.scalars(select(WorkOrder).options(*order_load_options()).where(
        WorkOrder.workshop_id == user.workshop_id, WorkOrder.status.in_(['in_progress', 'ready'])
    ).order_by(WorkOrder.id)))
    context = order_context(db, [order.id for order in orders])
    current = {entry.order_id: entry.id for entry in occupancies}

    return {"revision": workshop.layout_revision, "name": workshop.name, "configured": bool(zones and any(bay.active for bay in bays)),
        "is_mechanic": False,
        "zones": [geometry_json(zone) for zone in zones],
        "orders": [{'id': order.id, 'order_code': getattr(order, 'order_code', f"ORD-{order.id:04d}"),
                    'plate': order.vehicle.plate, 'vehicle_id': order.vehicle_id,
                    'vehicle_name': f'{order.vehicle.brand} {order.vehicle.model}',
                    'title': order.title, 'status': order.status,
                    'operational_stage': stage(order),
                    'is_assigned': True,
                    'occupancy_id': current.get(order.id), **context.get(order.id, {})} for order in orders],
        "bays": [{**geometry_json(bay), "zone_id": bay.zone_id,
            "occupancies": [{**occupancy_json(db, entry, context), 'is_assigned': True}
                           for entry in occupancies if entry.bay_id == bay.id]} for bay in bays]}


@router.get("/workshop/mechanic-view")
def mechanic_view(db: Database, user: User = Depends(staff)):
    workshop = db.get(Workshop, user.workshop_id)
    zones = list(db.scalars(select(WorkshopZone).where(WorkshopZone.workshop_id == user.workshop_id, WorkshopZone.active.is_(True)).order_by(WorkshopZone.id)))
    bays = list(db.scalars(select(WorkshopBay).where(WorkshopBay.workshop_id == user.workshop_id, WorkshopBay.active.is_(True)).order_by(WorkshopBay.id)))
    occupancies = list(db.scalars(occupancy_query().join(WorkshopBay).where(WorkshopBay.workshop_id == user.workshop_id)))
    orders_query = select(WorkOrder).options(*order_load_options()).where(
        WorkOrder.workshop_id == user.workshop_id, WorkOrder.status.in_(['in_progress', 'ready'])
    )
    assigned_order_ids = set()
    if user.role == 'mechanic':
        assigned_order_ids = set(db.scalars(
            select(WorkAssignment.order_id).where(
                WorkAssignment.mechanic_id == user.id,
                WorkAssignment.revoked_at.is_(None)
            )
        ))
        orders_query = orders_query.where(WorkOrder.id.in_(assigned_order_ids))
    orders = list(db.scalars(orders_query.order_by(WorkOrder.id)))
    context = order_context(db, [order.id for order in orders])
    current = {entry.order_id: entry.id for entry in occupancies}

    visible_occupancies = [entry for entry in occupancies if entry.order_id in assigned_order_ids] if user.role == 'mechanic' else occupancies

    return {"revision": workshop.layout_revision, "name": workshop.name, "configured": bool(zones and any(bay.active for bay in bays)),
        "is_mechanic": user.role == 'mechanic',
        "zones": [geometry_json(zone) for zone in zones],
        "orders": [{'id': order.id, 'order_code': getattr(order, 'order_code', f"ORD-{order.id:04d}"),
                    'plate': order.vehicle.plate, 'vehicle_id': order.vehicle_id,
                    'vehicle_name': f'{order.vehicle.brand} {order.vehicle.model}',
                    'title': order.title, 'status': order.status,
                    'operational_stage': stage(order),
                    'is_assigned': True,
                    'occupancy_id': current.get(order.id), **context.get(order.id, {})} for order in orders],
        "bays": [{**geometry_json(bay), "zone_id": bay.zone_id,
            "occupancies": [{**occupancy_json(db, entry, context), 'is_assigned': True}
                           for entry in visible_occupancies if entry.bay_id == bay.id]} for bay in bays]}


@router.post('/workshop/layout/init-default', status_code=201)
def init_default_layout(db: Database, user: User = Depends(admin)):
    workshop = layout_lock(db, user)
    existing_zones = db.scalar(select(WorkshopZone.id).where(WorkshopZone.workshop_id == user.workshop_id).limit(1))
    if not existing_zones:
        zone = WorkshopZone(workshop_id=user.workshop_id, name='Zona de servicio', kind='service',
                            capacity=6, x=.035, y=.05, width=.93, height=.9)
        db.add(zone)
        db.flush()
        for index, (x, y) in enumerate(( (x, y) for y in (90, 546) for x in (118, 525, 932) ), start=1):
            db.add(WorkshopBay(workshop_id=user.workshop_id, zone_id=zone.id,
                name=f'B{index:02d}', kind='mechanical', capacity=1,
                x=x / 1400, y=y / 900, width=350 / 1400, height=258 / 900))
        workshop.layout_revision += 1
        audit(db, user, 'layout.template_created', 'workshop', workshop.id, {'template': 'default_6_bay'})
        db.flush()
        invalidate(db)
    return layout(db, user, include_inactive=True)


@router.post('/workshop/layout/template', status_code=201)
def create_template(data: schemas.WorkshopTemplateInput, db: Database, user: User = Depends(admin)):
    workshop = layout_lock(db, user)
    if workshop.layout_revision != data.expected_revision:
        raise HTTPException(409, 'El plano cambió; actualice antes de configurar')
    if db.scalar(select(WorkshopZone.id).where(WorkshopZone.workshop_id == user.workshop_id).limit(1)) is not None or db.scalar(select(WorkshopBay.id).where(WorkshopBay.workshop_id == user.workshop_id).limit(1)) is not None:
        raise HTTPException(409, 'El taller ya tiene geometría; no se reemplazará con la plantilla')
    zone = WorkshopZone(workshop_id=user.workshop_id, name='Zona de servicio', kind='service',
                        capacity=6, x=.035, y=.05, width=.93, height=.9)
    db.add(zone)
    db.flush()
    for index, (x, y) in enumerate(( (x, y) for y in (90, 546) for x in (118, 525, 932) ), start=1):
        db.add(WorkshopBay(workshop_id=user.workshop_id, zone_id=zone.id,
            name=f'B{index:02d}', kind='mechanical', capacity=1,
            x=x / 1400, y=y / 900, width=350 / 1400, height=258 / 900))
    workshop.layout_revision += 1
    audit(db, user, 'layout.template_created', 'workshop', workshop.id, {'template': data.template})
    db.flush()
    invalidate(db)
    return layout(db, user, include_inactive=True)


@router.post("/workshop/zones", status_code=201)
def create_zone(data: schemas.GeometryInput, db: Database, user: User = Depends(admin)):
    workshop = layout_lock(db, user)
    row = WorkshopZone(workshop_id=user.workshop_id, **data.model_dump(exclude={"expected_revision"}))
    db.add(row)
    db.flush()
    workshop.layout_revision += 1
    audit(db, user, "zone.created", "zone", row.id)
    invalidate(db)
    return geometry_json(row)


@router.put("/workshop/zones/{zone_id}")
def edit_zone(zone_id: int, data: schemas.GeometryInput, db: Database, user: User = Depends(admin)):
    workshop = layout_lock(db, user)
    row = scoped_record(db, WorkshopZone, zone_id, user, lock=True)
    if row.revision != data.expected_revision:
        raise HTTPException(409, "La zona cambió; recargue")
    used = db.scalar(select(func.count(BayOccupancy.id)).join(WorkshopBay).where(BayOccupancy.exited_at.is_(None), WorkshopBay.zone_id == row.id))
    if used > data.capacity:
        raise HTTPException(409, "La capacidad es inferior a la ocupación actual")
    for bay in db.scalars(select(WorkshopBay).where(WorkshopBay.zone_id == row.id, WorkshopBay.active.is_(True))):
        if float(bay.x) < data.x or float(bay.y) < data.y or float(bay.x + bay.width) > data.x + data.width + 1e-8 or float(bay.y + bay.height) > data.y + data.height + 1e-8:
            raise HTTPException(409, "La geometría dejaría bahías fuera de la zona")
    for key, value in data.model_dump(exclude={"expected_revision"}).items():
        setattr(row, key, value)
    row.revision += 1
    workshop.layout_revision += 1
    audit(db, user, "zone.updated", "zone", row.id)
    invalidate(db)
    return geometry_json(row)


@router.post("/workshop/bays", status_code=201)
def create_bay(data: schemas.BayInput, db: Database, user: User = Depends(admin)):
    workshop = layout_lock(db, user)
    zone = scoped_record(db, WorkshopZone, data.zone_id, user, lock=True)
    if not zone.active:
        raise HTTPException(409, "Zona archivada")
    ensure_zone_bounds(zone, data)
    row = WorkshopBay(workshop_id=user.workshop_id, **data.model_dump(exclude={"expected_revision"}))
    db.add(row)
    db.flush()
    workshop.layout_revision += 1
    audit(db, user, "bay.created", "bay", row.id)
    invalidate(db)
    return {**geometry_json(row), "zone_id": row.zone_id}


@router.put("/workshop/bays/{bay_id}")
def edit_bay(bay_id: int, data: schemas.BayInput, db: Database, user: User = Depends(admin)):
    workshop = layout_lock(db, user)
    row = scoped_record(db, WorkshopBay, bay_id, user, lock=True)
    if row.revision != data.expected_revision:
        raise HTTPException(409, "La bahía cambió; recargue")
    zone = scoped_record(db, WorkshopZone, data.zone_id, user)
    if not zone.active:
        raise HTTPException(409, 'Zona archivada')
    ensure_zone_bounds(zone, data)
    used = db.scalar(select(func.count(BayOccupancy.id)).where(BayOccupancy.bay_id == row.id, BayOccupancy.exited_at.is_(None)))
    if used > data.capacity or (used and (data.zone_id != row.zone_id or not data.active)):
        raise HTTPException(409, "Libere la bahía antes de reducir capacidad o cambiar de zona")
    for key, value in data.model_dump(exclude={"expected_revision"}).items():
        setattr(row, key, value)
    row.revision += 1
    workshop.layout_revision += 1
    audit(db, user, "bay.updated", "bay", row.id)
    invalidate(db)
    return {**geometry_json(row), "zone_id": row.zone_id}


@router.delete("/workshop/bays/{bay_id}")
def archive_bay(bay_id: int, db: Database, user: User = Depends(admin)):
    workshop = layout_lock(db, user)
    row = scoped_record(db, WorkshopBay, bay_id, user, lock=True)
    if db.scalar(select(BayOccupancy.id).where(BayOccupancy.bay_id == row.id, BayOccupancy.exited_at.is_(None))):
        raise HTTPException(409, "La bahía está ocupada")
    row.active = False
    row.revision += 1
    workshop.layout_revision += 1
    audit(db, user, "bay.archived", "bay", row.id)
    invalidate(db)
    return {"archived": True}


def close_location(db, order, user, reason):
    layout_lock(db, user)
    current = db.scalar(occupancy_query().where(BayOccupancy.order_id == order.id).with_for_update())
    if current:
        current.exited_at, current.exited_by = utcnow(), user.id
        audit(db, user, "bay.released", "order", order.id, {"occupancy_id": current.id, "reason": reason})


@router.post("/orders/{order_id}/location")
def move(order_id: int, data: schemas.MoveInput, db: Database, user: User = Depends(admin)):
    order = accessible_order(db, order_id, user, lock=True)
    if order.status not in {"in_progress", "ready"}:
        raise HTTPException(409, "Solo se ubican órdenes activas")
    # Bloqueo del plano serializa cambios de capacidad, movimientos y cierre.
    layout_lock(db, user)
    current = db.scalar(occupancy_query().where(BayOccupancy.order_id == order.id).with_for_update())
    if (current.id if current else None) != data.expected_occupancy_id:
        raise HTTPException(409, "La ubicación cambió; recargue el plano")
    if current and current.bay_id == data.bay_id:
        raise HTTPException(409, "La orden ya está en esa bahía")
    if data.bay_id is not None:
        bay = scoped_record(db, WorkshopBay, data.bay_id, user, lock=True)
        zone = scoped_record(db, WorkshopZone, bay.zone_id, user, lock=True)
        if not bay.active or not zone.active:
            raise HTTPException(409, "Ubicación archivada")
        bay_count = db.scalar(select(func.count(BayOccupancy.id)).where(BayOccupancy.bay_id == bay.id, BayOccupancy.exited_at.is_(None)))
        zone_count = db.scalar(select(func.count(BayOccupancy.id)).join(WorkshopBay).where(WorkshopBay.zone_id == zone.id, BayOccupancy.exited_at.is_(None)))
        same_zone = current is not None and db.get(WorkshopBay, current.bay_id).zone_id == zone.id
        if bay_count >= bay.capacity or (zone_count - int(same_zone)) >= zone.capacity:
            raise HTTPException(409, "No hay capacidad disponible en la bahía o zona")
    if current:
        current.exited_at, current.exited_by = utcnow(), user.id
        db.flush()
    entry = None
    if data.bay_id is not None:
        entry = BayOccupancy(order_id=order.id, bay_id=data.bay_id, entered_by=user.id, reason=data.reason)
        db.add(entry)
        db.flush()
    audit(db, user, "bay.moved", "order", order.id, {"from_bay": current.bay_id if current else None, "to_bay": data.bay_id, "reason": data.reason})
    invalidate(db, order_id=order.id)
    return {"location": occupancy_json(db, entry) if entry else None, "order_status": order.status}


@router.get("/orders/{order_id}/locations")
def location_history(order_id: int, db: Database, user: User = Depends(admin)):
    accessible_order(db, order_id, user)
    return [occupancy_json(db, row) for row in db.scalars(select(BayOccupancy).where(BayOccupancy.order_id == order_id).order_by(BayOccupancy.id.desc()))]
