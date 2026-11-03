from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from . import schemas
from .access_policy import accessible_order, audit, scoped_record
from .dependencies import Database, admin, authenticated, invalidate
from .models import AuditEvent, InboxEvent, User, WorkAssignment, utcnow

router = APIRouter(tags=["Asignaciones y trazabilidad"])


def assignment_json(db, row):
    return {"id": row.id, "mechanic_id": row.mechanic_id, "mechanic_name": db.get(User, row.mechanic_id).username,
        "task_ids": row.task_ids, "can_quote": row.can_quote, "revision": row.revision,
        "created_at": row.created_at.isoformat(), "revoked_at": row.revoked_at.isoformat() if row.revoked_at else None}


@router.get("/staff/mechanics")
def mechanics(db: Database, user: User = Depends(admin)):
    return [{"id": row.id, "username": row.username} for row in db.scalars(select(User).where(
        User.workshop_id == user.workshop_id, User.role == "mechanic", User.active.is_(True)).order_by(User.username))]


@router.get("/orders/{order_id}/assignments")
def assignments(order_id: int, db: Database, user: User = Depends(authenticated)):
    accessible_order(db, order_id, user)
    if user.role == "customer":
        raise HTTPException(403, "Asignaciones internas del taller")
    query = select(WorkAssignment).where(WorkAssignment.order_id == order_id)
    if user.role == "mechanic":
        query = query.where(WorkAssignment.mechanic_id == user.id, WorkAssignment.revoked_at.is_(None))
    return [assignment_json(db, row) for row in db.scalars(query.order_by(WorkAssignment.id.desc()))]


def validate_assignment(db, order, data, user):
    mechanic = scoped_record(db, User, data.mechanic_id, user)
    if mechanic.role != "mechanic" or not mechanic.active:
        raise HTTPException(422, "Seleccione un mecánico activo de su taller")
    if set(data.task_ids) - {item.id for item in order.items} or any(item <= 0 for item in data.task_ids):
        raise HTTPException(422, "Las tareas deben pertenecer a esta orden")
    return mechanic


@router.post("/orders/{order_id}/assignments", status_code=201)
def assign(order_id: int, data: schemas.AssignmentInput, db: Database, user: User = Depends(admin)):
    order = accessible_order(db, order_id, user, lock=True)
    if order.status in {"delivered", "cancelled"}:
        raise HTTPException(409, "La orden está cerrada")
    mechanic = validate_assignment(db, order, data, user)
    if db.scalar(select(WorkAssignment.id).where(WorkAssignment.order_id == order.id,
        WorkAssignment.mechanic_id == mechanic.id, WorkAssignment.revoked_at.is_(None))):
        raise HTTPException(409, "El mecánico ya tiene una asignación activa; edítela")
    row = WorkAssignment(order_id=order.id, mechanic_id=mechanic.id, task_ids=sorted(set(data.task_ids)),
        can_quote=data.can_quote, assigned_by=user.id)
    db.add(row)
    db.flush()
    audit(db, user, "assignment.created", "order", order.id, {"assignment_id": row.id, "task_ids": row.task_ids, "mechanic_id": row.mechanic_id})
    db.add(InboxEvent(user_id=mechanic.id, title="Nueva asignación", body=f"Orden #{order.id}: {len(row.task_ids)} tareas asignadas.", order_id=order.id))
    invalidate(db, audience={mechanic.id}, order_id=order.id)
    return assignment_json(db, row)


@router.put("/orders/{order_id}/assignments/{assignment_id}")
def edit_assignment(order_id: int, assignment_id: int, data: schemas.AssignmentInput, db: Database, user: User = Depends(admin)):
    order = accessible_order(db, order_id, user, lock=True)
    from .order_routes import editable
    editable(order)
    row = db.get(WorkAssignment, assignment_id)
    if row is None or row.order_id != order.id or row.revoked_at:
        raise HTTPException(404, "Asignación no encontrada")
    if row.revision != data.expected_revision:
        raise HTTPException(409, "La asignación cambió; recargue")
    if row.mechanic_id != data.mechanic_id:
        raise HTTPException(422, "Revoque la asignación antes de cambiar de mecánico")
    validate_assignment(db, order, data, user)
    before = {"task_ids": row.task_ids, "can_quote": row.can_quote}
    row.task_ids, row.can_quote = sorted(set(data.task_ids)), data.can_quote
    row.revision += 1
    audit(db, user, "assignment.updated", "order", order.id, {"assignment_id": row.id, "before": before, "task_ids": row.task_ids})
    invalidate(db, audience={row.mechanic_id}, order_id=order.id)
    return assignment_json(db, row)


@router.delete("/orders/{order_id}/assignments/{assignment_id}")
def revoke(order_id: int, assignment_id: int, db: Database, user: User = Depends(admin)):
    order = accessible_order(db, order_id, user, lock=True)
    from .order_routes import editable
    editable(order)
    row = db.get(WorkAssignment, assignment_id)
    if row is None or row.order_id != order.id:
        raise HTTPException(404, "Asignación no encontrada")
    if row.revoked_at is None:
        row.revoked_at, row.revoked_by = utcnow(), user.id
        row.revision += 1
        audit(db, user, "assignment.revoked", "order", order.id, {"assignment_id": row.id, "mechanic_id": row.mechanic_id})
        invalidate(db, audience={row.mechanic_id}, order_id=order.id)
    return {"revoked": True}


@router.get("/orders/{order_id}/audit")
def order_audit(order_id: int, db: Database, user: User = Depends(admin)):
    accessible_order(db, order_id, user)
    return [{"id": row.id, "action": row.action, "actor": db.get(User, row.actor_id).username,
        "created_at": row.created_at.isoformat(), "payload": row.payload} for row in db.scalars(select(AuditEvent).where(
        AuditEvent.workshop_id == user.workshop_id, AuditEvent.resource_type == "order", AuditEvent.resource_id == order_id).order_by(AuditEvent.id.desc()).limit(300))]
