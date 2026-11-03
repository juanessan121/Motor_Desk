from decimal import Decimal, ROUND_HALF_UP
import warnings
import hashlib
from io import BytesIO
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import select

from . import schemas
from .branding import effective_config, require_feature
from .dependencies import Database, admin, authenticated, device_id, invalidate, staff
from .access_policy import accessible_order, accessible_vehicle, assignment, audit, order_load_options, order_query, photo_allowed, require_task
from .models import (
    ChecklistItem, Customer, ExtraQuote, IntakePhoto, MaintenanceCatalog,
    QuoteOption, User, Vehicle, WorkOrder, utcnow,
)
from .maintenance_service import (applicability, blockers, execution_complete, save_version, snapshot,
                                  task_status, touch_order, update_ready)
from .notifications import enqueue
from .registry_routes import active_customer, get_record, locked_record
from .serializers import order_json, order_total

router = APIRouter(prefix="/orders", tags=["Órdenes y mantenimiento"])


def editable(order):
    if order.status in {"delivered", "cancelled"}:
        raise HTTPException(409, "La orden está cerrada")


def visible_order(db, order, user, device):
    flags = effective_config(db, user.id, device)["features"] if user.role == "customer" else {"quotes": True, "photos": True}
    return order_json(order, show_quotes=flags["quotes"], show_photos=flags["photos"], db=db, user=user)


@router.get("")
def orders(db: Database, user: User = Depends(authenticated), device: int | None = Depends(device_id), limit: int = Query(500, ge=1, le=2000), offset: int = Query(0, ge=0)):
    require_feature(db, user, "maintenance", device)
    query = order_query(user).options(*order_load_options()).order_by(WorkOrder.id.desc())
    return [visible_order(db, row, user, device) for row in db.scalars(query.limit(limit).offset(offset))]


@router.get("/{order_id}")
def detail(order_id: int, db: Database, user: User = Depends(authenticated), device: int | None = Depends(device_id)):
    require_feature(db, user, "maintenance", device)
    return visible_order(db, accessible_order(db, order_id, user), user, device)


