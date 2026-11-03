from fastapi import HTTPException
from sqlalchemy import exists, select
from sqlalchemy.orm import selectinload

from .models import AuditEvent, Customer, IntakePhoto, User, Vehicle, WorkAssignment, WorkOrder


def order_load_options():
    """Carga por lotes para serializar listados; no descarga bytes de fotos."""
    from .models import ExtraQuote
    return (
        selectinload(WorkOrder.vehicle), selectinload(WorkOrder.items),
        selectinload(WorkOrder.quotes).selectinload(ExtraQuote.options),
        selectinload(WorkOrder.photos),
        selectinload(WorkOrder.assignments), selectinload(WorkOrder.part_requests),
    )


def order_query(user):
    query = select(WorkOrder).where(WorkOrder.workshop_id == user.workshop_id)
    if user.role == "customer":
        query = query.where(WorkOrder.customer_id.in_(select(Customer.id).where(Customer.user_id == user.id)))
    elif user.role == "mechanic":
        query = query.where(exists().where(WorkAssignment.order_id == WorkOrder.id,
            WorkAssignment.mechanic_id == user.id, WorkAssignment.revoked_at.is_(None)))
    elif user.role != "admin":
        raise HTTPException(403, "Rol no autorizado")
    return query


def vehicle_query(user):
    query = select(Vehicle).where(Vehicle.workshop_id == user.workshop_id)
    if user.role == "customer":
        query = query.where(Vehicle.owner_id.in_(select(Customer.id).where(Customer.user_id == user.id)))
    elif user.role == "mechanic":
        query = query.where(Vehicle.id.in_(order_query(user).with_only_columns(WorkOrder.vehicle_id)))
    return query


def accessible_order(db, order_id, user, *, lock=False):
    query = order_query(user).where(WorkOrder.id == order_id)
    if lock:
        query = query.with_for_update()
    row = db.scalar(query)
    if row is None:
        raise HTTPException(404, "Orden no encontrada")
    return row


def accessible_vehicle(db, vehicle_id, user, *, lock=False):
    query = vehicle_query(user).where(Vehicle.id == vehicle_id)
    if lock:
        query = query.with_for_update(of=Vehicle)
    row = db.scalar(query)
    if row is None:
        raise HTTPException(404, "Vehículo no encontrado")
    return row


def scoped_record(db, model, record_id, user, *, lock=False):
    query = select(model).where(model.id == record_id, model.workshop_id == user.workshop_id)
    if lock:
        query = query.with_for_update(of=model)
    row = db.scalar(query)
    if row is None:
        raise HTTPException(404, "Registro no encontrado")
    return row


def assignment(db, order_id, user):
    if user.role != "mechanic":
        return None
    return db.scalar(select(WorkAssignment).where(WorkAssignment.order_id == order_id,
        WorkAssignment.mechanic_id == user.id, WorkAssignment.revoked_at.is_(None)))


def task_ids(db, order, user):
    if user.role == "admin":
        return {item.id for item in order.items}
    row = assignment(db, order.id, user)
    return set(row.task_ids) if row else set()


def require_task(db, order, user, task_id):
    if task_id is not None and task_id not in {item.id for item in order.items}:
        raise HTTPException(422, "La tarea no pertenece a la orden")
    if user.role == "mechanic" and task_id not in task_ids(db, order, user):
        raise HTTPException(404, "Tarea no autorizada")


def photo_allowed(db, photo, order, user):
    if user.role == "admin":
        return True
    if user.role == "customer":
        return photo.published_at is not None
    return photo.task_id in task_ids(db, order, user)


def audit(db, user, action, resource_type, resource_id, payload=None):
    db.add(AuditEvent(workshop_id=user.workshop_id, actor_id=user.id, action=action,
        resource_type=resource_type, resource_id=resource_id, payload=payload or {}))


def admins(db, workshop_id):
    return set(db.scalars(select(User.id).where(User.workshop_id == workshop_id,
        User.role == "admin", User.active.is_(True))))
