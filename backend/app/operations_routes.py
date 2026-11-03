import asyncio
import time
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import func, or_, select

from .dependencies import Database, admin, authenticated, bearer, device_id, invalidate, staff
from .events import hub
from .models import Customer, InboxEvent, Inspection, Notification, User, Vehicle, WorkOrder, utcnow
from . import schemas
from .access_policy import audit
from .notifications import credentials_expired, delivery_problem, retarget_pending, resume_available, workshop_condition, notification_customer
from .security import decrypt_payload
from .registry_routes import get_record, locked_record
from .security import decode_token
from .serializers import order_total
from .settings import settings
from .access_policy import order_load_options, order_query, task_ids
from .maintenance_service import stage, task_status
from .branding import effective_config

router = APIRouter(tags=["Operaciones y eventos"])


@router.get("/dashboard")
def dashboard(db: Database, user: User = Depends(staff)):
    orders = list(db.scalars(order_query(user).options(*order_load_options())))
    if user.role == "mechanic":
        items = [item for order in orders for item in order.items if item.id in task_ids(db, order, user)]
        return {"assigned_orders": len(orders), "assigned_tasks": len(items),
            "pending_tasks": sum(task_status(item) not in ('completed', 'not_applicable') for item in items), "completed_tasks": sum(item.completed for item in items),
            "in_progress": sum(row.status == "in_progress" for row in orders), "ready": sum(row.status == "ready" for row in orders)}
    return {
        'operational_counts': {key: sum(stage(order) == key for order in orders) for key in ('received', 'pending_authorization', 'assigned', 'in_progress', 'waiting', 'pending_review', 'ready')},
        'pending_parts': sum(request.status in ('requested', 'approved') for order in orders if order.status not in ('delivered', 'cancelled') for request in order.part_requests),
        'attention_tasks': sum(task_status(item) == 'attention' for order in orders if order.status not in ('delivered', 'cancelled') for item in order.items),
        "customers": db.scalar(select(func.count(Customer.id)).where(Customer.active.is_(True), Customer.workshop_id == user.workshop_id)),
        "vehicles": db.scalar(select(func.count(Vehicle.id)).where(Vehicle.active.is_(True), Vehicle.workshop_id == user.workshop_id)),
        "in_progress": sum(row.status == "in_progress" for row in orders),
        "ready": sum(row.status == "ready" for row in orders),
        "pending_quotes": sum(quote.decision == "pending" for row in orders if row.status == "in_progress" for quote in row.quotes),
        "delivered_total": str(sum((order_total(row) for row in orders if row.status == "delivered"), Decimal("0.00"))),
    }


@router.get("/notifications")
def notifications(db: Database, user: User = Depends(authenticated), device: int | None = Depends(device_id),
                  limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0), include_archived: bool = False):
    if user.role == "admin":
        query = select(Notification, Customer).outerjoin(Customer, or_(Customer.id == Notification.customer_id,
            Notification.customer_id.is_(None) & (Customer.user_id == Notification.user_id))).where(workshop_condition(user.workshop_id))
        if not include_archived:
            query = query.where(Notification.archived_at.is_(None))
        return [{
            "id": row.id, "user_id": row.user_id, "order_id": row.order_id, "kind": row.kind, "channel": row.channel,
            "status": row.status, "attempts": row.attempts, "last_error": row.last_error,
            "sent_at": row.sent_at, "provider_message_id": row.provider_message_id,
            "subject": row.subject if row.kind != "credentials" else "Acceso al taller",
            "body": row.body if row.kind != "credentials" else "Acceso temporal protegido; gestione el acceso desde Clientes.",
            "created_at": row.created_at.isoformat(),
            'blocked_reason': row.blocked_reason,
            'effective_status': 'paused' if row.blocked_reason else row.status,
            'can_retry': bool(row.status != 'sent' and row.encrypted_payload and not credentials_expired(row)
                              and delivery_problem(row.channel, decrypt_payload(row.encrypted_payload), customer=customer) is None),
            'customer_id': customer.id if customer else None,
            'recipient_name': customer.full_name if customer else None,
            'email': customer.email if customer else None,
            'whatsapp': customer.whatsapp if customer else None,
            'notification_channel': customer.notification_channel if customer else row.channel,
            'telegram_chat_id': customer.telegram_chat_id if customer else None,
            'notifications_enabled': customer.notifications_enabled if customer else True,
            'email_notifications_enabled': customer.email_notifications_enabled if customer else True,
            'telegram_notifications_enabled': customer.telegram_notifications_enabled if customer else True,
            'whatsapp_notifications_enabled': customer.whatsapp_notifications_enabled if customer else True,
            'archived': row.archived_at is not None,
        } for row, customer in db.execute(query.order_by(Notification.id.desc()).offset(offset).limit(limit))]
    query = select(InboxEvent).where(InboxEvent.user_id == user.id)
    allowed_orders = order_query(user).with_only_columns(WorkOrder.id)
    query = query.where(or_(InboxEvent.order_id.is_(None), InboxEvent.order_id.in_(allowed_orders)))
    if user.role == 'customer':
        flags = effective_config(db, user.id, device)['features']
        if not flags['maintenance']:
            query = query.where(InboxEvent.order_id.is_(None) | InboxEvent.kind.in_(['inspection_published', 'inspection_withdrawn']))
        if not flags['quotes']:
            query = query.where(InboxEvent.kind != 'quote_requested')
        if not flags['history']:
            query = query.where(~InboxEvent.kind.in_(['inspection_published', 'inspection_withdrawn']))
        # Los eventos antiguos no se clasifican analizando el texto. Ante un
        # permiso parcial no se puede garantizar su contenido: se ocultan.
        if not all(flags[key] for key in ('maintenance', 'quotes', 'history', 'photos')):
            query = query.where(~((InboxEvent.kind == 'legacy') & InboxEvent.order_id.is_not(None)))
        published = select(Inspection.id).where(Inspection.published_at.is_not(None))
        query = query.where((InboxEvent.kind != 'inspection_published') | InboxEvent.inspection_id.in_(published))
    return [{
        "id": row.id, "title": row.title, "body": row.body,
        "kind": row.kind, "inspection_id": row.inspection_id,
        "order_id": row.order_id if user.role != 'customer' or flags['maintenance'] else None,
        "created_at": row.created_at.isoformat(),
    } for row in db.scalars(query.order_by(InboxEvent.id.desc()).offset(offset).limit(limit))]


