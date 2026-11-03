import asyncio
import copy
from datetime import timedelta
from io import BytesIO
from uuid import uuid4

from PIL import Image
from sqlalchemy import func, select

from app import notifications
from app.branding import DEFAULT_CONFIG
from app.events import EventHub
from app.models import Customer, Notification, OwnershipHistory, User, utcnow
from app.security import decrypt_payload, verify_password


def config_payload(client):
    config = client.get("/api/v1/public/config").json()
    return {key: config[key] for key in ("schema_version", "branding", "features")} | {"expected_revision": config["revision"]}


def complete_items(client, headers, order):
    result = order
    for item in order["items"]:
        response = client.patch(f'/api/v1/orders/{order["id"]}/items/{item["id"]}', headers=headers, json={"completed": True})
        assert response.status_code == 200, response.text
        result = response.json()
    if result.get('operational_stage') == 'pending_review':
        reviewed = client.post(f'/api/v1/orders/{order["id"]}/execution-review', headers=headers,
                              json={'expected_revision': result['revision'], 'note': 'Revisión final documentada en prueba'})
        assert reviewed.status_code == 200, reviewed.text
        result = reviewed.json()
    return result


def test_health_and_private_routes(client):
    assert client.get("/api/v1/health").json()["database"] == "connected"
    assert client.get("/api/v1/customers").status_code == 401
    assert client.get("/api/v1/public/config").json()["schema_version"] == 1


def test_temporary_password_required_and_old_token_revoked(client):
    login = client.post("/api/v1/auth/login", json={"username": "admin", "password": "test-only-admin-password"}).json()
    headers = {"Authorization": "Bearer " + login["access_token"]}
    assert client.get("/api/v1/customers", headers=headers).status_code == 403
    change = client.post("/api/v1/auth/password", headers=headers, json={"current_password": "test-only-admin-password", "new_password": "new-admin-password-123"})
    assert change.status_code == 200
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401


def test_credentials_encrypted_not_returned(client, admin_headers, factory):
    response = client.post("/api/v1/customers", headers=admin_headers, json={"national_id": "123456", "first_name": "Ana", "last_name": "Paz", "email": "ana@example.com"})
    assert response.status_code == 201
    assert "password" not in response.text
    with factory() as db:
        user = db.get(User, response.json()["user_id"])
        notification = db.scalar(select(Notification).where(Notification.user_id == user.id))
        body = decrypt_payload(notification.encrypted_payload)["body"]
        password = body.split("Contraseña temporal: ")[1].splitlines()[0]
        assert password not in notification.encrypted_payload
        assert verify_password(password, user.password_hash)
        assert user.password_hash.startswith("$argon2id$")
    listing = client.get("/api/v1/notifications", headers=admin_headers)
    assert "encrypted_payload" not in listing.text
    assert password not in listing.text


def test_duplicate_customer_rolls_back_user(client, admin_headers, make_customer, factory):
    make_customer()
    with factory() as db:
        before = db.scalar(select(func.count(User.id)))
    result = client.post("/api/v1/customers", headers=admin_headers, json={"national_id": "1000001", "first_name": "Otro", "last_name": "Cliente", "email": "otro@example.com"})
    assert result.status_code == 409
    with factory() as db:
        assert db.scalar(select(func.count(User.id))) == before


def test_telegram_requires_chat_id(client, admin_headers):
    response = client.post("/api/v1/customers", headers=admin_headers, json={"national_id": "1234", "first_name": "Ana", "last_name": "Paz", "email": "ana@example.com", "notification_channel": "telegram"})
    assert response.status_code == 422


def test_config_revision_and_color_validation(client, admin_headers):
    payload = config_payload(client)
    payload["branding"]["colors"]["primary"] = "#FF5500"
    saved = client.put("/api/v1/config/global", headers=admin_headers, json=payload)
    assert saved.status_code == 200
    assert saved.json()["revision"] == 2
    assert client.put("/api/v1/config/global", headers=admin_headers, json=payload).status_code == 409
    payload["expected_revision"] = 2
    payload["branding"]["colors"]["primary"] = "rojo"
    assert client.put("/api/v1/config/global", headers=admin_headers, json=payload).status_code == 422


