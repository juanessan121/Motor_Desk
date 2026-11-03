import secrets

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from . import schemas
from .access_policy import accessible_vehicle, audit, order_query, vehicle_query
from .branding import require_feature
from .catalog_link import CATALOG_FIELDS, apply_catalog_match, explicit_match, resolve_vehicle
from .dependencies import Database, admin, authenticated, device_id, invalidate, staff
from .models import CatalogTask, Customer, MaintenanceCatalog, MaintenanceVersion, Notification, OwnershipHistory, User, Vehicle, WorkOrder, utcnow
from .maintenance_service import apply_catalog, applicability, save_version, seed_templates, snapshot
from .notifications import enqueue
from .security import password_hasher
from .serializers import catalog_json, customer_json, vehicle_json

router = APIRouter(tags=["Clientes, vehículos y catálogo"])


def get_record(db, model, record_id):
    query = select(model).where(model.id == record_id)
    if model is Notification:
        from .notifications import workshop_condition
        query = query.where(workshop_condition(db.info.get("workshop_id", 1)))
    if hasattr(model, "workshop_id"):
        query = query.where(model.workshop_id == db.info.get("workshop_id", 1))
    record = db.scalar(query)
    if record is None:
        raise HTTPException(404, "Registro no encontrado")
    return record


def active_customer(db, customer_id):
    customer = locked_record(db, Customer, customer_id)
    if not customer.active:
        raise HTTPException(409, "El cliente está desactivado")
    return customer


def locked_record(db, model, record_id):
    query = select(model).where(model.id == record_id)
    if model is Notification:
        from .notifications import workshop_condition
        query = query.where(workshop_condition(db.info.get("workshop_id", 1)))
    if hasattr(model, "workshop_id"):
        query = query.where(model.workshop_id == db.info.get("workshop_id", 1))
    # Vehicle incluye LEFT JOIN a las referencias opcionales del catálogo.
    # PostgreSQL debe bloquear solo la fila principal, no el lado nullable.
    record = db.scalar(query.with_for_update(of=model))
    if record is None:
        raise HTTPException(404, "Registro no encontrado")
    return record


def issue_activation_grant(db, user, actor_id):
    from datetime import timedelta
    import hashlib
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    from .models import CustomerAccessGrant
    grant = CustomerAccessGrant(
        user_id=user.id,
        token_hash=token_hash,
        token_version=user.token_version,
        created_by=actor_id,
        expires_at=utcnow() + timedelta(days=7),
    )
    db.add(grant)
    return raw_token


def queue_credentials(db, customer, actor_id=None):
    if not customer.user_id or not customer.user:
        return None
    for old in db.scalars(select(Notification).where(
        Notification.user_id == customer.user_id, Notification.kind == "credentials",
        Notification.status.in_(["pending", "failed"]),
    ).with_for_update()):
        old.status, old.encrypted_payload = "failed", None
        old.blocked_reason = None
        old.last_error = "Acceso reemplazado por credenciales nuevas"
    password = secrets.token_urlsafe(15)
    customer.user.password_hash = password_hasher.hash(password)
    customer.user.must_change_password = True
    customer.user.token_version += 1
    raw_token = issue_activation_grant(db, customer.user, actor_id or customer.user.id)
    enqueue(db, customer, "credentials", "Acceso a su taller", (
        f"Hola {customer.full_name}.\nUsuario: {customer.user.username}\n"
        f"Contraseña temporal: {password}\nO active su cuenta directamente aquí: /activar?token={raw_token}\n"
        f"Debe cambiarla al iniciar sesión."
    ), private=True)
    return raw_token


@router.get("/customers")
def customers(db: Database, user: User = Depends(admin), include_inactive: bool = False, limit: int = Query(500, ge=1, le=2000), offset: int = Query(0, ge=0)):
    query = select(Customer).where(Customer.workshop_id == user.workshop_id).order_by(Customer.id.desc())
    if not include_inactive:
        query = query.where(Customer.active.is_(True))
    return [customer_json(row) for row in db.scalars(query.limit(limit).offset(offset))]