@router.get('/notifications/recipients')
def notification_recipients(db: Database, user: User = Depends(admin)):
    customers = list(db.scalars(select(Customer).where(Customer.workshop_id == user.workshop_id, Customer.active.is_(True)).order_by(Customer.first_name)))
    return [{
        "id": c.id,
        "customer_id": c.id,
        "name": c.full_name,
        "email": c.email,
        "phone": c.phone,
        "whatsapp": c.whatsapp,
        "telegram_chat_id": c.telegram_chat_id,
        "notification_channel": c.notification_channel,
        "notifications_enabled": c.notifications_enabled,
        "email_notifications_enabled": c.email_notifications_enabled,
        "telegram_notifications_enabled": c.telegram_notifications_enabled,
        "whatsapp_notifications_enabled": c.whatsapp_notifications_enabled,
        "has_account": c.user_id is not None,
    } for c in customers]


@router.post('/notifications/{notification_id}/archive')
def archive_notification(notification_id: int, db: Database, user: User = Depends(admin)):
    notification = locked_record(db, Notification, notification_id)
    notification.archived_at = utcnow()
    notification.archived_by = user.id
    db.flush()
    invalidate(db, 'notifications')
    return {"message": "Notificación descartada de la bandeja activa", "archived": True}


@router.post('/notifications/cleanup')
def cleanup_notifications(db: Database, user: User = Depends(admin), days: int = Query(0, ge=0)):
    from datetime import timedelta
    cutoff = utcnow() - timedelta(days=days) if days > 0 else utcnow()
    count = 0
    for row in db.scalars(select(Notification).where(
        workshop_condition(user.workshop_id),
        Notification.archived_at.is_(None),
        Notification.status.in_(['sent', 'failed']),
        Notification.created_at <= cutoff,
    ).with_for_update()):
        row.archived_at = utcnow()
        row.archived_by = user.id
        count += 1
    db.flush()
    if count:
        audit(db, user, 'notifications.cleaned', 'workshop', user.workshop_id, {'count': count})
        invalidate(db, 'notifications')
    return {"message": f"{count} notificaciones limpiadas de la bandeja", "cleaned": count}


@router.get("/notification-settings")
def notification_settings(db: Database, user: User = Depends(admin)):
    config = settings()
    return {"email_configured": bool(config.smtp_host and config.smtp_from), "telegram_configured": bool(config.telegram_bot_token),
        'paused_count': db.scalar(select(func.count(Notification.id)).where(
            workshop_condition(user.workshop_id), Notification.blocked_reason.is_not(None), Notification.archived_at.is_(None))),
        'worker_enabled': config.notification_worker}


@router.post('/notification-settings/resume')
def resume_notifications(db: Database, user: User = Depends(admin)):
    count = resume_available(db, user.workshop_id)
    if count:
        audit(db, user, 'notifications.resumed', 'workshop', user.workshop_id, {'count': count})
        invalidate(db, 'notifications')
    return {'resumed': count, 'message': 'Solo se reanudan los mensajes con proveedor y destinatario disponibles.'}


