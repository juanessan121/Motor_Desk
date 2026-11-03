import json
from pathlib import Path
import pytest
from sqlalchemy import select

from app.models import Customer, MaintenanceActivity, Notification, User, Vehicle, WorkOrder
from app.serializers import customer_access_status


def test_activity_catalog_crud(client, admin_headers):
    # 1. Crear actividad
    resp = client.post("/api/v1/activities", headers=admin_headers, json={
        "label": "Cambio de aceite de motor sintético",
        "system": "motor",
        "description": "Drenar aceite usado y colocar filtro nuevo",
        "estimated_minutes": 45,
        "technical_notes": "Usar especificación 5W-30",
    })
    assert resp.status_code == 201, resp.text
    act = resp.json()
    act_id = act["id"]
    assert act["name"] == "Cambio de aceite de motor sintético"
    assert act["system"] == "motor"
    assert act["estimated_minutes"] == 45

    # 2. Listar actividades
    list_resp = client.get("/api/v1/activities", headers=admin_headers)
    assert list_resp.status_code == 200
    items = list_resp.json()
    assert any(item["id"] == act_id for item in items)

    # 3. Filtrar por sistema
    filter_resp = client.get("/api/v1/activities?system=motor", headers=admin_headers)
    assert filter_resp.status_code == 200
    assert all(item["system"] == "motor" for item in filter_resp.json())

    # 4. Modificar actividad
    edit_resp = client.put(f"/api/v1/activities/{act_id}", headers=admin_headers, json={
        "label": "Cambio de aceite y filtro sintético",
        "system": "motor",
        "description": "Actualizado",
        "estimated_minutes": 50,
        "technical_notes": "Verificar nivel final",
    })
    assert edit_resp.status_code == 200
    assert edit_resp.json()["name"] == "Cambio de aceite y filtro sintético"

    # 5. Desactivar / Eliminar
    del_resp = client.delete(f"/api/v1/activities/{act_id}", headers=admin_headers)
    assert del_resp.status_code == 200
    assert del_resp.json()["active"] is False


def test_customer_portal_access_flows(client, admin_headers, factory):
    # 1. Cliente sin acceso al portal
    resp_no_portal = client.post("/api/v1/customers", headers=admin_headers, json={
        "national_id": "1720000001",
        "first_name": "Juan",
        "last_name": "SinPortal",
        "email": "juan.sinportal@example.com",
        "phone": "0991112233",
        "whatsapp": "+593991112233",
        "has_portal_access": False,
    })
    assert resp_no_portal.status_code == 201, resp_no_portal.text
    c_no_portal = resp_no_portal.json()
    assert c_no_portal["user_id"] is None
    assert c_no_portal["access_status"] == "sin_cuenta"
    assert c_no_portal["whatsapp"] == "+593991112233"

    # 2. Habilitar acceso posteriormente
    enable_resp = client.post(f"/api/v1/customers/{c_no_portal['id']}/enable-access", headers=admin_headers)
    assert enable_resp.status_code == 200, enable_resp.text
    assert enable_resp.json()["access_status"] in ("pendiente_activacion", "activo")
    raw_token = enable_resp.json().get("activation_token")
    assert raw_token is not None

    # 3. Activar cuenta con contraseña segura mediante token
    activate_resp = client.post("/api/v1/auth/activate", json={
        "token": raw_token,
        "password": "PasswordSegura123!",
    })
    assert activate_resp.status_code == 200, activate_resp.text

    # 4. Iniciar sesión con la cuenta activada
    import uuid
    login_resp = client.post("/api/v1/auth/login", headers={"X-Device-Id": str(uuid.uuid4())}, json={
        "username": enable_resp.json()["username"],
        "password": "PasswordSegura123!",
    })
    assert login_resp.status_code == 200, login_resp.text
    assert "access_token" in login_resp.json()


