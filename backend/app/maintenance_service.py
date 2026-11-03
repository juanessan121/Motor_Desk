"""Reglas compartidas de plantillas, intervalos y ejecución del mantenimiento."""
from copy import deepcopy
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select

from .access_policy import audit
from .catalog_models import VehicleEngine, VehicleGeneration, VehicleMake, VehicleModel, VehiclePart
from .models import CatalogTask, MaintenanceCatalog, MaintenanceVersion, WorkOrder, utcnow

REFERENCE = 'Referencia genérica de MotorDesk; verificar y adaptar al manual del fabricante, motor y condiciones de uso.'
DEFAULT_TEMPLATES = [
    ('preventivo-basico', 'Mantenimiento preventivo básico', None, [
        'Revisar aceite del motor', 'Cambiar aceite cuando corresponda', 'Revisar filtro de aceite',
        'Inspeccionar filtro de aire', 'Revisar niveles de fluidos', 'Revisar presión y estado de neumáticos',
        'Verificar luces', 'Revisar estado general de frenos']),
    ('preventivo-completo', 'Mantenimiento preventivo completo', None, [
        'Revisión de lubricación', 'Inspección de filtros', 'Revisión del sistema de frenos',
        'Inspección de suspensión', 'Revisión del sistema de dirección', 'Revisión de batería',
        'Inspección del sistema de refrigeración', 'Revisión de correas',
        'Diagnóstico electrónico cuando aplique', 'Inspección general de seguridad']),
    ('frenos', 'Servicio de frenos', None, ['Inspeccionar pastillas', 'Revisar discos',
        'Revisar líquido de frenos', 'Inspeccionar posibles fugas', 'Verificar componentes asociados', 'Realizar comprobación final']),
    ('aceite-filtros', 'Cambio de aceite y filtros', None, ['Confirmar especificación del aceite',
        'Revisar cantidad requerida según fabricante', 'Cambiar aceite', 'Sustituir filtros correspondientes',
        'Verificar posibles fugas', 'Registrar kilometraje del servicio']),
    ('diagnostico', 'Diagnóstico automotriz', None, ['Registrar síntomas reportados',
        'Realizar inspección inicial', 'Consultar códigos de diagnóstico cuando aplique', 'Registrar resultados',
        'Determinar posibles causas', 'Proponer acciones correctivas']),
]


def task_data(task):
    return {key: getattr(task, key) for key in ('label', 'description', 'required', 'estimated_minutes', 'suggested_part_ids')}


def snapshot(catalog):
    return {'id': catalog.id, 'revision': catalog.revision, 'name': catalog.name,
            'description': catalog.description, 'base_price': str(catalog.base_price),
            'price_configured': catalog.price_configured, 'active': catalog.active,
            'interval_km': catalog.interval_km, 'schedule_source': catalog.schedule_source,
            'applicability': deepcopy(catalog.applicability),
            'tasks': [task_data(task) for task in catalog.tasks]}


def save_version(db, catalog, user):
    db.flush()
    if not db.scalar(select(MaintenanceVersion.id).where(
            MaintenanceVersion.catalog_id == catalog.id, MaintenanceVersion.revision == catalog.revision)):
        db.add(MaintenanceVersion(catalog_id=catalog.id, revision=catalog.revision,
                                  snapshot=snapshot(catalog), created_by=user.id))


def validate_catalog(db, data, user):
    condition = data.applicability.model_dump(exclude_none=True)
    references = {}
    for kind, model, field in [('make', VehicleMake, None), ('model', VehicleModel, 'make_id'),
                                ('generation', VehicleGeneration, 'model_id'), ('engine', VehicleEngine, 'generation_id')]:
        record_id = condition.get(kind + '_id')
        if record_id:
            from .catalog_browse_routes import visible
            row = db.scalar(select(model).where(model.id == record_id, visible(kind, model, user)))
            if not row:
                raise HTTPException(422, 'Referencia de aplicabilidad no disponible')
            references[kind] = row
    # Comprueba también referencias no contiguas, p. ej. marca + motor sin
    # seleccionar generación, para que no se mezclen ramas del catálogo.
    models = {'make': VehicleMake, 'model': VehicleModel, 'generation': VehicleGeneration, 'engine': VehicleEngine}
    parents = {'engine': ('generation', 'generation_id'), 'generation': ('model', 'model_id'), 'model': ('make', 'make_id')}
    for kind, row in references.items():
        current = kind
        while current in parents:
            current, field = parents[current]
            row = db.get(models[current], getattr(row, field))
            if row is None or (condition.get(current + '_id') is not None and condition[current + '_id'] != row.id):
                raise HTTPException(422, 'La jerarquía de aplicabilidad no coincide')
    ids = {part_id for task in data.tasks if not isinstance(task, str) for part_id in task.suggested_part_ids}
    if ids:
        from .catalog_browse_routes import visible
        known = set(db.scalars(select(VehiclePart.id).where(VehiclePart.id.in_(ids), visible('part', VehiclePart, user))))
        if known != ids:
            raise HTTPException(422, 'Hay repuestos sugeridos no disponibles en el catálogo')
    return condition