@router.patch('/notifications/recipients/{customer_id}')
def edit_recipient(customer_id: int, data: schemas.NotificationContactInput, db: Database, user: User = Depends(admin)):
    customer = locked_record(db, Customer, customer_id)
    if not customer.active:
        raise HTTPException(409, 'El cliente está desactivado')
    email = str(data.email).lower()
    customer.email = email
    if customer.user:
        customer.user.email = email
    customer.notification_channel = data.notification_channel
    customer.telegram_chat_id = data.telegram_chat_id or None
    if data.whatsapp is not None:
        customer.whatsapp = data.whatsapp
    if data.notifications_enabled is not None:
        customer.notifications_enabled = data.notifications_enabled
    if data.email_notifications_enabled is not None:
        customer.email_notifications_enabled = data.email_notifications_enabled
    if data.telegram_notifications_enabled is not None:
        customer.telegram_notifications_enabled = data.telegram_notifications_enabled
    if data.whatsapp_notifications_enabled is not None:
        customer.whatsapp_notifications_enabled = data.whatsapp_notifications_enabled
    db.flush()
    changed = retarget_pending(db, customer)
    audit(db, user, 'notification.contact_updated', 'customer', customer.id, {'channel': customer.notification_channel, 'retargeted': changed})
    if customer.user_id:
        invalidate(db, 'notifications', {customer.user_id})
    else:
        invalidate(db, 'notifications')
    return {
        'customer_id': customer.id, 'email': customer.email, 'notification_channel': customer.notification_channel,
        'telegram_chat_id': customer.telegram_chat_id, 'whatsapp': customer.whatsapp,
        'notifications_enabled': customer.notifications_enabled,
        'email_notifications_enabled': customer.email_notifications_enabled,
        'telegram_notifications_enabled': customer.telegram_notifications_enabled,
        'whatsapp_notifications_enabled': customer.whatsapp_notifications_enabled,
        'message': 'Contacto y preferencias actualizadas sin duplicar información. Envíos pendientes redirigidos.'
    }


@router.delete('/notifications/recipients/{customer_id}/channel/{channel_name}')
def remove_recipient_channel(customer_id: int, channel_name: str, db: Database, user: User = Depends(admin)):
    customer = locked_record(db, Customer, customer_id)
    if not customer.active:
        raise HTTPException(409, 'El cliente está desactivado')
    if channel_name == 'telegram':
        customer.telegram_chat_id = None
        customer.telegram_notifications_enabled = False
        if customer.notification_channel == 'telegram':
            customer.notification_channel = 'email'
    elif channel_name == 'whatsapp':
        customer.whatsapp = ""
        customer.whatsapp_notifications_enabled = False
        if customer.notification_channel == 'whatsapp':
            customer.notification_channel = 'email'
    elif channel_name == 'email':
        customer.email_notifications_enabled = False
    else:
        raise HTTPException(400, f"Canal '{channel_name}' no reconocido")
    db.flush()
    changed = retarget_pending(db, customer)
    audit(db, user, 'notification.channel_removed', 'customer', customer.id, {'channel': channel_name, 'retargeted': changed})
    if customer.user_id:
        invalidate(db, 'notifications', {customer.user_id})
    else:
        invalidate(db, 'notifications')
    return {
        'customer_id': customer.id,
        'notification_channel': customer.notification_channel,
        'email_notifications_enabled': customer.email_notifications_enabled,
        'telegram_notifications_enabled': customer.telegram_notifications_enabled,
        'whatsapp_notifications_enabled': customer.whatsapp_notifications_enabled,
        'telegram_chat_id': customer.telegram_chat_id,
        'whatsapp': customer.whatsapp,
        'message': f'Canal {channel_name} desactivado/removido para el cliente sin afectar su historial.',
    }


@router.post("/notifications/{notification_id}/retry")
def retry(notification_id: int, db: Database, _: User = Depends(admin)):
    notification = locked_record(db, Notification, notification_id)
    if notification.status == "sent" or not notification.encrypted_payload:
        raise HTTPException(409, "Mensaje enviado o contenido vencido. Para credenciales, genere un acceso nuevo")
    if credentials_expired(notification):
        raise HTTPException(409, 'Las credenciales vencieron; genere un nuevo acceso con confirmación')
    problem = delivery_problem(notification.channel, decrypt_payload(notification.encrypted_payload), customer=notification_customer(db, notification))
    if problem:
        raise HTTPException(409, problem)
    notification.status, notification.attempts = "pending", 0
    notification.blocked_reason = None
    notification.next_attempt_at, notification.last_error = utcnow(), None
    invalidate(db, "notifications")
    return {"status": "pending"}


@router.get("/events")
async def events(request: Request, user: User = Depends(authenticated), credentials=Depends(bearer)):
    user_id = user.id
    expiration = decode_token(credentials.credentials)["exp"]

    async def stream():
        async with hub.subscribe(user_id) as queue:
            yield 'event: refresh\ndata: {"type":"connected"}\n\n'
            while time.time() < expiration:
                if await request.is_disconnected():
                    break
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=min(20, max(0.1, expiration - time.time())))
                    yield f"event: refresh\ndata: {payload}\n\n"
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