@router.post("/customers", status_code=201)
def create_customer(data: schemas.CustomerInput, db: Database, actor: User = Depends(admin)):
    values = data.model_dump()
    has_portal_access = values.pop("has_portal_access", True)
    values["email"] = str(data.email).lower()
    user = None
    if has_portal_access:
        user = User(
            username=f"cli-{secrets.token_hex(5)}",
            email=values["email"],
            password_hash="",
            role="customer",
            workshop_id=actor.workshop_id,
            must_change_password=True,
        )
    customer = Customer(**values, user=user, workshop_id=actor.workshop_id)
    db.add(customer)
    db.flush()
    token = None
    if user:
        token = queue_credentials(db, customer, actor_id=actor.id)
        db.flush()
        invalidate(db, audience={user.id})
    else:
        invalidate(db)
    result = customer_json(customer)
    if token:
        result["activation_token"] = token
        result["activation_url"] = f"/activar?token={token}"
        result["delivery_status"] = "pending"
    else:
        result["delivery_status"] = "none"
    return result


@router.put("/customers/{customer_id}")
def update_customer(customer_id: int, data: schemas.CustomerInput, db: Database, _: User = Depends(admin)):
    customer = get_record(db, Customer, customer_id)
    old_contact = (customer.email, customer.notification_channel, customer.telegram_chat_id)
    values = data.model_dump()
    values.pop("has_portal_access", None)
    for key, value in values.items():
        setattr(customer, key, str(value).lower() if key == "email" else value)
    if customer.user:
        customer.user.email = customer.email
    if old_contact != (customer.email, customer.notification_channel, customer.telegram_chat_id):
        from .notifications import retarget_pending
        retarget_pending(db, customer)
    db.flush()
    if customer.user_id:
        invalidate(db, audience={customer.user_id})
    else:
        invalidate(db)
    return customer_json(customer)


@router.delete("/customers/{customer_id}")
def delete_customer(customer_id: int, db: Database, _: User = Depends(admin)):
    customer = locked_record(db, Customer, customer_id)
    if db.scalar(select(WorkOrder.id).where(WorkOrder.customer_id == customer.id, WorkOrder.status.in_(["in_progress", "ready"]))):
        raise HTTPException(409, "Entregue o cancele las órdenes abiertas antes de desactivar al cliente")
    customer.active = False
    if customer.user:
        customer.user.active = False
        customer.user.token_version += 1
    db.flush()
    invalidate(db)
    if customer.user_id:
        invalidate(db, "session", {customer.user_id})
    return {"message": "Cliente desactivado; se conserva el historial"}


@router.post("/customers/{customer_id}/credentials")
def reset_credentials(customer_id: int, db: Database, actor: User = Depends(admin)):
    customer = active_customer(db, customer_id)
    token = queue_credentials(db, customer, actor_id=actor.id)
    invalidate(db)
    if customer.user_id:
        invalidate(db, "session", {customer.user_id})
    return {
        "delivery_status": "pending",
        "activation_token": token,
        "activation_url": f"/activar?token={token}" if token else None,
    }


@router.post("/customers/{customer_id}/enable-access")
def enable_customer_access(customer_id: int, db: Database, actor: User = Depends(admin)):
    customer = active_customer(db, customer_id)
    if customer.user_id and customer.user:
        raise HTTPException(409, "El cliente ya tiene una cuenta asociada")
    user = User(
        username=f"cli-{secrets.token_hex(5)}",
        email=customer.email,
        password_hash="",
        role="customer",
        workshop_id=actor.workshop_id,
        must_change_password=True,
    )
    customer.user = user
    db.flush()
    token = queue_credentials(db, customer, actor_id=actor.id)
    db.flush()
    invalidate(db, audience={user.id})
    return {
        **customer_json(customer),
        "activation_token": token,
        "activation_url": f"/activar?token={token}",
        "delivery_status": "pending",
    }


@router.post("/customers/{customer_id}/activation-link")
def get_activation_link(customer_id: int, db: Database, actor: User = Depends(admin)):
    customer = active_customer(db, customer_id)
    if not customer.user_id or not customer.user:
        raise HTTPException(400, "El cliente no tiene cuenta de acceso habilitada")
    token = queue_credentials(db, customer, actor_id=actor.id)
    db.flush()
    invalidate(db, audience={customer.user_id})
    return {
        "activation_token": token,
        "activation_url": f"/activar?token={token}",
        "message": "Enlace de activación generado",
    }