def test_notifications_recipient_management_and_channels(client, admin_headers, make_customer):
    customer, _ = make_customer("notif1")

    # 1. Listar destinatarios desde módulo de notificaciones
    recipients_resp = client.get("/api/v1/notifications/recipients", headers=admin_headers)
    assert recipients_resp.status_code == 200
    recipients = recipients_resp.json()
    matching = next((r for r in recipients if r["id"] == customer["id"]), None)
    assert matching is not None

    # 2. Editar contacto y canales directamente desde notificaciones
    patch_resp = client.patch(f"/api/v1/notifications/recipients/{customer['id']}", headers=admin_headers, json={
        "email": "nuevo_correo_notif@example.com",
        "notification_channel": "whatsapp",
        "whatsapp": "+593987654321",
        "telegram_chat_id": "123456789",
        "email_notifications_enabled": True,
        "telegram_notifications_enabled": True,
        "whatsapp_notifications_enabled": True,
    })
    assert patch_resp.status_code == 200, patch_resp.text
    data = patch_resp.json()
    assert data["email"] == "nuevo_correo_notif@example.com"
    assert data["whatsapp"] == "+593987654321"
    assert data["telegram_notifications_enabled"] is True
    assert data["whatsapp_notifications_enabled"] is True

    # 3. Eliminar canal individual sin afectar otros datos
    del_chan_resp = client.delete(f"/api/v1/notifications/recipients/{customer['id']}/channel/telegram", headers=admin_headers)
    assert del_chan_resp.status_code == 200
    assert del_chan_resp.json()["telegram_notifications_enabled"] is False
    assert del_chan_resp.json()["telegram_chat_id"] is None


def test_order_creation_with_hybrid_checklist_and_tax(client, admin_headers, make_customer):
    customer, _ = make_customer("hybrid")
    v_resp = client.post("/api/v1/vehicles", headers=admin_headers, json={
        "owner_id": customer["id"],
        "plate": "HYB-1234",
        "brand": "Chevrolet",
        "model": "D-Max",
        "year": 2022,
        "color": "Blanco Polar",
        "fuel_type": "diesel",
        "mileage": 30000,
    })
    assert v_resp.status_code == 201
    vehicle = v_resp.json()
    assert vehicle["color"] == "Blanco Polar"
    assert vehicle["fuel_type"] == "diesel"

    cat_resp = client.post("/api/v1/catalogs", headers=admin_headers, json={
        "name": "Mantenimiento 30.000 km",
        "base_price": "120.00",
        "tasks": ["Cambio aceite motor", "Filtro combustible", "Revisión frenos"],
    })
    assert cat_resp.status_code == 201
    catalog = cat_resp.json()

    # Crear orden seleccionando solo un subconjunto de tareas del checklist
    order_resp = client.post("/api/v1/orders", headers=admin_headers, json={
        "vehicle_id": vehicle["id"],
        "catalog_id": catalog["id"],
        "maintenance_type": "preventivo",
        "problem_description": "Mantenimiento preventivo periódico",
        "technical_diagnosis": "Vehículo en buen estado general",
        "included_tasks": ["Cambio aceite motor", "Filtro combustible"],
        "labor_cost": 120.00,
        "parts_cost": 50.00,
    })
    assert order_resp.status_code == 201, order_resp.text
    order = order_resp.json()
    assert order["order_code"].startswith(("OT-", "ORD-"))
    assert float(order["labor_cost"]) == 120.00
    assert float(order["parts_cost"]) == 50.00
    assert order["tax_rate"] == "0.15"
    assert float(order["tax_amount"]) == round((120.00 + 50.00) * 0.15, 2)
    assert len(order["items"]) == 2
    item_labels = [i["label"] for i in order["items"]]
    assert "Cambio aceite motor" in item_labels
    assert "Filtro combustible" in item_labels
    assert "Revisión frenos" not in item_labels


def test_export_workshop_data_and_schema_conformance(client, admin_headers):
    resp = client.get("/api/v1/export/workshop-data", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    payload = resp.json()

    # Validar presencia de las 5 fases
    assert "metadatos" in payload
    assert "clientes" in payload
    assert "vehiculos" in payload
    assert "mantenimientos" in payload
    assert "seguimiento_estados" in payload
    assert "notificaciones" in payload

    # Validar contra esquema oficial JSON Schema Draft-07
    schema_path = Path(__file__).resolve().parent.parent.parent / "docs" / "motordesk_workshop_schema.json"
    assert schema_path.exists(), "El esquema JSON Schema debe existir en docs/motordesk_workshop_schema.json"
    with open(schema_path, "r", encoding="utf-8") as f:
        schema = json.load(f)

    import jsonschema
    jsonschema.validate(instance=payload, schema=schema)
