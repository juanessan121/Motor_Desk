"""Solicitudes de repuestos e inventario físico mínimo, sin precios inferidos."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select

from . import schemas
from .access_policy import accessible_order, audit, require_task
from .catalog_browse_routes import visible
from .catalog_models import VehiclePart
from .dependencies import Database, admin, invalidate, staff
from .maintenance_service import touch_order, update_ready
from .models import PartRequest, StockItem, StockMovement, User, Workshop, WorkOrder, utcnow
from .order_routes import editable

router = APIRouter(tags=['Solicitudes y existencias físicas'])


def request_json(row):
    return {key: (str(getattr(row, key)) if key == 'quantity' else getattr(row, key)) for key in (
        'id', 'task_id', 'part_id', 'description', 'quantity', 'unit', 'reason', 'status',
        'quote_id', 'authorization_basis', 'resolution_note', 'created_by', 'revision')}


def known_part(db, part_id, user):
    row = db.scalar(select(VehiclePart).where(VehiclePart.id == part_id, visible('part', VehiclePart, user)))
    if not row:
        raise HTTPException(422, 'El repuesto no está disponible en el catálogo; regístrelo o seleccione otra ficha')
    return row


def current_request(db, order, request_id):
    row = db.get(PartRequest, request_id)
    if row is None or row.order_id != order.id:
        raise HTTPException(404, 'Solicitud no encontrada')
    return row


@router.get('/orders/{order_id}/part-requests')
def requests(order_id: int, db: Database, user: User = Depends(staff)):
    order = accessible_order(db, order_id, user)
    from .access_policy import task_ids
    allowed = task_ids(db, order, user)
    return [request_json(row) for row in order.part_requests if row.task_id in allowed]


@router.post('/orders/{order_id}/part-requests', status_code=201)
def request_part(order_id: int, data: schemas.PartRequestInput, db: Database, user: User = Depends(staff)):
    order = accessible_order(db, order_id, user, lock=True)
    require_task(db, order, user, data.task_id)
    existing = next((row for row in order.part_requests if row.request_key == str(data.request_key)), None)
    if existing:
        same = all(getattr(existing, key) == getattr(data, key) for key in ('task_id', 'part_id', 'description', 'quantity', 'unit', 'reason'))
        if not same:
            raise HTTPException(409, 'La clave de solicitud ya fue utilizada con otros datos')
        return request_json(existing)
    editable(order)
    if data.part_id:
        known_part(db, data.part_id, user)
    row = PartRequest(**data.model_dump(exclude={'request_key'}), request_key=str(data.request_key), created_by=user.id)
    order.part_requests.append(row)
    touch_order(order)
    db.flush()
    update_ready(db, order)
    audit(db, user, 'part.requested', 'order', order.id, {'request_id': row.id, 'task_id': row.task_id, 'quantity': str(row.quantity)})
    invalidate(db, order_id=order.id)
    return request_json(row)


@router.post('/orders/{order_id}/part-requests/{request_id}/resolution')
def resolve(order_id: int, request_id: int, data: schemas.PartResolutionInput, db: Database, user: User = Depends(admin)):
    order = accessible_order(db, order_id, user, lock=True)
    editable(order)
    row = current_request(db, order, request_id)
    if row.revision != data.expected_revision or row.status != 'requested':
        raise HTTPException(409, 'La solicitud ya cambió o fue resuelta')
    if data.decision == 'approve':
        if order.base_approval != 'approved':
            raise HTTPException(409, 'El cliente aún no acepta el servicio base')
        if data.authorization_basis == 'approved_quote':
            quote = next((quote for quote in order.quotes if quote.id == data.quote_id), None)
            if quote is None or quote.decision != 'approved' or quote.task_id not in (None, row.task_id):
                raise HTTPException(409, 'Se necesita una cotización de esta tarea aprobada por el cliente')
            row.quote_id = quote.id
        elif data.authorization_basis != 'included_base' or data.quote_id is not None:
            raise HTTPException(422, 'Indique si está incluido en el servicio aceptado o en un adicional autorizado')
        part_id = data.part_id or row.part_id
        if not part_id:
            raise HTTPException(422, 'Vincule un repuesto real antes de aprobar la entrega de inventario')
        known_part(db, part_id, user)
        row.part_id, row.authorization_basis, row.status = part_id, data.authorization_basis, 'approved'
    else:
        row.status = 'rejected'
    row.resolution_note = data.note
    row.resolved_at, row.resolved_by = utcnow(), user.id
    row.revision += 1
    touch_order(order)
    update_ready(db, order)
    audit(db, user, 'part.' + row.status, 'order', order.id, {'request_id': row.id, 'note': data.note, 'authorization_basis': row.authorization_basis})
    invalidate(db, order_id=order.id)
    return request_json(row)


@router.post('/orders/{order_id}/part-requests/{request_id}/issue')
def issue(order_id: int, request_id: int, data: schemas.RevisionInput, db: Database, user: User = Depends(admin)):
    order = accessible_order(db, order_id, user, lock=True)
    row = current_request(db, order, request_id)
    if row.status == 'issued':
        return request_json(row)  # Reintentar no vuelve a descontar.
    editable(order)
    if row.status != 'approved' or row.revision != data.expected_revision:
        raise HTTPException(409, 'La solicitud no está aprobada o cambió')
    if order.base_approval != 'approved':
        raise HTTPException(409, 'Falta aceptación del servicio')
    if row.authorization_basis == 'approved_quote' and not any(q.id == row.quote_id and q.decision == 'approved' for q in order.quotes):
        raise HTTPException(409, 'El costo adicional no está autorizado')
    stock = db.scalar(select(StockItem).where(StockItem.workshop_id == user.workshop_id, StockItem.part_id == row.part_id).with_for_update())
    if stock is None or stock.quantity < row.quantity:
        raise HTTPException(409, 'Existencias insuficientes; registre una entrada real antes de entregar')
    if stock.unit != row.unit:
        raise HTTPException(422, 'La unidad solicitada no coincide con la existencia física; no se convierten unidades automáticamente')
    stock.quantity -= row.quantity
    db.add(StockMovement(workshop_id=user.workshop_id, stock_item_id=stock.id, part_request_id=row.id,
        delta=-row.quantity, request_key=row.request_key, reason=row.reason, actor_id=user.id))
    row.status, row.revision = 'issued', row.revision + 1
    touch_order(order)
    update_ready(db, order)
    audit(db, user, 'part.issued', 'order', order.id, {'request_id': row.id, 'part_id': row.part_id, 'quantity': str(row.quantity)})
    invalidate(db, order_id=order.id)
    return request_json(row)


@router.get('/stock')
def stock(db: Database, user: User = Depends(admin), limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
    return [{'id': row.id, 'part_id': row.part_id, 'sku': part.sku, 'name': part.title, 'quantity': str(row.quantity), 'unit': row.unit}
            for row, part in db.execute(select(StockItem, VehiclePart).join(VehiclePart, VehiclePart.id == StockItem.part_id).where(
                StockItem.workshop_id == user.workshop_id).order_by(StockItem.id).offset(offset).limit(limit))]


@router.post('/stock/receipts', status_code=201)
def receipt(data: schemas.StockReceiptInput, db: Database, user: User = Depends(admin)):
    # Serializa la creación inicial de un saldo y los reintentos de entradas.
    db.scalar(select(Workshop).where(Workshop.id == user.workshop_id).with_for_update())
    existing = db.scalar(select(StockMovement).where(StockMovement.workshop_id == user.workshop_id, StockMovement.request_key == str(data.request_key)))
    if existing:
        previous = db.get(StockItem, existing.stock_item_id)
        if existing.part_request_id or previous.part_id != data.part_id or existing.delta != data.quantity or existing.reason != data.reason or previous.unit != data.unit:
            raise HTTPException(409, 'La confirmación ya fue utilizada con otros datos')
        return {'movement_id': existing.id, 'quantity': str(previous.quantity), 'unit': previous.unit}
    known_part(db, data.part_id, user)
    row = db.scalar(select(StockItem).where(StockItem.workshop_id == user.workshop_id, StockItem.part_id == data.part_id).with_for_update())
    if row is None:
        row = StockItem(workshop_id=user.workshop_id, part_id=data.part_id, quantity=0, unit=data.unit)
        db.add(row)
        db.flush()
    if row.unit != data.unit:
        raise HTTPException(422, 'La unidad no coincide con las entradas previas')
    row.quantity += data.quantity
    movement = StockMovement(workshop_id=user.workshop_id, stock_item_id=row.id, delta=data.quantity,
        request_key=str(data.request_key), reason=data.reason, actor_id=user.id)
    db.add(movement)
    db.flush()
    audit(db, user, 'stock.received', 'stock', row.id, {'movement_id': movement.id, 'quantity': str(data.quantity), 'reason': data.reason})
    invalidate(db)
    return {'movement_id': movement.id, 'quantity': str(row.quantity), 'unit': row.unit}


@router.get('/stock/{stock_id}/movements')
def movements(stock_id: int, db: Database, user: User = Depends(admin), limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
    from .access_policy import scoped_record
    scoped_record(db, StockItem, stock_id, user)
    return [{'id': row.id, 'delta': str(row.delta), 'reason': row.reason, 'part_request_id': row.part_request_id,
             'created_at': row.created_at.isoformat(), 'actor_id': row.actor_id}
            for row in db.scalars(select(StockMovement).where(StockMovement.stock_item_id == stock_id).order_by(StockMovement.id.desc()).offset(offset).limit(limit))]