@router.post("/customers/{customer_id}/toggle-access")
def toggle_customer_access(customer_id: int, db: Database, _: User = Depends(admin)):
    customer = locked_record(db, Customer, customer_id)
    if not customer.user_id or not customer.user:
        raise HTTPException(400, "El cliente no tiene cuenta de acceso")
    customer.user.active = not customer.user.active
    customer.user.token_version += 1
    db.flush()
    invalidate(db)
    invalidate(db, "session", {customer.user_id})
    return customer_json(customer)


@router.get("/vehicles")
def vehicles(db: Database, user: User = Depends(authenticated), device: int | None = Depends(device_id), limit: int = Query(500, ge=1, le=2000), offset: int = Query(0, ge=0), include_inactive: bool = False, q: str = Query("", max_length=100), catalog_model_id: int | None = Query(None, gt=0)):
    require_feature(db, user, "vehicles", device)
    query = vehicle_query(user).options(selectinload(Vehicle.owner)).order_by(Vehicle.id.desc())
    if not include_inactive or user.role != "admin":
        query = query.where(Vehicle.active.is_(True))
    if catalog_model_id is not None:
        query = query.where(Vehicle.catalog_model_id == catalog_model_id)
    if q:
        from sqlalchemy import or_
        query = query.where(or_(Vehicle.plate.ilike(f"%{q}%"), Vehicle.brand.ilike(f"%{q}%"), Vehicle.model.ilike(f"%{q}%")))
    return [vehicle_json(row, user=user) for row in db.scalars(query.limit(limit).offset(offset))]


@router.post("/vehicles", status_code=201)
def create_vehicle(data: schemas.VehicleInput, db: Database, user: User = Depends(admin)):
    active_customer(db, data.owner_id)
    vehicle = Vehicle(**data.model_dump(exclude=CATALOG_FIELDS), workshop_id=user.workshop_id)
    db.add(vehicle)
    db.flush()
    # Se intenta enlazar con el catálogo. Si no resuelve, el vehículo se guarda
    # igual: el enlace es una ayuda, no un requisito para registrar un coche.
    match = (explicit_match(db, data) if CATALOG_FIELDS & data.model_fields_set
             else resolve_vehicle(db, data.brand, data.model, data.year))
    apply_catalog_match(db, vehicle, match)
    db.flush()
    db.add(OwnershipHistory(vehicle_id=vehicle.id, previous_owner_id=None, new_owner_id=data.owner_id, changed_by=user.id))
    invalidate(db, audience={vehicle.owner.user_id})
    return vehicle_json(vehicle)


@router.put("/vehicles/{vehicle_id}")
def update_vehicle(vehicle_id: int, data: schemas.VehicleInput, db: Database, _: User = Depends(admin)):
    vehicle = get_record(db, Vehicle, vehicle_id)
    if data.owner_id != vehicle.owner_id:
        raise HTTPException(409, "Use el traspaso de propietario para conservar la auditoría")
    identity_changed = (vehicle.brand, vehicle.model, vehicle.year) != (data.brand, data.model, data.year)
    for key, value in data.model_dump(exclude=CATALOG_FIELDS).items():
        setattr(vehicle, key, value)
    # Editar la marca o el modelo deja obsoleto el enlace anterior: se vuelve a
    # resolver, y si ya nada coincide se limpia en vez de dejar apuntando a una
    # ficha que ya no describe este coche.
    if CATALOG_FIELDS & data.model_fields_set:
        apply_catalog_match(db, vehicle, explicit_match(db, data))
    elif identity_changed:
        apply_catalog_match(db, vehicle, resolve_vehicle(db, data.brand, data.model, data.year))
    db.flush()
    invalidate(db, audience={vehicle.owner.user_id})
    return vehicle_json(vehicle)


