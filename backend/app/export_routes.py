from decimal import Decimal
from datetime import timezone
from typing import Any, Dict, List
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from .access_policy import order_load_options
from .dependencies import Database, admin
from .maintenance_service import execution_complete, stage, task_status
from .models import AuditEvent, Customer, Notification, User, Vehicle, Workshop, WorkOrder, utcnow
from .serializers import customer_access_status, order_total
from .notifications import workshop_condition

def iso_utc(value):
    return value.replace(tzinfo=timezone.utc).isoformat() if value.tzinfo is None else value.isoformat()


router = APIRouter(tags=["Exportación y Conformidad Académica"])


def map_academic_stage(order: WorkOrder) -> str:
    """Mapea una orden de trabajo a uno de los 7 estados académicos automotrices:
    1. recepcionado
    2. diagnostico
    3. esperando_repuestos
    4. en_reparacion
    5. control_calidad
    6. listo_para_entrega
    7. entregado
    """
    if order.status == "delivered":
        return "entregado"
    if order.status == "ready":
        return "listo_para_entrega"
    if execution_complete(order):
        return "control_calidad"
    if any(request.status in ("requested", "approved") for request in order.part_requests) or any(
        quote.decision == "pending" for quote in order.quotes
    ):
        return "esperando_repuestos"
    if any(task_status(item) != "pending" for item in order.items):
        return "en_reparacion"
    if any(grant.revoked_at is None for grant in order.assignments):
        return "diagnostico"
    return "recepcionado"


def build_7_state_timeline(order: WorkOrder) -> List[Dict[str, Any]]:
    current = map_academic_stage(order)
    stage_order = [
        "recepcionado",
        "diagnostico",
        "esperando_repuestos",
        "en_reparacion",
        "control_calidad",
        "listo_para_entrega",
        "entregado",
    ]
    timeline = []
    for idx, st in enumerate(stage_order):
        # No inferir un recorrido lineal: una orden puede omitir etapas.
        date = {"recepcionado": order.created_at,
                "listo_para_entrega": order.ready_notified_at,
                "entregado": order.delivered_at}.get(st)
        reached = date is not None or st == current
        fecha = iso_utc(date) if date is not None else None

        timeline.append({
            "estado": st,
            "alcanzado": reached,
            "fecha": fecha,
        })
    return timeline