@router.post("", status_code=201)
def create_order(data: schemas.OrderInput, db: Database, user: User = Depends(admin)):
    digest = hashlib.sha256(data.model_dump_json(exclude={'request_key'}).encode()).hexdigest()
    vehicle = accessible_vehicle(db, data.vehicle_id, user, lock=True)
    if data.request_key:
        previous = db.scalar(select(WorkOrder).where(WorkOrder.workshop_id == user.workshop_id, WorkOrder.request_key == str(data.request_key)))
        if previous:
            if previous.request_hash != digest:
                raise HTTPException(409, 'La confirmación ya se usó con otros datos')
            return order_json(previous, db=db, user=user)
    if not vehicle or not vehicle.active:
        raise HTTPException(404, "Vehículo activo no encontrado")
    if db.scalar(select(WorkOrder.id).where(WorkOrder.vehicle_id == vehicle.id, WorkOrder.status.in_(["in_progress", "ready"]))):
        raise HTTPException(409, "El vehículo ya tiene una orden abierta")
    customer = active_customer(db, data.customer_id or vehicle.owner_id)
    service_ids = data.catalog_ids or [data.catalog_id]
    locked = {key: locked_record(db, MaintenanceCatalog, key) for key in sorted(service_ids)}
    catalogs = [locked[key] for key in service_ids]
    for catalog in catalogs:
        if not catalog.active or not catalog.tasks or not catalog.price_configured:
            raise HTTPException(409, 'Configure el precio y las tareas de la plantilla activa antes de abrir la orden')
        if applicability(catalog, vehicle) == 'not_applicable':
            raise HTTPException(422, 'La plantilla no corresponde a la referencia del vehículo')
        save_version(db, catalog, user)
    mileage = data.mileage if data.mileage is not None else vehicle.mileage
    if mileage < vehicle.mileage:
        raise HTTPException(422, 'El kilometraje es inferior al último registro')
    vehicle.mileage = mileage
    included = set(data.included_tasks) if data.included_tasks is not None else None
    template_items = [
        ChecklistItem(
            label=task.label,
            description=task.description,
            required=task.required,
            estimated_minutes=task.estimated_minutes,
            suggested_part_ids=task.suggested_part_ids,
            template_catalog_id=catalog.id,
        )
        for catalog in catalogs
        for task in catalog.tasks
        if included is None or task.label in included
    ]
    extra_items = [
        ChecklistItem(label=task.label, notes=task.reason)
        for task in data.extra_tasks
    ]
    all_items = template_items + extra_items
    if not all_items:
        raise HTTPException(422, "La orden debe contener al menos una actividad seleccionada")
    labor = data.labor_cost if data.labor_cost is not None else sum(catalog.base_price for catalog in catalogs)
    parts = data.parts_cost if data.parts_cost is not None else Decimal("0.00")
    subtotal = labor + parts
    tax_rate = Decimal(str(effective_config(db, workshop_id=user.workshop_id)["regional"]["tax_rate"]))
    tax_amount = (subtotal * tax_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    total_amount = subtotal + tax_amount
    order = WorkOrder(
        workshop_id=user.workshop_id,
        vehicle_id=vehicle.id, vehicle=vehicle, customer_id=customer.id, customer=customer,
        catalog_id=catalogs[0].id, title=' + '.join(catalog.name for catalog in catalogs)[:150],
        order_code=data.order_code,
        maintenance_type=data.maintenance_type,
        problem_description=data.problem_description or data.symptoms or "Mantenimiento general programado",
        technical_diagnosis=data.technical_diagnosis,
        base_total=sum(catalog.base_price for catalog in catalogs),
        labor_cost=labor, parts_cost=parts, tax_rate=tax_rate, tax_amount=tax_amount, total_amount=total_amount,
        notes=data.notes, symptoms=data.symptoms, delay_reason=data.delay_reason,
        estimated_delivery_date=data.estimated_delivery_date,
        intake_mileage=mileage, template_snapshot=[snapshot(catalog) for catalog in catalogs],
        priority=data.priority, review_required=True,
        request_key=str(data.request_key) if data.request_key else None, request_hash=digest,
        payer_snapshot={"name": customer.full_name, "national_id": customer.national_id, "email": customer.email, "address": customer.address},
        items=all_items,
    )
    db.add(order)
    db.flush()
    if not order.order_code:
        order.order_code = f"OT-{order.created_at.year}-{order.id:04d}"
        db.flush()
    if data.mechanic_id:
        from .assignment_routes import assign
        assign(order.id, schemas.AssignmentInput(mechanic_id=data.mechanic_id, task_ids=[item.id for item in order.items]), db, user)
    order_code_str = order.order_code or f"#{order.id}"
    date_str = order.created_at.strftime("%d/%m/%Y %H:%M")
    enqueue(
        db,
        customer,
        "order_created",
        "Recepción de vehículo",
        f"Estimado/a {customer.full_name}, confirmamos la recepción de su vehículo placa {vehicle.plate} con fecha de ingreso {date_str}. Orden de trabajo N° {order_code_str}. Servicio: {order.title}.",
        order.id,
    )
    audit(db, user, "order.created", "order", order.id, {'before': None, 'after': order.status, 'reason': 'Recepción'})
    invalidate(db, audience={order.customer.user_id}, order_id=order.id)
    return order_json(order, db=db, user=user)


@router.patch("/{order_id}/items/{item_id}")
def check_item(order_id: int, item_id: int, data: schemas.ChecklistInput, db: Database, user: User = Depends(staff)):
    order = accessible_order(db, order_id, user, lock=True)
    editable(order)
    require_task(db, order, user, item_id)
    item = next((item for item in order.items if item.id == item_id), None)
    if item is None:
        raise HTTPException(404, "Ítem no encontrado")
    if data.expected_revision is not None and data.expected_revision != item.revision:
        raise HTTPException(409, 'La actividad cambió; actualice la orden')
    if data.status is not None and data.expected_revision is None:
        raise HTTPException(422, 'Incluya la revisión de la actividad')
    next_status = data.status or (('completed' if data.completed else 'pending') if data.completed is not None else task_status(item))
    if next_status in ('in_progress', 'completed') and order.base_approval != 'approved':
        raise HTTPException(409, 'Espere la aceptación del servicio por el cliente antes de ejecutar')
    notes = item.notes if data.notes is None else data.notes
    if next_status in ('not_applicable', 'attention') and not notes.strip():
        raise HTTPException(422, 'Explique por qué no aplica o qué requiere atención')
    if next_status == 'not_applicable' and item.required and user.role != 'admin':
        raise HTTPException(403, 'Una actividad obligatoria solo puede excluirla administración con justificación')
    before = {'status': task_status(item), 'notes': item.notes}
    if before != {'status': next_status, 'notes': notes}:
        item.status, item.notes = next_status, notes
        item.completed = next_status == 'completed'
        item.completed_at = utcnow() if item.completed else None
        item.completed_by = user.id if item.completed else None
        item.updated_at, item.updated_by = utcnow(), user.id
        item.revision += 1
        touch_order(order)
        audit(db, user, 'task.completed' if item.completed else 'task.updated', 'order', order.id,
              {'task_id': item.id, 'before': before, 'status': next_status, 'notes': notes, 'revision': item.revision})
    update_ready(db, order)
    invalidate(db, audience={order.customer.user_id}, order_id=order.id)
    return visible_order(db, order, user, None)


@router.post('/{order_id}/items', status_code=201)
def add_item(order_id: int, data: schemas.ExtraTaskInput, db: Database, user: User = Depends(admin)):
    order = accessible_order(db, order_id, user, lock=True)
    editable(order)
    item = ChecklistItem(label=data.label, notes=data.reason)
    order.items.append(item)
    touch_order(order)
    db.flush()
    audit(db, user, 'task.added', 'order', order.id, {'task_id': item.id, 'reason': data.reason, 'no_additional_charge': True})
    update_ready(db, order)
    invalidate(db, audience={order.customer.user_id}, order_id=order.id)
    return visible_order(db, order, user, None)


@router.post('/{order_id}/execution-review')
def review_execution(order_id: int, data: schemas.OrderReviewInput, db: Database, user: User = Depends(admin)):
    order = accessible_order(db, order_id, user, lock=True)
    editable(order)
    if order.revision != data.expected_revision:
        raise HTTPException(409, 'La ejecución cambió; actualice antes de revisar')
    if blockers(order) or not execution_complete(order):
        raise HTTPException(409, 'Resuelva actividades, autorizaciones y solicitudes antes de aprobar la ejecución')
    order.execution_reviewed_at, order.execution_reviewed_by = utcnow(), user.id
    order.revision += 1
    audit(db, user, 'order.execution_reviewed', 'order', order.id, {'note': data.note, 'revision': order.revision})
    update_ready(db, order)
    invalidate(db, audience={order.customer.user_id}, order_id=order.id)
    return visible_order(db, order, user, None)


@router.post("/{order_id}/quotes", status_code=201)
def create_quote(order_id: int, data: schemas.QuoteInput, db: Database, user: User = Depends(staff)):
    order = accessible_order(db, order_id, user, lock=True)
    editable(order)
    require_task(db, order, user, data.task_id)
    if user.role == "mechanic" and not assignment(db, order.id, user).can_quote:
        raise HTTPException(403, "Esta asignación no permite cotizar")
    # No se solicita una aprobación que el cliente no pueda responder.
    flags = effective_config(db, order.customer.user_id)["features"]
    if not flags["quotes"] or not flags["maintenance"]:
        raise HTTPException(409, "Habilite el seguimiento y las aprobaciones de este cliente antes de cotizar")
    quote = ExtraQuote(title=data.title, task_id=data.task_id, options=[QuoteOption(**option.model_dump()) for option in data.options])
    order.quotes.append(quote)
    touch_order(order)
    order.status, order.ready_notified_at = "in_progress", None
    db.flush()
    enqueue(db, order.customer, "quote_requested", "Repuesto pendiente de aprobación", f"{order.vehicle.plate}: {data.title}. Revise las variantes y autorice o rechace el gasto en la app.", order.id)
    audit(db, user, "quote.created", "order", order.id, {"quote_id": quote.id})
    invalidate(db, audience={order.customer.user_id}, order_id=order.id)
    return visible_order(db, order, user, None)


@router.post("/{order_id}/quotes/{quote_id}/decision")
def decide(order_id: int, quote_id: int, data: schemas.DecisionInput, db: Database, user: User = Depends(authenticated), device: int | None = Depends(device_id)):
    if user.role != "customer":
        raise HTTPException(403, "Solo el cliente pagador puede aprobar un gasto")
    require_feature(db, user, "quotes", device)
    require_feature(db, user, "maintenance", device)
    order = accessible_order(db, order_id, user, lock=True)
    editable(order)
    quote = next((row for row in order.quotes if row.id == quote_id), None)
    if quote is None:
        raise HTTPException(404, "Cotización no encontrada")
    if quote.decision != "pending":
        raise HTTPException(409, "Esta cotización ya fue respondida")
    option = next((row for row in quote.options if row.id == data.option_id), None)
    if data.decision == "approved" and option is None:
        raise HTTPException(422, "La variante no pertenece a esta cotización")
    quote.decision, quote.decided_at = data.decision, utcnow()
    quote.selected_option_id = option.id if option else None
    if option:
        added = ChecklistItem(label=f"{quote.title}: {option.label}", quote_id=quote.id)
        order.items.append(added)
        db.flush()
        # Si una cotización nació de una tarea asignada, su instalación también
        # llega al mismo técnico; no se concede acceso a tareas ajenas.
        for grant in order.assignments:
            if grant.revoked_at is None and quote.task_id in grant.task_ids:
                grant.task_ids = [*grant.task_ids, added.id]
                grant.revision += 1
    touch_order(order)
    db.flush()
    update_ready(db, order)
    audit(db, user, "quote." + data.decision, "order", order.id, {"quote_id": quote.id})
    invalidate(db, audience={order.customer.user_id}, order_id=order.id)
    return visible_order(db, order, user, device)


@router.patch("/{order_id}/status")
def status(order_id: int, status: Literal["delivered", "cancelled"], db: Database, user: User = Depends(admin)):
    order = accessible_order(db, order_id, user, lock=True)
    editable(order)
    if status == "delivered" and order.status != "ready":
        raise HTTPException(409, "Complete las tareas y resuelva las cotizaciones antes de entregar")
    if status == 'delivered' and (blockers(order) or not execution_complete(order) or (order.review_required and order.execution_reviewed_at is None)):
        raise HTTPException(409, 'Falta autorización o revisión final antes de entregar')
    previous = order.status
    if status == 'delivered':
        from .pricing import freeze_final
        freeze_final(order)
    order.status = status
    order.revision += 1
    if status == "delivered":
        order.delivered_at = utcnow()
        completed_tasks = ", ".join(item.label for item in order.items if item.completed) or order.title
        from .serializers import order_total
        total_val = order.total_amount if order.total_amount is not None else order_total(order)
        order_code_str = order.order_code or f"OT-{order.id}"
        enqueue(
            db,
            order.customer,
            "payment_info",
            "Información de pago y liquidación",
            f"Orden N° {order_code_str}. Servicios realizados: {completed_tasks}. Valor total a pagar: ${total_val:.2f} (impuesto aplicado: {order.tax_rate * 100:g}%).",
            order.id,
        )
    from .workshop_routes import close_location
    close_location(db, order, user, "Cierre de orden: " + status)
    audit(db, user, "order." + status, "order", order.id, {'before': previous, 'after': status, 'reason': 'Cierre de orden'})
    invalidate(db, audience={order.customer.user_id}, order_id=order.id)
    return order_json(order)


@router.post("/{order_id}/photos", status_code=201)
async def upload_photo(order_id: int, db: Database, user: User = Depends(staff), file: UploadFile = File(), caption: str = Form(default="", max_length=250), task_id: int | None = Form(default=None), inspection_id: int | None = Form(default=None), finding_id: int | None = Form(default=None), expected_revision: int | None = Form(default=None)):
    order = accessible_order(db, order_id, user, lock=True)
    editable(order)
    require_task(db, order, user, task_id)
    inspection = None
    if inspection_id is not None:
        from .inspection_routes import get_inspection, check_revision
        inspection = get_inspection(db, inspection_id, user, write=True)
        if inspection.order_id != order.id or inspection.task_id != task_id:
            raise HTTPException(422, "La inspección no corresponde a esta orden/tarea")
        check_revision(inspection, expected_revision)
    if finding_id is not None:
        from .models import Finding
        finding = db.get(Finding, finding_id)
        if inspection is None or finding is None or finding.inspection_id != inspection.id or not finding.active:
            raise HTTPException(422, "Hallazgo no válido para la inspección")
    if len(order.photos) >= 12:
        raise HTTPException(409, "Máximo 12 fotografías por recepción")
    raw = await file.read(5 * 1024 * 1024 + 1)
    if len(raw) > 5 * 1024 * 1024:
        raise HTTPException(413, "La foto supera 5 MB")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(raw)) as source:
                if source.format not in {"PNG", "JPEG", "WEBP"} or source.width * source.height > 20000000:
                    raise ValueError("Formato o dimensiones inválidas")
                image = ImageOps.exif_transpose(source).convert("RGB")
                image.thumbnail((1920, 1920))
                buffer = BytesIO()
                image.save(buffer, format="JPEG", quality=85)
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise HTTPException(422, "Use una imagen JPEG, PNG o WebP válida de hasta 20 megapíxeles") from exc
    photo = IntakePhoto(order_id=order.id, uploaded_by=user.id, caption=caption, content=buffer.getvalue(), task_id=task_id, inspection_id=inspection_id, finding_id=finding_id)
    db.add(photo)
    db.flush()
    if inspection:
        from .inspection_routes import touch_inspection
        touch_inspection(db, inspection, user)
    audit(db, user, "photo.created.internal", "order", order.id, {"photo_id": photo.id})
    invalidate(db, order_id=order.id)
    return {"id": photo.id, "caption": photo.caption}