@router.post("/vehicles/{vehicle_id}/transfer")
def transfer(vehicle_id: int, data: schemas.TransferInput, db: Database, user: User = Depends(admin)):
    vehicle = accessible_vehicle(db, vehicle_id, user, lock=True)
    if not vehicle:
        raise HTTPException(404, "Vehículo no encontrado")
    if vehicle.owner_id == data.owner_id:
        raise HTTPException(409, "El cliente ya es propietario")
    if db.scalar(select(WorkOrder.id).where(WorkOrder.vehicle_id == vehicle.id, WorkOrder.status.in_(["in_progress", "ready"]))):
        raise HTTPException(409, "Entregue o cancele las órdenes abiertas antes del traspaso")
    owner = active_customer(db, data.owner_id)
    previous_user_id = vehicle.owner.user_id
    db.add(OwnershipHistory(vehicle_id=vehicle.id, previous_owner_id=vehicle.owner_id, new_owner_id=owner.id, changed_by=user.id))
    vehicle.owner_id = owner.id
    vehicle.owner = owner
    invalidate(db, audience={previous_user_id, owner.user_id})
    return vehicle_json(vehicle)


@router.delete("/vehicles/{vehicle_id}")
def delete_vehicle(vehicle_id: int, db: Database, _: User = Depends(admin)):
    vehicle = locked_record(db, Vehicle, vehicle_id)
    if db.scalar(select(WorkOrder.id).where(WorkOrder.vehicle_id == vehicle.id, WorkOrder.status.in_(["in_progress", "ready"]))):
        raise HTTPException(409, "El vehículo tiene órdenes abiertas")
    vehicle.active = False
    invalidate(db, audience={vehicle.owner.user_id})
    return {"message": "Vehículo archivado"}


@router.get("/vehicles/{vehicle_id}/history")
def history(vehicle_id: int, db: Database, user: User = Depends(authenticated), device: int | None = Depends(device_id)):
    require_feature(db, user, "history", device)
    vehicle = accessible_vehicle(db, vehicle_id, user)
    from .access_policy import task_ids
    query = select(WorkOrder).where(WorkOrder.workshop_id == user.workshop_id)
    if user.role == "mechanic":
        query = order_query(user)
    return [{
        "id": row.id, "title": row.title, "date": row.created_at.isoformat(), "status": row.status,
        'intake_mileage': row.intake_mileage,
        'templates': [{'name': ref['name'], 'revision': ref['revision']} for ref in row.template_snapshot or []],
        'checklist': [{'label': item.label, 'status': 'completed' if item.completed else item.status,
                       'notes': item.notes if user.role != 'customer' else '',
                       'completed_at': item.completed_at.isoformat() if item.completed_at else None}
                      for item in row.items if user.role != 'mechanic' or item.id in task_ids(db, row, user)],
        "tasks": [item.label for item in row.items if item.completed and (user.role != "mechanic" or item.id in task_ids(db, row, user))],
    } for row in db.scalars(query.where(WorkOrder.vehicle_id == vehicle.id).order_by(WorkOrder.id.desc()))]


@router.get("/catalogs")
def catalogs(db: Database, user: User = Depends(admin), include_inactive: bool = False):
    query = select(MaintenanceCatalog).options(selectinload(MaintenanceCatalog.tasks)).where(MaintenanceCatalog.workshop_id == user.workshop_id)
    if not include_inactive:
        query = query.where(MaintenanceCatalog.active.is_(True))
    return [catalog_json(row) for row in db.scalars(query.order_by(MaintenanceCatalog.id.desc()))]


@router.post('/catalogs/reference')
def initial_templates(db: Database, user: User = Depends(admin)):
    from .models import Workshop
    db.scalar(select(Workshop).where(Workshop.id == user.workshop_id).with_for_update())
    created = seed_templates(db, user)
    invalidate(db)
    return {'created_ids': created, 'notice': 'Plantillas de referencia sin precio configurado; adapte al fabricante antes de utilizarlas.'}