def export_workshop_payload(db: Database, workshop_id: int, user: User) -> Dict[str, Any]:
    workshop = db.get(Workshop, workshop_id)

    # 1. Clientes
    customers = list(
        db.scalars(
            select(Customer)
            .options(selectinload(Customer.user))
            .where(Customer.workshop_id == workshop_id)
            .order_by(Customer.id)
        )
    )
    clientes_data = []
    for c in customers:
        clientes_data.append({
            "id": c.id,
            "cedula_ruc": c.national_id,
            "nombre_completo": c.full_name,
            "email": c.email,
            "telefono": c.phone,
            "whatsapp": c.whatsapp,
            "direccion": c.address,
            "acceso_portal": {
                "tiene_acceso": bool(c.user_id),
                "estado": customer_access_status(c),
                "usuario": c.user.username if c.user else None,
            },
            "canales_notificacion": {
                "email_habilitado": c.email_notifications_enabled,
                "telegram_habilitado": c.telegram_notifications_enabled,
                "whatsapp_habilitado": c.whatsapp_notifications_enabled,
                "telegram_chat_id": c.telegram_chat_id,
                "canal_preferido": c.preferred_channel,
            },
        })

    # 2. Vehículos
    vehicles = list(
        db.scalars(
            select(Vehicle)
            .options(selectinload(Vehicle.owner))
            .where(Vehicle.workshop_id == workshop_id)
            .order_by(Vehicle.id)
        )
    )
    vehiculos_data = []
    for v in vehicles:
        vehiculos_data.append({
            "id": v.id,
            "placa": v.plate,
            "marca": v.brand,
            "modelo": v.model,
            "anio": v.year,
            "vin": v.vin,
            "color": v.color or "No especificado",
            "tipo_combustible": v.fuel_type or "gasolina",
            "kilometraje": v.mileage,
            "propietario": {
                "cliente_id": v.owner_id,
                "nombre": v.owner.full_name if v.owner else None,
                "cedula_ruc": v.owner.national_id if v.owner else None,
            },
        })

    # 3. Mantenimientos
    orders = list(
        db.scalars(
            select(WorkOrder)
            .options(*order_load_options())
            .where(WorkOrder.workshop_id == workshop_id)
            .order_by(WorkOrder.id)
        )
    )
    mantenimientos_data = []
    seguimiento_data = []
    histories = {}
    for event in db.scalars(select(AuditEvent).where(AuditEvent.workshop_id == workshop_id,
            AuditEvent.resource_type == 'order').order_by(AuditEvent.id)):
        if 'after' in event.payload:
            histories.setdefault(event.resource_id, []).append({
                'estado_anterior': event.payload.get('before'), 'estado_nuevo': event.payload['after'],
                'fecha': iso_utc(event.created_at), 'usuario_id': event.actor_id,
                'motivo': event.payload.get('reason'),
            })

    for o in orders:
        from .pricing import amounts
        labor, parts, subtotal, tax_rate, tax_amount, total = amounts(o)

        assigned_mech = next((grant.mechanic.username for grant in o.assignments if grant.revoked_at is None and getattr(grant, "mechanic", None)), None)

        mantenimientos_data.append({
            "orden_id": o.id,
            "codigo_orden": getattr(o, "order_code", None) or f"ORD-{o.id:04d}",
            "vehiculo": {
                "id": o.vehicle_id,
                "placa": o.vehicle.plate,
                "marca_modelo": f"{o.vehicle.brand} {o.vehicle.model}",
            },
            "cliente": {
                "id": o.customer_id,
                "nombre": o.customer.full_name if o.customer else None,
                "cedula_ruc": o.customer.national_id if o.customer else None,
            },
            "tipo_mantenimiento": getattr(o, "maintenance_type", None) or "preventivo-basico",
            "titulo": o.title,
            "descripcion_problema": getattr(o, "problem_description", None) or "Mantenimiento general programado",
            "diagnostico_tecnico": o.technical_diagnosis or "",
            "costos": {
                "mano_obra": float(labor),
                "repuestos": float(parts),
                "subtotal": float(subtotal),
                "porcentaje_iva": float(tax_rate * 100),
                "monto_iva": float(tax_amount),
                "total": float(total),
                "estado": "final" if o.status == "delivered" else "estimado",
            },
            "observaciones": {
                "observaciones_vehiculo": getattr(o.vehicle, "observations", None) if o.vehicle else None,
                "observaciones_orden": o.notes,
                "motivo_retraso": getattr(o, "delay_reason", None),
            },
            "fechas": {
                "creacion": iso_utc(o.created_at),
                "estimada_entrega": iso_utc(o.estimated_delivery_date) if o.estimated_delivery_date else None,
                "entrega_real": iso_utc(o.delivered_at) if getattr(o, "delivered_at", None) else None,
            },
            "actividades_incluidas": [
                {
                    "id": item.id,
                    "nombre": item.label,
                    "sistema": getattr(item, "system", None) or "general",
                    "estado": item.status or ("completed" if item.completed else "pending"),
                    "notas_tecnicas": getattr(item, "technical_notes", None),
                    "posicion": getattr(item, "position", item.id),
                    "requerido": item.required,
                    "mecanico_asignado": assigned_mech,
                }
                for item in o.items
            ],
        })

        # 4. Seguimiento de estados (7 estados automotrices)
        acad_stage = map_academic_stage(o)
        seguimiento_data.append({
            "orden_id": o.id,
            "codigo_orden": getattr(o, "order_code", None) or f"ORD-{o.id:04d}",
            "placa": o.vehicle.plate,
            "estado_actual": o.status,
            "estado_academico": acad_stage,
            "etapa_operativa": stage(o),
            "es_activo": o.status in ("in_progress", "ready"),
            "flujo_7_estados": build_7_state_timeline(o),
            "historial_real": histories.get(o.id, []),
        })

    # 5. Notificaciones
    notifs = list(
        db.scalars(
            select(Notification)
            .where(workshop_condition(workshop_id))
            .order_by(Notification.id)
        )
    )
    notificaciones_data = []
    for n in notifs:
        notificaciones_data.append({
            "id": n.id,
            "orden_id": getattr(n, "order_id", None),
            "destinatario": n.recipient or "Destinatario no especificado",
            "canal": n.channel or "email",
            "evento_tipo": n.kind or "general",
            "asunto": n.subject or f"Notificación: {n.kind}",
            "mensaje": "Acceso temporal omitido por seguridad" if n.kind == "credentials" else (n.body or ""),
            "identificador_externo": n.provider_message_id,
            "estado": n.status,
            "fecha_creacion": iso_utc(n.created_at),
            "fecha_envio": iso_utc(n.sent_at) if n.sent_at else None,
            "archivado": getattr(n, "archived_at", None) is not None,
        })

    return {
        "metadatos": {
            "sistema": "MotorDesk",
            "version": "1.0.0",
            "fecha_exportacion": utcnow().isoformat(),
            "taller_id": workshop.id if workshop else workshop_id,
            "nombre_taller": workshop.name if workshop else "Taller MotorDesk",
            "generado_por": user.username,
        },
        "clientes": clientes_data,
        "vehiculos": vehiculos_data,
        "mantenimientos": mantenimientos_data,
        "seguimiento_estados": seguimiento_data,
        "notificaciones": notificaciones_data,
    }


@router.get("/export/workshop-data")
def export_workshop_data(db: Database, user: User = Depends(admin)):
    return export_workshop_payload(db, user.workshop_id, user)
