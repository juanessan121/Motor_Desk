import asyncio
import contextlib
import smtplib
import ssl
import socket
from datetime import timedelta
from email.message import EmailMessage
from email.utils import make_msgid

import httpx
from sqlalchemy import select, or_
from sqlalchemy.orm import Session

from .database import SessionLocal
from .events import hub
from .models import Customer, InboxEvent, Notification, User, utcnow
from .security import decrypt_payload, encrypt_payload
from .settings import settings


class DeliveryBlocked(RuntimeError):
    """No se resuelve reintentando en bucle: requiere conexión o corrección."""


def recipient_condition(customer):
    return or_(Notification.customer_id == customer.id,
               (Notification.customer_id.is_(None) & (Notification.user_id == customer.user_id))) if customer.user_id else Notification.customer_id == customer.id


def workshop_condition(workshop_id):
    return or_(Notification.customer_id.in_(select(Customer.id).where(Customer.workshop_id == workshop_id)),
               Notification.customer_id.is_(None) & Notification.user_id.in_(select(User.id).where(User.workshop_id == workshop_id)))


def notification_customer(db, row):
    if row.customer_id:
        return db.get(Customer, row.customer_id)
    return db.scalar(select(Customer).where(Customer.user_id == row.user_id)) if row.user_id else None


def delivery_problem(channel, payload, config=None, customer=None):
    config = config or settings()
    if customer is not None:
        if not customer.notifications_enabled:
            return 'Notificaciones desactivadas para este cliente'
        if channel == 'email' and not customer.email_notifications_enabled:
            return 'Canal de correo desactivado en las preferencias del cliente'
        if channel == 'telegram' and not customer.telegram_notifications_enabled:
            return 'Canal de Telegram desactivado en las preferencias del cliente'
        if channel == 'whatsapp' and not customer.whatsapp_notifications_enabled:
            return 'Canal de WhatsApp desactivado en las preferencias del cliente'
    if channel == 'email':
        if not config.smtp_host or not config.smtp_from:
            return 'Email / SMTP no conectado; configure el proveedor para reanudar'
        if not payload.get('to'):
            return 'Falta el correo del destinatario; edítelo desde Notificaciones'
    elif channel == 'telegram':
        if not config.telegram_bot_token:
            return 'Telegram Bot no conectado; configure el proveedor para reanudar'
        if not payload.get('chat_id'):
            return 'Falta el chat_id de Telegram; edítelo desde Notificaciones'
    elif channel == 'whatsapp':
        if not payload.get('whatsapp') and not payload.get('phone'):
            return 'Falta el número de WhatsApp; regístrelo desde Notificaciones'
        return 'Proveedor de WhatsApp no configurado en el servidor'
    else:
        return 'Canal de entrega no reconocido'
    return None


def credentials_expired(notification):
    date = notification.created_at
    if date is not None and date.tzinfo is None:
        from datetime import timezone
        date = date.replace(tzinfo=timezone.utc)
    return notification.kind == 'credentials' and date is not None and date < utcnow() - timedelta(hours=24)


def retarget_pending(db, customer):
    """Cambia destino/canal de envíos no entregados, sin regenerar accesos."""
    changed = 0
    for row in db.scalars(select(Notification).where(recipient_condition(customer),
            Notification.status.in_(['pending', 'failed']), Notification.encrypted_payload.is_not(None)).with_for_update()):
        if credentials_expired(row):
            row.status, row.encrypted_payload, row.blocked_reason = 'failed', None, None
            row.last_error = 'Credenciales vencidas; genere un nuevo acceso'
            continue
        payload = decrypt_payload(row.encrypted_payload)
        payload.update(to=customer.email, chat_id=customer.telegram_chat_id, whatsapp=customer.whatsapp or customer.phone)
        row.encrypted_payload = encrypt_payload(payload)
        row.channel = customer.notification_channel
        row.blocked_reason = delivery_problem(row.channel, payload, customer=customer)
        row.last_error = row.blocked_reason
        row.status, row.next_attempt_at = 'pending', utcnow()
        changed += 1
    return changed


def resume_available(db, workshop_id=None):
    query = select(Notification).where(Notification.blocked_reason.is_not(None),
        Notification.encrypted_payload.is_not(None), Notification.status == 'pending')
    if workshop_id is not None:
        query = query.where(workshop_condition(workshop_id))
    resumed = 0
    for row in db.scalars(query.with_for_update(of=Notification, skip_locked=True)):
        if credentials_expired(row):
            continue
        problem = delivery_problem(row.channel, decrypt_payload(row.encrypted_payload), customer=notification_customer(db, row))
        if problem is None:
            row.blocked_reason, row.last_error, row.next_attempt_at = None, None, utcnow()
            resumed += 1
    return resumed


def enqueue(db: Session, customer: Customer, kind: str, title: str, body: str, order_id: int | None = None, *, private=False, inspection_id=None):
    if not customer.user_id and kind == 'credentials':
        return None
    # Prevención de duplicados para el mismo evento, orden y destinatario
    if order_id is not None:
        duplicate = db.scalar(
            select(Notification).where(
                recipient_condition(customer),
                Notification.kind == kind,
                Notification.order_id == order_id,
                # Reutilizar también intentos fallidos y mensajes archivados.
                Notification.status.in_(['pending', 'sent', 'failed']),
            ).limit(1)
        )
        if duplicate:
            return duplicate

    payload = {
        "message_id": make_msgid(domain="motordesk.local"),
        "title": title,
        "body": body,
        "to": customer.email,
        "chat_id": customer.telegram_chat_id,
        "whatsapp": getattr(customer, "whatsapp", None) or customer.phone,
    }
    problem = delivery_problem(customer.notification_channel, payload, customer=customer)
    notification = Notification(
        user_id=customer.user_id,
        customer_id=customer.id,
        order_id=order_id,
        kind=kind,
        channel=customer.notification_channel,
        encrypted_payload=encrypt_payload(payload),
        blocked_reason=problem,
        last_error=problem,
    )
    db.add(notification)
    if not private and customer.user_id:
        db.add(InboxEvent(user_id=customer.user_id, title=title, body=body, order_id=order_id,
                          kind=kind, inspection_id=inspection_id))
    return notification