@router.get('/vehicles/{vehicle_id}/maintenance-suggestions')
def suggestions(vehicle_id: int, db: Database, user: User = Depends(admin), mileage: int | None = Query(None, ge=0, le=10000000)):
    vehicle = accessible_vehicle(db, vehicle_id, user)
    current = vehicle.mileage if mileage is None else mileage
    if current < vehicle.mileage:
        raise HTTPException(422, 'El kilometraje es inferior al último registro')
    history = list(db.scalars(select(WorkOrder).where(WorkOrder.vehicle_id == vehicle.id, WorkOrder.status == 'delivered').order_by(WorkOrder.id.desc())))
    result = []
    for catalog in db.scalars(select(MaintenanceCatalog).options(selectinload(MaintenanceCatalog.tasks)).where(
            MaintenanceCatalog.workshop_id == user.workshop_id, MaintenanceCatalog.active.is_(True))):
        match = applicability(catalog, vehicle)
        if match == 'not_applicable':
            continue
        last = next((order for order in history if order.intake_mileage is not None and (
            any(ref.get('id') == catalog.id for ref in order.template_snapshot or []) or order.catalog_id == catalog.id)), None)
        due = ((last.intake_mileage if last else 0) + catalog.interval_km) if catalog.interval_km else None
        result.append({**catalog_json(catalog), 'applicability_status': match,
            'last_service_km': last.intake_mileage if last else None, 'due_at_km': due,
            'due': due is not None and current >= due,
            'basis': 'historial_entregado' if last else 'sin_historial_documentado',
            'warning': 'Sugerencia, no diagnóstico ni autorización. Confirme manual del fabricante y servicios fuera de MotorDesk.'})
    result.sort(key=lambda row: (not row['due'], row['due_at_km'] is None, row['name']))
    return {'vehicle_id': vehicle.id, 'mileage': current, 'items': result}


@router.post("/catalogs", status_code=201)
def create_catalog(data: schemas.CatalogInput, db: Database, user: User = Depends(admin)):
    catalog = MaintenanceCatalog(workshop_id=user.workshop_id)
    apply_catalog(db, catalog, data, user)
    db.add(catalog)
    db.flush()
    save_version(db, catalog, user)
    audit(db, user, 'maintenance.created', 'catalog', catalog.id)
    invalidate(db)
    return catalog_json(catalog)


@router.put("/catalogs/{catalog_id}")
def update_catalog(catalog_id: int, data: schemas.CatalogInput, db: Database, user: User = Depends(admin)):
    catalog = locked_record(db, MaintenanceCatalog, catalog_id)
    if data.expected_revision is not None and data.expected_revision != catalog.revision:
        raise HTTPException(409, 'La plantilla cambió; actualice antes de editar')
    save_version(db, catalog, user)
    # Los clientes previos no conocen los metadatos nuevos. No borrarlos al editar.
    for key in ('interval_km', 'schedule_source', 'applicability', 'active', 'price_configured'):
        if key not in data.model_fields_set:
            value = getattr(catalog, key)
            setattr(data, key, schemas.ApplicabilityInput(**value) if key == 'applicability' else value)
    apply_catalog(db, catalog, data, user)
    catalog.revision += 1
    db.flush()
    save_version(db, catalog, user)
    audit(db, user, 'maintenance.updated', 'catalog', catalog.id, {'revision': catalog.revision})
    invalidate(db)
    return catalog_json(catalog)


@router.delete("/catalogs/{catalog_id}")
def delete_catalog(catalog_id: int, db: Database, user: User = Depends(admin)):
    catalog = locked_record(db, MaintenanceCatalog, catalog_id)
    save_version(db, catalog, user)
    if catalog.active:
        catalog.active = False
        catalog.revision += 1
        save_version(db, catalog, user)
        audit(db, user, 'maintenance.archived', 'catalog', catalog.id)
    invalidate(db)
    return {"message": "Catálogo archivado; las órdenes conservan su checklist y precio"}


@router.get('/catalogs/{catalog_id}/versions')
def versions(catalog_id: int, db: Database, user: User = Depends(admin)):
    catalog = get_record(db, MaintenanceCatalog, catalog_id)
    return [{'revision': row.revision, 'snapshot': row.snapshot, 'created_at': row.created_at.isoformat()}
            for row in db.scalars(select(MaintenanceVersion).where(MaintenanceVersion.catalog_id == catalog.id).order_by(MaintenanceVersion.revision.desc()))]


@router.post('/catalogs/{catalog_id}/duplicate', status_code=201)
def duplicate(catalog_id: int, data: schemas.DuplicateCatalogInput, db: Database, user: User = Depends(admin)):
    source = get_record(db, MaintenanceCatalog, catalog_id)
    original = snapshot(source)
    payload = {key: value for key, value in original.items() if key not in ('id', 'revision')}
    payload.update(name=data.name, active=True)
    return create_catalog(schemas.CatalogInput(**payload), db, user)