def test_flag_precedence_global_account_device(client, admin_headers, make_customer):
    customer, headers = make_customer(device=str(uuid4()))
    device = client.get("/api/v1/devices", headers=admin_headers).json()[0]
    assert client.put(f'/api/v1/config/devices/{device["id"]}', headers=admin_headers, json={"features": {"vehicles": False}}).status_code == 200
    assert client.get("/api/v1/vehicles", headers=headers).status_code == 403
    assert client.get("/api/v1/config", headers=headers).json()["features"]["vehicles"] is False
    assert client.put(f'/api/v1/config/users/{customer["user_id"]}', headers=admin_headers, json={"features": {"maintenance": True}}).status_code == 200
    payload = config_payload(client)
    payload["features"]["maintenance"] = False
    assert client.put("/api/v1/config/global", headers=admin_headers, json=payload).status_code == 200
    assert client.get("/api/v1/orders", headers=headers).status_code == 403


def test_device_restrictions_cannot_be_bypassed_by_omitting_header(client, admin_headers, make_customer):
    _, headers = make_customer()
    without_device = {"Authorization": headers["Authorization"]}
    assert client.get("/api/v1/vehicles", headers=without_device).status_code == 403
    assert client.get("/api/v1/vehicles", headers={**headers, "X-Device-Id": str(uuid4())}).status_code == 403


def test_customers_cannot_manage_other_accounts(client, admin_headers, work_order, make_customer):
    order, _, first_headers = work_order
    _, second_headers = make_customer("2")
    assert client.get(f'/api/v1/orders/{order["id"]}', headers=second_headers).status_code == 404
    assert client.get("/api/v1/orders", headers=second_headers).json() == []
    assert client.get("/api/v1/customers", headers=first_headers).status_code == 403
    assert client.put("/api/v1/config/global", headers=first_headers, json=config_payload(client)).status_code == 403


def test_ready_notification_is_idempotent(client, admin_headers, work_order, factory):
    order, _, customer = work_order
    assert client.post(f'/api/v1/orders/{order["id"]}/approval', headers=customer, json={'approved': True}).status_code == 200
    result = complete_items(client, admin_headers, order)
    assert result["progress"] == 1
    assert result["status"] == "ready"
    assert result["total"] == "115.12"
    complete_items(client, admin_headers, order)
    with factory() as db:
        rows = list(db.scalars(select(Notification).where(Notification.kind == "vehicle_ready")))
        assert len(rows) == 1
        assert "$115.12" in decrypt_payload(rows[0].encrypted_payload)["body"]


def test_quote_approval_adds_installation_and_exact_total(client, admin_headers, work_order):
    order, _, customer_headers = work_order
    assert client.post(f'/api/v1/orders/{order["id"]}/approval', headers=customer_headers, json={'approved': True}).status_code == 200
    quote_response = client.post(f'/api/v1/orders/{order["id"]}/quotes', headers=admin_headers, json={"title": "Pastillas", "options": [{"label": "Original", "price": "25.20"}, {"label": "Nacional", "price": "20.00"}]})
    assert quote_response.status_code == 201, quote_response.text
    quote = quote_response.json()["quotes"][0]
    result = complete_items(client, admin_headers, order)
    assert result["status"] == "in_progress"
    decision_path = f'/api/v1/orders/{order["id"]}/quotes/{quote["id"]}/decision'
    assert client.post(decision_path, headers=admin_headers, json={"decision": "approved", "option_id": quote["options"][0]["id"]}).status_code == 403
    approved = client.post(decision_path, headers=customer_headers, json={"decision": "approved", "option_id": quote["options"][0]["id"]})
    assert approved.status_code == 200, approved.text
    assert approved.json()["total"] == "144.10"
    assert len(approved.json()["items"]) == 3
    assert approved.json()["status"] == "in_progress"
    assert client.post(decision_path, headers=customer_headers, json={"decision": "rejected"}).status_code == 409
    assert complete_items(client, admin_headers, approved.json())["status"] == "ready"


def test_quote_wrong_option_and_rejection(client, admin_headers, work_order):
    order, _, headers = work_order
    response = client.post(f'/api/v1/orders/{order["id"]}/quotes', headers=admin_headers, json={"title": "Batería", "options": [{"label": "Original", "price": "50.00"}]})
    quote = response.json()["quotes"][0]
    path = f'/api/v1/orders/{order["id"]}/quotes/{quote["id"]}/decision'
    assert client.post(path, headers=headers, json={"decision": "approved", "option_id": 999999}).status_code == 422
    rejected = client.post(path, headers=headers, json={"decision": "rejected"})
    assert rejected.status_code == 200
    assert rejected.json()["total"] == "115.12"
    assert len(rejected.json()["items"]) == 2


def test_catalog_changes_do_not_rewrite_orders(client, admin_headers, work_order):
    order, _, headers = work_order
    catalog_id = client.get("/api/v1/catalogs", headers=admin_headers).json()[0]["id"]
    assert client.put(f"/api/v1/catalogs/{catalog_id}", headers=admin_headers, json={"name": "Nuevo nombre", "base_price": "999.00", "tasks": ["Nueva tarea"]}).status_code == 200
    current = client.get(f'/api/v1/orders/{order["id"]}', headers=headers).json()
    assert current["title"] == order["title"]
    assert current["base_total"] == "100.10"
    assert len(current["items"]) == 2