@router.post('/{order_id}/notes/publication')
def publish_notes(order_id: int, data: schemas.NotesPublicationInput, db: Database,
                  user: User = Depends(admin)):
    order = accessible_order(db, order_id, user, lock=True)
    if order.notes_published != data.expected_published:
        raise HTTPException(409, 'La publicación cambió; actualice la orden')
    if data.published and not order.notes.strip():
        raise HTTPException(409, 'No hay notas que publicar')
    order.notes_published = data.published
    audit(db, user, 'order.notes_published' if data.published else 'order.notes_internal', 'order', order.id)
    invalidate(db, audience={order.customer.user_id}, order_id=order.id)
    return visible_order(db, order, user, None)


@router.get("/{order_id}/photos/{photo_id}")
def photo(order_id: int, photo_id: int, db: Database, user: User = Depends(authenticated), device: int | None = Depends(device_id)):
    require_feature(db, user, "photos", device)
    order = accessible_order(db, order_id, user)
    photo = get_record(db, IntakePhoto, photo_id)
    if photo.order_id != order_id:
        raise HTTPException(404, "Fotografía no encontrada")
    if not photo_allowed(db, photo, order, user):
        raise HTTPException(404, "Fotografía no encontrada")
    return Response(photo.content, media_type="image/jpeg", headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})