def send_email(payload: dict):
    config = settings()
    if not config.smtp_host or not config.smtp_from:
        raise DeliveryBlocked('Email / SMTP no conectado; configure el proveedor para reanudar')
    message = EmailMessage()
    message["From"] = config.smtp_from
    message["To"] = payload["to"]
    message["Subject"] = payload["title"]
    message["Message-ID"] = payload.get("message_id") or make_msgid(domain="motordesk.local")
    message.set_content(payload["body"])
    with smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=15) as server:
        if config.smtp_starttls:
            server.starttls(context=ssl.create_default_context())
        if config.smtp_username:
            server.login(config.smtp_username, config.smtp_password)
        server.send_message(message)
    return str(message["Message-ID"])


async def deliver(channel: str, payload: dict):
    if channel == "email":
        return await asyncio.to_thread(send_email, payload)
    elif channel == "telegram":
        if not settings().telegram_bot_token or not payload.get("chat_id"):
            raise DeliveryBlocked('Telegram no conectado o sin chat_id; corrija el canal para reanudar')
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                f"https://api.telegram.org/bot{settings().telegram_bot_token}/sendMessage",
                json={"chat_id": payload["chat_id"], "text": f'{payload["title"]}\n\n{payload["body"]}'},
            )
            if response.status_code in (400, 401, 403, 404):
                raise DeliveryBlocked('Telegram rechazó el bot o el chat_id; corrija el canal desde Notificaciones')
            if response.status_code != 200 or not response.json().get("ok"):
                raise RuntimeError("Telegram rechazó la entrega; revise bot y chat_id")
            return str(response.json()["result"]["message_id"])
    else:
        raise RuntimeError("Canal desconocido")


async def process_one():
    with SessionLocal() as db:
        for expired in db.scalars(select(Notification).where(
            Notification.kind == "credentials", Notification.encrypted_payload.is_not(None),
            Notification.created_at < utcnow() - timedelta(hours=24),
        ).with_for_update(skip_locked=True)):
            expired.status, expired.encrypted_payload, expired.blocked_reason = "failed", None, None
            expired.last_error = "Credenciales vencidas; genere un nuevo acceso"
        notification = db.scalar(
            select(Notification).where(
                Notification.status == "pending", Notification.next_attempt_at <= utcnow(),
                Notification.blocked_reason.is_(None), Notification.encrypted_payload.is_not(None),
            ).order_by(Notification.id).with_for_update(skip_locked=True).limit(1),
        )
        if notification is None:
            db.commit()
            return False
        try:
            payload = decrypt_payload(notification.encrypted_payload)
            problem = delivery_problem(notification.channel, payload, customer=notification_customer(db, notification))
            if problem:
                raise DeliveryBlocked(problem)
            notification.attempts += 1
            notification.provider_message_id = await deliver(notification.channel, payload)
            notification.status = "sent"
            notification.sent_at = utcnow()
            notification.last_error = None
            if notification.kind == "credentials":
                notification.encrypted_payload = None
        except (DeliveryBlocked, smtplib.SMTPAuthenticationError, smtplib.SMTPRecipientsRefused,
                smtplib.SMTPSenderRefused, smtplib.SMTPConnectError, httpx.ConnectError,
                httpx.TimeoutException, ConnectionError, TimeoutError, socket.gaierror) as exc:
            reason = str(exc) if isinstance(exc, DeliveryBlocked) else (
                'SMTP rechazó la autenticación o el destinatario; revise la configuración' if isinstance(exc, (
                    smtplib.SMTPAuthenticationError, smtplib.SMTPRecipientsRefused, smtplib.SMTPSenderRefused)) else
                'Canal sin conexión; corrija la conectividad y reanude desde Notificaciones')
            notification.blocked_reason, notification.last_error = reason, reason
        except Exception as exc:
            notification.last_error = str(exc) if isinstance(exc, RuntimeError) else f"Error de entrega: {type(exc).__name__}"
            notification.status = "failed" if notification.attempts >= 5 else "pending"
            notification.next_attempt_at = utcnow() + timedelta(seconds=min(3600, 30 * 2 ** notification.attempts))
        recipient = db.get(Customer, notification.customer_id) if notification.customer_id else db.get(User, notification.user_id)
        audience = set(db.scalars(select(User.id).where(User.role == "admin", User.active.is_(True), User.workshop_id == recipient.workshop_id)))
        if notification.user_id:
            audience.add(notification.user_id)
        db.commit()
        hub.publish("notifications", audience)
        return True


async def worker():
    # Una comprobación al arrancar tras configurar el servidor. No se reevalúan
    # los mensajes pausados cada pocos segundos ni se generan eventos repetidos.
    with SessionLocal.begin() as db:
        resume_available(db)
    while True:
        try:
            handled = await process_one()
            await asyncio.sleep(0.1 if handled else 3)
        except asyncio.CancelledError:
            raise
        except Exception:
            await asyncio.sleep(5)


@contextlib.asynccontextmanager
async def notification_lifespan():
    task = asyncio.create_task(worker()) if settings().notification_worker else None
    try:
        yield
    finally:
        if task:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