def test_transfer_preserves_history_without_previous_payer_data(client, admin_headers, work_order, make_customer, factory):
    order, old_customer, old_headers = work_order
    assert client.post(f'/api/v1/orders/{order["id"]}/approval', headers=old_headers, json={'approved': True}).status_code == 200
    new_customer, new_headers = make_customer("2")
    vehicle_id = order["vehicle_id"]
    path = f"/api/v1/vehicles/{vehicle_id}/transfer"
    assert client.post(path, headers=admin_headers, json={"owner_id": new_customer["id"]}).status_code == 409
    complete_items(client, admin_headers, order)
    assert client.patch(f'/api/v1/orders/{order["id"]}/status?status=delivered', headers=admin_headers).status_code == 200
    response = client.post(path, headers=admin_headers, json={"owner_id": new_customer["id"]})
    assert response.status_code == 200
    assert client.get("/api/v1/vehicles", headers=old_headers).json() == []
    assert client.get(f'/api/v1/orders/{order["id"]}', headers=new_headers).status_code == 404
    history = client.get(f'/api/v1/vehicles/{vehicle_id}/history', headers=new_headers)
    assert history.status_code == 200
    assert old_customer["email"] not in history.text
    assert "payer_snapshot" not in history.text
    assert "total" not in history.text
    with factory() as db:
        assert db.scalar(select(func.count(OwnershipHistory.id))) == 2


def test_photo_upload_protected_and_validated(client, admin_headers, work_order, make_customer):
    order, _, headers = work_order
    _, stranger = make_customer("2")
    path = f'/api/v1/orders/{order["id"]}/photos'
    assert client.post(path, headers=admin_headers, files={"file": ("bad.jpg", b"not an image", "image/jpeg")}).status_code == 422
    buffer = BytesIO()
    Image.new("RGB", (20, 20), "red").save(buffer, format="PNG")
    photo = client.post(path, headers=admin_headers, files={"file": ("car.png", buffer.getvalue(), "image/png")})
    assert photo.status_code == 201, photo.text
    photo_path = path + "/" + str(photo.json()["id"])
    assert client.get(photo_path, headers=headers).status_code == 404
    assert client.post(photo_path + '/publication', headers=admin_headers, json={"published": True}).status_code == 200
    assert client.get(photo_path, headers=headers).headers["content-type"] == "image/jpeg"
    assert client.get(photo_path, headers=stranger).status_code == 404
    payload = config_payload(client)
    payload["features"]["photos"] = False
    client.put("/api/v1/config/global", headers=admin_headers, json=payload)
    assert client.get(photo_path, headers=headers).status_code == 403


def test_notification_delivery_clears_encrypted_credentials(client, admin_headers, make_customer, factory, monkeypatch):
    monkeypatch.setattr(notifications.settings(), 'smtp_host', 'smtp.example.test')
    monkeypatch.setattr(notifications.settings(), 'smtp_from', 'taller@example.com')
    customer, _ = make_customer()
    received = []
    async def deliver(channel, payload):
        received.append((channel, payload))
    monkeypatch.setattr(notifications, "deliver", deliver)
    assert asyncio.run(notifications.process_one())
    with factory() as db:
        row = db.scalar(select(Notification).where(Notification.user_id == customer["user_id"]))
        assert row.status == "sent"
        assert row.encrypted_payload is None
    assert received[0][0] == "email"
    assert "Contraseña temporal:" in received[0][1]["body"]


def test_unconfigured_provider_not_reported_as_sent(client, admin_headers, make_customer, factory):
    make_customer()
    assert asyncio.run(notifications.process_one()) is False
    with factory() as db:
        row = db.scalar(select(Notification))
        assert row.status == "pending"
        assert row.attempts == 0
        assert row.blocked_reason is not None and 'SMTP no conectado' in row.blocked_reason


def test_login_rate_limit(client):
    for _ in range(5):
        assert client.post("/api/v1/auth/login", json={"username": "missing", "password": "wrong"}).status_code == 401
    assert client.post("/api/v1/auth/login", json={"username": "missing", "password": "wrong"}).status_code == 429


def test_sse_broker_targets_only_expected_account():
    async def check():
        hub = EventHub()
        async with hub.subscribe(1) as one, hub.subscribe(2) as two:
            hub.publish("config", {1})
            assert '"config"' in one.get_nowait()
            assert two.empty()
            hub.publish("data")
            assert not two.empty()
        assert hub.subscribers == {}
    asyncio.run(check())


