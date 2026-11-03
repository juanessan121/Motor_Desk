from copy import deepcopy

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import and_, false, select, or_

from . import schemas
from .access_policy import accessible_order, accessible_vehicle, audit, order_query, require_task, task_ids
from .branding import effective_config, require_feature
from .dependencies import Database, admin, authenticated, device_id, invalidate, staff
from .models import Finding, Inspection, InspectionRevision, IntakePhoto, User, WorkAssignment, WorkOrder, utcnow
from .notifications import enqueue
from .serializers import order_json, vehicle_json
from .templates import validate_mapping, vehicle_template

router = APIRouter(tags=["Pasaporte e inspecciones"])


def inspection_query(db, user):
    query = select(Inspection).where(Inspection.order_id.in_(order_query(user).with_only_columns(WorkOrder.id)))
    if user.role == "customer":
        query = query.where(Inspection.published_at.is_not(None))
    elif user.role == "mechanic":
        grants = list(db.scalars(select(WorkAssignment).where(WorkAssignment.mechanic_id == user.id, WorkAssignment.revoked_at.is_(None))))
        conditions = [and_(Inspection.order_id == row.order_id, Inspection.task_id.in_(row.task_ids)) for row in grants]
        query = query.where(or_(*conditions) if conditions else false())
    return query


def get_inspection(db, inspection_id, user, *, write=False):
    # Siempre bloquear primero la orden: revocación, evidencia y checklist usan el mismo orden de bloqueo.
    identity = db.scalar(inspection_query(db, user).where(Inspection.id == inspection_id))
    if identity is None:
        raise HTTPException(404, "Inspección no encontrada")
    order = accessible_order(db, identity.order_id, user, lock=write)
    require_task(db, order, user, identity.task_id)
    row = db.scalar(inspection_query(db, user).where(Inspection.id == inspection_id).with_for_update() if write
        else inspection_query(db, user).where(Inspection.id == inspection_id))
    if row is None:
        raise HTTPException(404, "Inspección no encontrada")
    if write and user.role == "customer":
        raise HTTPException(403, "La inspección es de solo lectura")
    if write and user.role == "mechanic" and order.status in {"delivered", "cancelled"}:
        raise HTTPException(409, "La orden está cerrada")
    return row


def check_revision(row, expected):
    if row.revision != expected:
        raise HTTPException(409, "La inspección cambió. Recargue antes de guardar")


def snapshot(db, row):
    photos = list(db.scalars(select(IntakePhoto).where(IntakePhoto.inspection_id == row.id).order_by(IntakePhoto.id)))
    return {
        "id": row.id, "order_id": row.order_id, "vehicle_id": row.vehicle_id, "task_id": row.task_id,
        "title": row.title, "template_id": row.template_id, "revision": row.revision,
        "review_status": row.review_status, "created_at": row.created_at.isoformat(),
        "author": db.get(User, row.created_by).username,
        "reviewed_at": row.reviewed_at.isoformat() if row.reviewed_at else None,
        "photos": [{"id": photo.id, "caption": photo.caption, "published": photo.published_at is not None} for photo in photos],
        "findings": [{"id": item.id, "component_id": item.component_id, "view_id": item.view_id,
            "x": float(item.x) if item.x is not None else None, "y": float(item.y) if item.y is not None else None, "polygon": item.polygon, "category": item.category,
            "severity": item.severity, "condition": item.condition, "note": item.note,
            "created_at": item.created_at.isoformat(), "updated_at": item.updated_at.isoformat(),
            "photo_ids": [photo.id for photo in photos if photo.finding_id == item.id],
        } for item in row.findings if item.active],
    }


def record_revision(db, row, user):
    db.flush()
    db.add(InspectionRevision(inspection_id=row.id, version=row.revision, actor_id=user.id, snapshot=snapshot(db, row)))