@router.post("/{order_id}/photos/{photo_id}/publication")
def publish_photo(order_id: int, photo_id: int, data: schemas.PublicationInput, db: Database, user: User = Depends(admin)):
    order = accessible_order(db, order_id, user, lock=True)
    photo = get_record(db, IntakePhoto, photo_id)
    if photo.order_id != order.id:
        raise HTTPException(404, "Fotografía no encontrada")
    photo.published_at = utcnow() if data.published else None
    photo.published_by = user.id if data.published else None
    audit(db, user, "photo.published" if data.published else "photo.internal", "order", order.id, {"photo_id": photo.id})
    invalidate(db, audience={order.customer.user_id}, order_id=order.id)
    return {"id": photo.id, "published": data.published}


@router.post("/{order_id}/approval")
def base_approval(order_id: int, data: schemas.BaseApprovalInput, db: Database, user: User = Depends(authenticated), device: int | None = Depends(device_id)):
    if user.role != "customer":
        raise HTTPException(403, "La aceptación corresponde al cliente pagador")
    require_feature(db, user, "maintenance", device)
    order = accessible_order(db, order_id, user, lock=True)
    editable(order)
    if order.base_approval != "pending":
        raise HTTPException(409, "La aceptación ya fue registrada")
    order.base_approval = "approved" if data.approved else "rejected"
    order.base_approved_at, order.base_approved_by = utcnow(), user.id
    touch_order(order)
    update_ready(db, order)
    audit(db, user, "order.base_" + order.base_approval, "order", order.id)
    invalidate(db, audience={user.id}, order_id=order.id)
    return visible_order(db, order, user, device)


@router.post('/{order_id}/recorded-approval')
def recorded_approval(order_id: int, data: schemas.RecordedApprovalInput, db: Database, user: User = Depends(admin)):
    order = accessible_order(db, order_id, user, lock=True)
    editable(order)
    if order.customer.user_id is not None:
        raise HTTPException(409, 'Este cliente tiene portal; debe registrar allí su decisión')
    if order.revision != data.expected_revision or order.base_approval != 'pending':
        raise HTTPException(409, 'La orden cambió o su autorización ya fue registrada')
    order.base_approval = 'approved' if data.approved else 'rejected'
    order.base_approved_at, order.base_approved_by = utcnow(), user.id
    touch_order(order)
    update_ready(db, order)
    audit(db, user, 'order.recorded_approval', 'order', order.id, {
        'decision': order.base_approval, 'note': data.note, 'channel': 'in_person',
        'customer_id': order.customer_id, 'authorized_total': str(order_total(order)),
    })
    invalidate(db, order_id=order.id)
    return visible_order(db, order, user, None)