def test_money_negative_and_fractional_cents_rejected(client, admin_headers):
    for price in ("-1.00", "1.001"):
        response = client.post("/api/v1/catalogs", headers=admin_headers, json={"name": "Servicio", "base_price": price, "tasks": ["Aceite"]})
        assert response.status_code == 422


def test_cors_allows_only_configured_origin(client):
    headers = {"Origin": "http://localhost:8080", "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "Authorization,Content-Type,X-Device-Id"}
    response = client.options("/api/v1/auth/login", headers=headers)
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:8080"
    forbidden = client.options("/api/v1/auth/login", headers={**headers, "Origin": "https://unknown.example.com"})
    assert forbidden.status_code == 400
    assert "access-control-allow-origin" not in forbidden.headers


def test_customer_edit_does_not_regenerate_credentials(client, admin_headers, make_customer, factory):
    customer, _ = make_customer()
    data = {key: customer[key] for key in ("national_id", "first_name", "last_name", "address", "phone", "email", "telegram_chat_id", "notification_channel")}
    data.update({"first_name": "Nombre actualizado", "email": "actualizado@example.com"})
    response = client.put(f'/api/v1/customers/{customer["id"]}', headers=admin_headers, json=data)
    assert response.status_code == 200
    assert response.json()["username"] == customer["username"]
    with factory() as db:
        assert db.get(User, customer["user_id"]).email == "actualizado@example.com"
        assert db.scalar(select(func.count(Notification.id)).where(Notification.kind == "credentials")) == 1


def test_archiving_preserves_history_and_revokes_customer(client, admin_headers, work_order):
    order, customer, headers = work_order
    assert client.delete(f'/api/v1/customers/{customer["id"]}', headers=admin_headers).status_code == 409
    assert client.delete(f'/api/v1/vehicles/{order["vehicle_id"]}', headers=admin_headers).status_code == 409
    catalog = client.get("/api/v1/catalogs", headers=admin_headers).json()[0]
    assert client.delete(f'/api/v1/catalogs/{catalog["id"]}', headers=admin_headers).status_code == 200
    assert client.get("/api/v1/catalogs", headers=admin_headers).json() == []
    assert client.get(f'/api/v1/orders/{order["id"]}', headers=headers).json()["title"] == order["title"]
    assert client.patch(f'/api/v1/orders/{order["id"]}/status?status=cancelled', headers=admin_headers).status_code == 200
    assert client.delete(f'/api/v1/vehicles/{order["vehicle_id"]}', headers=admin_headers).status_code == 200
    assert client.get("/api/v1/vehicles", headers=admin_headers).json() == []
    assert client.delete(f'/api/v1/customers/{customer["id"]}', headers=admin_headers).status_code == 200
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401
    assert client.get(f'/api/v1/orders/{order["id"]}', headers=admin_headers).status_code == 200


def test_reset_credentials_invalidates_previous_outbox_and_session(client, admin_headers, make_customer, factory):
    customer, headers = make_customer()
    assert client.post(f'/api/v1/customers/{customer["id"]}/credentials', headers=admin_headers).status_code == 200
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401
    with factory() as db:
        rows = list(db.scalars(select(Notification).where(Notification.user_id == customer["user_id"]).order_by(Notification.id)))
        assert rows[0].status == "failed" and rows[0].encrypted_payload is None
        assert rows[1].status == "pending" and rows[1].encrypted_payload is not None


def test_expired_credentials_are_erased(client, admin_headers, make_customer, factory):
    make_customer()
    with factory.begin() as db:
        row = db.scalar(select(Notification))
        row.created_at = utcnow() - timedelta(hours=25)
    assert asyncio.run(notifications.process_one()) is False
    with factory() as db:
        row = db.scalar(select(Notification))
        assert row.encrypted_payload is None
        assert row.status == "failed"


def test_logo_rejects_script_and_accepts_valid_base64(client, admin_headers):
    import base64
    payload = config_payload(client)
    for logo in ("javascript:alert(1)", "http://unsafe.example.com/logo.png", "data:image/svg+xml;base64,PHN2Zz4="):
        payload["branding"]["logo"] = logo
        assert client.put("/api/v1/config/global", headers=admin_headers, json=payload).status_code == 422
    buffer = BytesIO()
    Image.new("RGB", (32, 32), "blue").save(buffer, format="PNG")
    payload["branding"]["logo"] = "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()
    assert client.put("/api/v1/config/global", headers=admin_headers, json=payload).status_code == 200