def touch_inspection(db, row, user):
    row.revision += 1
    row.review_status, row.reviewed_at, row.reviewed_by = "draft", None, None
    record_revision(db, row, user)


def inspection_json(db, row, user, *, device=None):
    customer = user.role == "customer"
    data = deepcopy(row.published_snapshot) if customer else snapshot(db, row)
    if data is None:
        raise HTTPException(404, "No hay informe publicado")
    data["published_revision"] = row.published_revision
    data["published_at"] = row.published_at.isoformat() if row.published_at else None
    data["can_edit"] = not customer
    data["can_publish"] = user.role == "admin"
    if customer:
        flags = effective_config(db, user.id, device)["features"]
        public_ids = set(db.scalars(select(IntakePhoto.id).where(IntakePhoto.inspection_id == row.id, IntakePhoto.published_at.is_not(None)))) if flags["photos"] else set()
        data["photos"] = [photo for photo in data.get("photos", []) if photo["id"] in public_ids]
        for finding in data["findings"]:
            finding["photo_ids"] = [pid for pid in finding.get("photo_ids", []) if pid in public_ids]
        data["author"] = "Equipo del taller"
        if not flags["maintenance"]:
            data["order_id"], data["task_id"] = None, None
    return data


def notify_inspection(db, row, user, action):
    order = db.get(WorkOrder, row.order_id)
    audit(db, user, action, "order", row.order_id, {"inspection_id": row.id, "revision": row.revision})
    invalidate(db, audience={order.customer.user_id}, order_id=row.order_id)


@router.get("/orders/{order_id}/inspections")
def inspections_for_order(order_id: int, db: Database, user: User = Depends(authenticated), device: int | None = Depends(device_id)):
    require_feature(db, user, "history", device)
    accessible_order(db, order_id, user)
    return [inspection_json(db, row, user, device=device) for row in db.scalars(inspection_query(db, user).where(Inspection.order_id == order_id).order_by(Inspection.id.desc()))]


@router.post("/inspections", status_code=201)
def create_inspection(data: schemas.InspectionInput, db: Database, user: User = Depends(staff)):
    order = accessible_order(db, data.order_id, user, lock=True)
    if order.status in {"delivered", "cancelled"}:
        raise HTTPException(409, "Abra una orden activa para registrar una nueva inspección")
    require_task(db, order, user, data.task_id)
    row = Inspection(order_id=order.id, vehicle_id=order.vehicle_id, task_id=data.task_id,
        template_id=order.vehicle.template_id, title=data.title, created_by=user.id)
    db.add(row)
    db.flush()
    record_revision(db, row, user)
    notify_inspection(db, row, user, "inspection.created")
    return inspection_json(db, row, user)


@router.get("/inspections/{inspection_id}")
def inspection_detail(inspection_id: int, db: Database, user: User = Depends(authenticated), device: int | None = Depends(device_id)):
    require_feature(db, user, "history", device)
    return inspection_json(db, get_inspection(db, inspection_id, user), user, device=device)


@router.post("/inspections/{inspection_id}/findings", status_code=201)
def add_finding(inspection_id: int, data: schemas.FindingInput, db: Database, user: User = Depends(staff)):
    row = get_inspection(db, inspection_id, user, write=True)
    check_revision(row, data.expected_revision)
    validate_mapping(row.template_id, data.component_id, data.view_id)
    finding = Finding(**data.model_dump(exclude={"expected_revision"}), created_by=user.id)
    row.findings.append(finding)
    db.flush()
    touch_inspection(db, row, user)
    notify_inspection(db, row, user, "finding.created")
    return inspection_json(db, row, user)