def apply_catalog(db, catalog, data, user):
    condition = validate_catalog(db, data, user)
    for key in ('name', 'description', 'base_price', 'active', 'price_configured', 'interval_km', 'schedule_source'):
        setattr(catalog, key, getattr(data, key))
    catalog.applicability = condition
    catalog.tasks = [CatalogTask(position=index, **({'label': task} if isinstance(task, str) else task.model_dump()))
                     for index, task in enumerate(data.tasks)]


def seed_templates(db, user):
    existing = set(db.scalars(select(MaintenanceCatalog.system_key).where(MaintenanceCatalog.workshop_id == user.workshop_id)))
    definitions = DEFAULT_TEMPLATES + [
        (f'paquete-{km}', f'Paquete de referencia {km:,} km'.replace(',', '.'), km,
         DEFAULT_TEMPLATES[0 if km < 20000 else 1][3]) for km in (5000, 10000, 20000)]
    created = []
    for key, name, km, tasks in definitions:
        if key in existing:
            continue
        catalog = MaintenanceCatalog(workshop_id=user.workshop_id, system_key=key, name=name,
            description=REFERENCE, base_price=Decimal('0.00'), price_configured=False,
            interval_km=km, schedule_source=REFERENCE, applicability={},
            tasks=[CatalogTask(label=label, position=i) for i, label in enumerate(tasks)])
        db.add(catalog)
        db.flush()
        save_version(db, catalog, user)
        audit(db, user, 'maintenance.reference_created', 'catalog', catalog.id)
        created.append(catalog.id)
    return created


def applicability(catalog, vehicle):
    """No inferir un motor ni una relación que no esté documentada."""
    unknown = False
    for key, expected in catalog.applicability.items():
        if key in ('year_from', 'year_to'):
            if key == 'year_from' and vehicle.year < expected or key == 'year_to' and vehicle.year > expected:
                return 'not_applicable'
        else:
            actual = getattr(vehicle, 'catalog_' + key, None)
            if actual is None:
                unknown = True
            elif actual != expected:
                return 'not_applicable'
    return 'unverified' if unknown or not catalog.applicability else 'documented_match'


def task_status(item):
    return 'completed' if item.completed else (item.status or 'pending')


def progress(items):
    applicable = [item for item in items if task_status(item) != 'not_applicable']
    return round(sum(task_status(item) == 'completed' for item in applicable) / len(applicable), 4) if applicable else (1 if items else 0)


def execution_complete(order):
    return bool(order.items) and all(task_status(item) in ('completed', 'not_applicable') for item in order.items)


def blockers(order):
    return order.base_approval != 'approved' or any(quote.decision == 'pending' for quote in order.quotes) or any(
        request.status in ('requested', 'approved') for request in order.part_requests)


def stage(order):
    if order.status in ('delivered', 'cancelled', 'ready'):
        return order.status
    if order.base_approval != 'approved':
        return 'pending_authorization'
    if any(request.status in ('requested', 'approved') for request in order.part_requests) or any(quote.decision == 'pending' for quote in order.quotes):
        return 'waiting'
    if execution_complete(order):
        return 'pending_review'
    if any(task_status(item) != 'pending' for item in order.items):
        return 'in_progress'
    return 'assigned' if any(grant.revoked_at is None for grant in order.assignments) else 'received'


def touch_order(order):
    order.revision += 1
    order.execution_reviewed_at = None
    order.execution_reviewed_by = None


def update_ready(db, order):
    if order.status in ('delivered', 'cancelled'):
        return
    # Legacy: sin reescribir el pasado, una autorización pendiente deja de poder
    # producir un nuevo aviso de «listo» en cualquier versión del flujo.
    ready = execution_complete(order) and not blockers(order) and (
        not order.review_required or order.execution_reviewed_at is not None)
    previous = order.status
    order.status = 'ready' if ready else 'in_progress'
    if previous != order.status and db.info.get('actor_id'):
        from .models import AuditEvent
        db.add(AuditEvent(workshop_id=order.workshop_id, actor_id=db.info['actor_id'],
            action='order.status_changed', resource_type='order', resource_id=order.id,
            payload={'before': previous, 'after': order.status, 'reason': 'Reevaluación de ejecución y autorizaciones'}))
    if ready and order.ready_notified_at is None:
        from .notifications import enqueue
        from .serializers import order_total
        order.ready_notified_at = utcnow()
        order_code_str = getattr(order, 'order_code', None) or f"#{order.id}"
        enqueue(
            db,
            order.customer,
            'vehicle_ready',
            'Vehículo listo para entrega',
            f'Estimado/a {order.customer.full_name}, su vehículo placa {order.vehicle.plate} se encuentra listo para entrega (Orden {order_code_str}). Estado final: Listo para entrega. Disponible para retiro en taller. Total: ${order_total(order):.2f}',
            order.id,
        )
