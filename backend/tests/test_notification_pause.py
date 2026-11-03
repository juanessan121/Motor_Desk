import asyncio
from datetime import timedelta

import pytest
from sqlalchemy import select

from app import notifications
from app.models import Customer, Notification, User, Workshop, utcnow
from app.security import decrypt_payload, issue_token


def smtp(monkeypatch):
    monkeypatch.setattr(notifications.settings(), 'smtp_host', 'smtp.example.test')
    monkeypatch.setattr(notifications.settings(), 'smtp_from', 'taller@example.com')


def test_missing_provider_never_attempts_delivery_or_refreshes(client, admin_headers, make_customer, factory, monkeypatch):
    customer, _ = make_customer()
    calls = []
    async def deliver(*_): calls.append('send')
    monkeypatch.setattr(notifications, 'deliver', deliver)
    monkeypatch.setattr(notifications.hub, 'publish', lambda *_: calls.append('event'))
    for _ in range(3):
        assert asyncio.run(notifications.process_one()) is False
    assert calls == []
    with factory() as db:
        row = db.scalar(select(Notification).where(Notification.user_id == customer['user_id']))
        assert row.attempts == 0 and row.status == 'pending' and row.blocked_reason
    listed = client.get('/api/v1/notifications', headers=admin_headers).json()[0]
    assert listed['effective_status'] == 'paused' and not listed['can_retry']
    assert listed['customer_id'] == customer['id'] and listed['email'] == customer['email']
    assert 'encrypted_payload' not in listed
    assert client.post(f"/api/v1/notifications/{listed['id']}/retry", headers=admin_headers).status_code == 409


def test_disconnected_network_is_paused_after_one_real_attempt(client, admin_headers, make_customer, factory, monkeypatch):
    smtp(monkeypatch)
    make_customer()
    calls = []
    async def disconnected(*_):
        calls.append('send')
        raise ConnectionRefusedError('Mensaje externo no se publica')
    monkeypatch.setattr(notifications, 'deliver', disconnected)
    monkeypatch.setattr(notifications.hub, 'publish', lambda *_: calls.append('event'))
    assert asyncio.run(notifications.process_one())
    assert not asyncio.run(notifications.process_one())
    assert not asyncio.run(notifications.process_one())
    assert calls == ['send', 'event']
    with factory() as db:
        row = db.scalar(select(Notification))
        assert row.attempts == 1 and 'sin conexión' in row.blocked_reason
        assert row.encrypted_payload is not None


def test_edit_contact_retargets_pending_without_resetting_password(client, admin_headers, make_customer, factory, monkeypatch):
    customer, _ = make_customer()
    with factory() as db:
        original = db.scalar(select(Notification).where(Notification.user_id == customer['user_id']))
        content = decrypt_payload(original.encrypted_payload)
        password_hash = db.get(User, customer['user_id']).password_hash
    smtp(monkeypatch)
    response = client.patch(f"/api/v1/notifications/recipients/{customer['id']}", headers=admin_headers, json={
        'email': 'corregido@example.com', 'notification_channel': 'email', 'telegram_chat_id': None})
    assert response.status_code == 200, response.text
    with factory() as db:
        user = db.get(User, customer['user_id'])
        row = db.scalar(select(Notification).where(Notification.user_id == user.id))
        updated = decrypt_payload(row.encrypted_payload)
        assert updated['body'] == content['body'] and updated['title'] == content['title']
        assert updated['to'] == 'corregido@example.com' and row.blocked_reason is None
        assert user.email == db.get(Customer, customer['id']).email == 'corregido@example.com'
        assert user.password_hash == password_hash and not user.must_change_password
    assert 'password' not in response.text and 'encrypted_payload' not in response.text


def test_channel_change_telegram_and_manual_resume(client, admin_headers, make_customer, factory, monkeypatch):
    customer, _ = make_customer()
    payload = {'email': customer['email'], 'notification_channel': 'telegram', 'telegram_chat_id': '-10012345'}
    assert client.patch(f"/api/v1/notifications/recipients/{customer['id']}", headers=admin_headers, json=payload).status_code == 200
    assert client.post('/api/v1/notification-settings/resume', headers=admin_headers).json()['resumed'] == 0
    with factory() as db:
        row = db.scalar(select(Notification))
        assert row.channel == 'telegram' and row.blocked_reason is not None
        assert decrypt_payload(row.encrypted_payload)['chat_id'] == '-10012345'
    monkeypatch.setattr(notifications.settings(), 'telegram_bot_token', 'test-only-token')
    assert client.post('/api/v1/notification-settings/resume', headers=admin_headers).json()['resumed'] == 1
    assert client.post('/api/v1/notification-settings/resume', headers=admin_headers).json()['resumed'] == 0


def test_contact_permissions_validation_and_expired_credentials(client, admin_headers, make_customer, factory):
    customer, customer_headers = make_customer()
    path = f"/api/v1/notifications/recipients/{customer['id']}"
    data = {'email': customer['email'], 'notification_channel': 'email', 'telegram_chat_id': None}
    assert client.patch(path, headers=customer_headers, json=data).status_code == 403
    assert client.patch(path, headers=admin_headers, json={**data, 'email': 'incorrecto'}).status_code == 422
    assert client.patch(path, headers=admin_headers, json={**data, 'notification_channel': 'telegram'}).status_code == 422
    with factory.begin() as db:
        row = db.scalar(select(Notification))
        row.created_at = utcnow() - timedelta(hours=25)
        user = User(workshop_id=1, username='notificaciones-mecanico', email='notificaciones-mech@example.com', role='mechanic',
                    password_hash='test-only', must_change_password=False)
        db.add(user); db.flush()
        mechanic = {'Authorization': 'Bearer ' + issue_token(user)}
        db.add(Workshop(id=2, name='Otro taller')); db.flush()
        other = User(workshop_id=2, username='notification-other-admin', email='notification-other@example.com', role='admin',
                    password_hash='test-only', must_change_password=False)
        db.add(other); db.flush()
        foreign = {'Authorization': 'Bearer ' + issue_token(other)}
    assert client.patch(path, headers=mechanic, json=data).status_code == 403
    assert client.patch(path, headers=foreign, json=data).status_code == 404
    assert client.patch(path, headers=admin_headers, json={**data, 'email': 'otrocorreo@example.com'}).status_code == 200
    with factory() as db:
        row = db.scalar(select(Notification))
        assert row.status == 'failed' and row.encrypted_payload is None and row.blocked_reason is None


def test_original_customer_form_also_corrects_queued_destination(client, admin_headers, make_customer, factory):
    customer, _ = make_customer()
    body = {key: customer[key] for key in ('national_id', 'first_name', 'last_name', 'email', 'notification_channel')}
    body['email'] = 'cambiado-en-clientes@example.com'
    assert client.put(f"/api/v1/customers/{customer['id']}", headers=admin_headers, json=body).status_code == 200
    with factory() as db:
        row = db.scalar(select(Notification))
        assert decrypt_payload(row.encrypted_payload)['to'] == body['email']
        assert row.blocked_reason is not None and row.attempts == 0