@router.put("/inspections/{inspection_id}/findings/{finding_id}")
def edit_finding(inspection_id: int, finding_id: int, data: schemas.FindingInput, db: Database, user: User = Depends(staff)):
    row = get_inspection(db, inspection_id, user, write=True)
    check_revision(row, data.expected_revision)
    finding = next((item for item in row.findings if item.id == finding_id and item.active), None)
    if finding is None:
        raise HTTPException(404, "Hallazgo no encontrado")
    validate_mapping(row.template_id, data.component_id, data.view_id)
    for key, value in data.model_dump(exclude={"expected_revision"}).items():
        setattr(finding, key, value)
    finding.updated_at = utcnow()
    touch_inspection(db, row, user)
    notify_inspection(db, row, user, "finding.updated")
    return inspection_json(db, row, user)


@router.delete("/inspections/{inspection_id}/findings/{finding_id}")
def remove_finding(inspection_id: int, finding_id: int, data: schemas.RevisionInput, db: Database, user: User = Depends(staff)):
    row = get_inspection(db, inspection_id, user, write=True)
    check_revision(row, data.expected_revision)
    finding = next((item for item in row.findings if item.id == finding_id and item.active), None)
    if finding is None:
        raise HTTPException(404, "Hallazgo no encontrado")
    finding.active = False
    finding.updated_at = utcnow()
    touch_inspection(db, row, user)
    notify_inspection(db, row, user, "finding.archived")
    return inspection_json(db, row, user)


@router.post("/inspections/{inspection_id}/review")
def review(inspection_id: int, data: schemas.RevisionInput, db: Database, user: User = Depends(admin)):
    row = get_inspection(db, inspection_id, user, write=True)
    check_revision(row, data.expected_revision)
    if not any(item.active for item in row.findings):
        raise HTTPException(409, "Registre al menos una observación documentada")
    row.revision += 1
    row.review_status, row.reviewed_at, row.reviewed_by = "reviewed", utcnow(), user.id
    record_revision(db, row, user)
    notify_inspection(db, row, user, "inspection.reviewed")
    return inspection_json(db, row, user)


@router.post("/inspections/{inspection_id}/publish")
def publish(inspection_id: int, data: schemas.PublishInspection, db: Database, user: User = Depends(admin)):
    row = get_inspection(db, inspection_id, user, write=True)
    check_revision(row, data.expected_revision)
    if row.review_status != "reviewed":
        raise HTTPException(409, "Revise el informe antes de publicarlo")
    photos = list(db.scalars(select(IntakePhoto).where(IntakePhoto.inspection_id == row.id)))
    if set(data.photo_ids) - {photo.id for photo in photos}:
        raise HTTPException(422, "Una fotografía no pertenece a esta inspección")
    for photo in photos:
        if photo.id in data.photo_ids:
            photo.published_at, photo.published_by = utcnow(), user.id
    row.revision += 1
    db.flush()
    public = snapshot(db, row)
    public["photos"] = [photo for photo in public["photos"] if photo["id"] in data.photo_ids]
    for finding in public["findings"]:
        finding["photo_ids"] = [pid for pid in finding["photo_ids"] if pid in data.photo_ids]
    row.published_snapshot = public
    row.published_revision, row.published_at, row.published_by = row.revision, utcnow(), user.id
    order = db.get(WorkOrder, row.order_id)
    enqueue(db, order.customer, 'inspection_published', 'Informe publicado por el taller',
            'Hay una inspección publicada disponible para consultar en tu expediente.',
            order.id, inspection_id=row.id)
    record_revision(db, row, user)
    notify_inspection(db, row, user, "inspection.published")
    return inspection_json(db, row, user)


@router.post("/inspections/{inspection_id}/withdraw")
def withdraw(inspection_id: int, data: schemas.RevisionInput, db: Database, user: User = Depends(admin)):
    row = get_inspection(db, inspection_id, user, write=True)
    check_revision(row, data.expected_revision)
    row.published_snapshot, row.published_revision, row.published_at, row.published_by = None, None, None, None
    row.revision += 1
    for photo in db.scalars(select(IntakePhoto).where(IntakePhoto.inspection_id == row.id)):
        photo.published_at, photo.published_by = None, None
    record_revision(db, row, user)
    notify_inspection(db, row, user, "inspection.withdrawn")
    return inspection_json(db, row, user)


@router.get('/inspections/{inspection_id}/photos/{photo_id}')
def inspection_photo(inspection_id: int, photo_id: int, db: Database,
                      user: User = Depends(authenticated), device: int | None = Depends(device_id)):
    require_feature(db, user, 'history', device)
    require_feature(db, user, 'photos', device)
    row = get_inspection(db, inspection_id, user)
    photo = db.get(IntakePhoto, photo_id)
    if photo is None or photo.inspection_id != row.id:
        raise HTTPException(404, 'Fotografía no encontrada')
    if user.role == 'customer':
        public_ids = {item['id'] for item in (row.published_snapshot or {}).get('photos', [])}
        if photo.published_at is None or photo.id not in public_ids:
            raise HTTPException(404, 'Fotografía no publicada en este informe')
    return Response(photo.content, media_type='image/jpeg', headers={'Cache-Control': 'private, no-store'})


@router.get("/inspections/{inspection_id}/revisions")
def revisions(inspection_id: int, db: Database, user: User = Depends(admin)):
    get_inspection(db, inspection_id, user)
    return [{"version": row.version, "created_at": row.created_at.isoformat(),
        "actor": db.get(User, row.actor_id).username, "snapshot": row.snapshot} for row in db.scalars(
            select(InspectionRevision).where(InspectionRevision.inspection_id == inspection_id).order_by(InspectionRevision.version.desc()))]


@router.get("/vehicles/{vehicle_id}/passport")
def passport(vehicle_id: int, db: Database, user: User = Depends(authenticated), device: int | None = Depends(device_id)):
    require_feature(db, user, "vehicles", device)
    vehicle = accessible_vehicle(db, vehicle_id, user)
    flags = effective_config(db, user.id, device)["features"] if user.role == "customer" else {"history": True, "maintenance": True, "photos": True, "quotes": True}
    records = list(db.scalars(inspection_query(db, user).where(Inspection.vehicle_id == vehicle.id).order_by(Inspection.id))) if flags["history"] else []
    inspections = [inspection_json(db, row, user, device=device) for row in records]
    states = {item["id"]: {"condition": "no_data", "date": None, "inspection_id": None} for item in vehicle_template(vehicle.template_id)["components"]}
    for row, data in zip(records, inspections):
        if user.role != "customer" and row.review_status != "reviewed":
            continue
        for finding in data["findings"]:
            previous = states[finding["component_id"]]
            date = data.get("reviewed_at") or data["created_at"]
            if previous["date"] is None or date >= previous["date"]:
                states[finding["component_id"]] = {"condition": finding["condition"], "date": date, "inspection_id": row.id}
    orders = list(db.scalars(order_query(user).where(WorkOrder.vehicle_id == vehicle.id).order_by(WorkOrder.id.desc()))) if flags["maintenance"] else []
    history_query = select(WorkOrder).where(WorkOrder.workshop_id == user.workshop_id, WorkOrder.vehicle_id == vehicle.id)
    if user.role == "mechanic":
        history_query = order_query(user).where(WorkOrder.vehicle_id == vehicle.id)
    history = [{"id": row.id if user.role != "customer" or row.customer.user_id == user.id else None,
        "title": row.title, "date": row.created_at.isoformat(), "status": row.status,
        "tasks": [item.label for item in row.items if item.completed and (user.role != "mechanic" or item.id in task_ids(db, row, user))]}
        for row in db.scalars(history_query.order_by(WorkOrder.id.desc()))] if flags["history"] else []
    return {"vehicle": vehicle_json(vehicle, user=user), "template_id": vehicle.template_id,
        "component_states": states, "inspections": inspections[::-1], "history": history,
        "orders": [order_json(order, db=db, user=user, show_quotes=flags["quotes"], show_photos=flags["photos"]) for order in orders]}
