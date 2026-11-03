from io import BytesIO

import pytest
from PIL import Image
from sqlalchemy import select

from app.models import AuditEvent, BayOccupancy, User, Vehicle, WorkAssignment, Workshop
from app.security import issue_token, password_hasher


@pytest.fixture
def make_mechanic(factory):
    def make(name="mech-a", workshop_id=1):
        with factory.begin() as db:
            user = User(username=name, email=name + "@example.com", password_hash=password_hasher.hash("test-mechanic-secret"), role="mechanic", workshop_id=workshop_id, must_change_password=False)
            db.add(user)
            db.flush()
            return user.id, {"Authorization": "Bearer " + issue_token(user)}
    return make


def assign(client, admin, order, mechanic, task_ids=None, can_quote=False):
    response = client.post(f'/api/v1/orders/{order["id"]}/assignments', headers=admin, json={
        "mechanic_id": mechanic, "task_ids": task_ids or [order["items"][0]["id"]], "can_quote": can_quote,
    })
    assert response.status_code == 201, response.text
    return response.json()


def inspection(client, headers, order, task_id=None):
    result = client.post('/api/v1/inspections', headers=headers, json={"order_id": order["id"], "task_id": task_id, "title": "Inspección documentada"})
    assert result.status_code == 201, result.text
    return result.json()


def finding_payload(revision, **overrides):
    return {"expected_revision": revision, "component_id": "carroceria", "view_id": "inspection_side", "x": .24, "y": .71,
        "condition": "issue", "category": "rayón", "severity": "minor", "note": "Rayón observado y registrado por el técnico", **overrides}


def second_order(client, admin, make_customer, suffix="2"):
    customer, headers = make_customer(suffix)
    vehicle = client.post('/api/v1/vehicles', headers=admin, json={"owner_id": customer["id"], "plate": "SECOND-" + suffix, "brand": "Marca de prueba", "model": "Modelo de prueba", "year": 2023}).json()
    catalog = client.get('/api/v1/catalogs', headers=admin).json()[0]
    order = client.post('/api/v1/orders', headers=admin, json={"vehicle_id": vehicle["id"], "catalog_id": catalog["id"]})
    assert order.status_code == 201, order.text
    return order.json(), headers


def test_mechanic_without_assignments_is_fail_closed(client, admin_headers, work_order, make_mechanic):
    order, _, _ = work_order
    _, headers = make_mechanic()
    assert client.get('/api/v1/orders', headers=headers).json() == []
    assert client.get('/api/v1/vehicles', headers=headers).json() == []
    assert client.get('/api/v1/customers', headers=headers).status_code == 403
    assert client.get('/api/v1/catalogs', headers=headers).status_code == 403
    assert client.get('/api/v1/notification-settings', headers=headers).status_code == 403
    assert client.get(f'/api/v1/orders/{order["id"]}', headers=headers).status_code == 404
    assert client.get(f'/api/v1/vehicles/{order["vehicle_id"]}/passport', headers=headers).status_code == 404
    assert client.get('/api/v1/workshop/layout', headers=headers).status_code == 403
    summary = client.get('/api/v1/dashboard', headers=headers).json()
    assert summary['assigned_orders'] == 0 and 'delivered_total' not in summary
    assert client.post('/api/v1/orders', headers=headers, json={"vehicle_id": order['vehicle_id'], "catalog_id": 1}).status_code == 403


def test_task_scope_revoke_and_audit_remain(client, admin_headers, work_order, make_mechanic, factory):
    order, _, customer = work_order
    assert client.post(f'/api/v1/orders/{order["id"]}/approval', headers=customer, json={'approved': True}).status_code == 200
    a, ha = make_mechanic()
    b, hb = make_mechanic('mech-b')
    grant = assign(client, admin_headers, order, a)
    assign(client, admin_headers, order, b, [order['items'][1]['id']])
    own = client.get(f'/api/v1/orders/{order["id"]}', headers=ha).json()
    assert len(own['items']) == 1
    assert all(key not in own for key in ('payer_snapshot', 'total', 'base_total', 'notes'))
    assert client.patch(f'/api/v1/orders/{order["id"]}/items/{order["items"][1]["id"]}', headers=ha, json={"completed": True}).status_code == 404
    assert client.patch(f'/api/v1/orders/{order["id"]}/items/{order["items"][0]["id"]}', headers=ha, json={"completed": True}).status_code == 200
    report = inspection(client, ha, order, order['items'][0]['id'])
    assert client.get(f'/api/v1/inspections/{report["id"]}', headers=hb).status_code == 404
    assert client.post(f'/api/v1/orders/{order["id"]}/quotes', headers=ha, json={"title": "Repuesto", "task_id": order['items'][0]['id'], "options": [{"label": "Original", "price": "10.00"}]}).status_code == 403
    assert client.delete(f'/api/v1/orders/{order["id"]}/assignments/{grant["id"]}', headers=admin_headers).status_code == 200
    assert client.get('/api/v1/orders', headers=ha).json() == []
    assert client.get('/api/v1/vehicles', headers=ha).json() == []
    assert client.get('/api/v1/notifications', headers=ha).json() == []
    assert client.get(f'/api/v1/inspections/{report["id"]}', headers=ha).status_code == 404
    assert client.get(f'/api/v1/vehicles/{order["vehicle_id"]}/history', headers=ha).status_code == 404
    with factory() as db:
        assert db.get(WorkAssignment, grant['id']).revoked_at is not None
        assert db.scalar(select(AuditEvent.id).where(AuditEvent.actor_id == a, AuditEvent.action == 'task.completed'))


def test_mechanic_a_cannot_get_b_resources_by_any_id(client, admin_headers, work_order, make_customer, make_mechanic):
    first, _, _ = work_order
    second, _ = second_order(client, admin_headers, make_customer)
    a, ha = make_mechanic()
    b, hb = make_mechanic('mech-b')
    assign(client, admin_headers, first, a)
    assign(client, admin_headers, second, b)
    report = inspection(client, hb, second, second['items'][0]['id'])
    for path in (f'/orders/{second["id"]}', f'/orders/{second["id"]}/inspections', f'/inspections/{report["id"]}', f'/vehicles/{second["vehicle_id"]}/passport', f'/vehicles/{second["vehicle_id"]}/history'):
        assert client.get('/api/v1' + path, headers=ha).status_code == 404, path
    assert len(client.get('/api/v1/orders?limit=1&offset=0', headers=ha).json()) == 1
    assert client.get('/api/v1/orders?limit=1&offset=1', headers=ha).json() == []
    assert client.get('/api/v1/vehicles?q=SECOND', headers=ha).json() == []
    assert client.post('/api/v1/inspections', headers=ha, json={"order_id": second['id'], "task_id": second['items'][0]['id'], "title": "Intento ajeno"}).status_code == 404


def test_inspection_versions_publication_and_unknown_state(client, admin_headers, work_order, make_mechanic):
    order, _, customer = work_order
    mid, mechanic = make_mechanic()
    assign(client, admin_headers, order, mid)
    report = inspection(client, mechanic, order, order['items'][0]['id'])
    path = f'/api/v1/inspections/{report["id"]}'
    assert client.get(path, headers=customer).status_code == 404
    response = client.post(path + '/findings', headers=mechanic, json=finding_payload(report['revision']))
    assert response.status_code == 201, response.text
    draft = response.json()
    saved = client.get(path, headers=mechanic).json()['findings'][0]
    assert saved['component_id'] == 'carroceria' and saved['view_id'] == 'inspection_side'
    assert saved['x'] == .24 and saved['y'] == .71
    assert client.post(path + '/findings', headers=mechanic, json=finding_payload(report['revision'])).status_code == 409
    passport = client.get(f'/api/v1/vehicles/{order["vehicle_id"]}/passport', headers=admin_headers).json()
    assert passport['component_states']['carroceria']['condition'] == 'no_data'
    assert client.post(path + '/review', headers=mechanic, json={"expected_revision": draft['revision']}).status_code == 403
    reviewed = client.post(path + '/review', headers=admin_headers, json={"expected_revision": draft['revision']}).json()
    published = client.post(path + '/publish', headers=admin_headers, json={"expected_revision": reviewed['revision'], "photo_ids": []})
    assert published.status_code == 200, published.text
    public = client.get(path, headers=customer).json()
    assert len(public['findings']) == 1
    changed = client.post(path + '/findings', headers=mechanic, json=finding_payload(published.json()['revision'], note='Borrador nuevo privado', condition='normal'))
    assert changed.status_code == 201, changed.text
    assert len(client.get(path, headers=customer).json()['findings']) == 1
    assert 'Borrador nuevo privado' not in client.get(path, headers=customer).text
    revisions = client.get(path + '/revisions', headers=admin_headers).json()
    assert len(revisions) == 5
    assert client.get(path + '/revisions', headers=mechanic).status_code == 403


def test_mechanic_evidence_internal_until_admin_publication(client, admin_headers, work_order, make_mechanic):
    order, _, customer = work_order
    mid, mechanic = make_mechanic()
    assign(client, admin_headers, order, mid)
    buffer = BytesIO()
    Image.new('RGB', (20, 20), 'gray').save(buffer, format='PNG')
    path = f'/api/v1/orders/{order["id"]}/photos'
    bad = client.post(path, headers=mechanic, files={"file": ('image.png', buffer.getvalue(), 'image/png')})
    assert bad.status_code == 404
    image = client.post(path, headers=mechanic, data={"task_id": order['items'][0]['id']}, files={"file": ('image.png', buffer.getvalue(), 'image/png')})
    assert image.status_code == 201, image.text
    file_path = path + '/' + str(image.json()['id'])
    assert client.get(file_path, headers=customer).status_code == 404
    assert client.post(file_path + '/publication', headers=mechanic, json={"published": True}).status_code == 403
    assert client.post(file_path + '/publication', headers=admin_headers, json={"published": True}).status_code == 200
    assert client.get(file_path, headers=customer).status_code == 200
    assert client.post(file_path + '/publication', headers=admin_headers, json={"published": False}).status_code == 200
    assert client.get(file_path, headers=customer).status_code == 404


def test_cross_workshop_ids_never_grant_access(client, admin_headers, work_order, factory):
    order, _, _ = work_order
    with factory.begin() as db:
        db.add(Workshop(id=2, name='Taller de prueba aislado'))
        db.flush()
        other = User(workshop_id=2, username='other-admin', email='other-admin@example.com', password_hash=password_hasher.hash('test-only-other-secret'), role='admin', must_change_password=False)
        db.add(other)
        db.flush()
        headers = {"Authorization": 'Bearer ' + issue_token(other)}
    assert client.get('/api/v1/orders', headers=headers).json() == []
    assert client.get('/api/v1/customers', headers=headers).json() == []
    assert client.get(f'/api/v1/orders/{order["id"]}', headers=headers).status_code == 404
    assert client.get(f'/api/v1/vehicles/{order["vehicle_id"]}/passport', headers=headers).status_code == 404
    assert client.get('/api/v1/config/users/1', headers=headers).status_code == 404


def create_layout(client, admin, capacity=1):
    zone = client.post('/api/v1/workshop/zones', headers=admin, json={"name": 'Zona real de prueba', "kind": 'service', "capacity": capacity, "x": 0, "y": 0, "width": 1, "height": 1})
    assert zone.status_code == 201, zone.text
    body = {"zone_id": zone.json()['id'], "name": 'Bahía configurada', "kind": 'mechanical', "capacity": capacity, "x": .1, "y": .1, "width": .4, "height": .7}
    bay = client.post('/api/v1/workshop/bays', headers=admin, json=body)
    assert bay.status_code == 201, bay.text
    return zone.json(), bay.json(), body


def test_layout_is_empty_until_configured_and_movements_do_not_change_order(client, admin_headers, work_order, make_customer):
    order, _, _ = work_order
    second, _ = second_order(client, admin_headers, make_customer)
    assert client.get('/api/v1/workshop/layout', headers=admin_headers).json()['configured'] is False
    _, bay, _ = create_layout(client, admin_headers)
    path = f'/api/v1/orders/{order["id"]}/location'
    first = client.post(path, headers=admin_headers, json={"bay_id": bay['id'], "reason": 'Ingreso documentado', "expected_occupancy_id": None})
    assert first.status_code == 200, first.text
    assert first.json()['order_status'] == 'in_progress'
    assert client.post(f'/api/v1/orders/{second["id"]}/location', headers=admin_headers, json={"bay_id": bay['id'], "reason": 'Intento de ingreso'}).status_code == 409
    assert client.post(path, headers=admin_headers, json={"bay_id": None, "reason": 'Salida documentada'}).status_code == 409
    released = client.post(path, headers=admin_headers, json={"bay_id": None, "reason": 'Salida documentada', "expected_occupancy_id": first.json()['location']['id']})
    assert released.status_code == 200
    history = client.get(f'/api/v1/orders/{order["id"]}/locations', headers=admin_headers).json()
    assert len(history) == 1 and history[0]['exited_at'] is not None


def test_closed_order_never_repairs_a_component(client, admin_headers, work_order):
    order, _, customer = work_order
    assert client.post(f'/api/v1/orders/{order["id"]}/approval', headers=customer, json={'approved': True}).status_code == 200
    report = inspection(client, admin_headers, order)
    result = client.post(f'/api/v1/inspections/{report["id"]}/findings', headers=admin_headers, json=finding_payload(report['revision'])).json()
    client.post(f'/api/v1/inspections/{report["id"]}/review', headers=admin_headers, json={"expected_revision": result['revision']})
    for item in order['items']:
        assert client.patch(f'/api/v1/orders/{order["id"]}/items/{item["id"]}', headers=admin_headers, json={"completed": True}).status_code == 200
    current = client.get(f'/api/v1/orders/{order["id"]}', headers=admin_headers).json()
    assert client.post(f'/api/v1/orders/{order["id"]}/execution-review', headers=admin_headers,
                       json={'expected_revision': current['revision'], 'note': 'Revisión administrativa final'}).status_code == 200
    assert client.patch(f'/api/v1/orders/{order["id"]}/status?status=delivered', headers=admin_headers).status_code == 200
    passport = client.get(f'/api/v1/vehicles/{order["vehicle_id"]}/passport', headers=admin_headers).json()
    assert passport['component_states']['carroceria']['condition'] == 'issue'


def test_mechanic_payload_carries_no_customer_or_vehicle_identifiers(client, admin_headers, work_order, make_mechanic, factory):
    order, _, _ = work_order
    with factory.begin() as db:
        db.get(Vehicle, order["vehicle_id"]).vin = "TESTVIN0000000001"
    a, ha = make_mechanic()
    assign(client, admin_headers, order, a)
    mine = client.get(f'/api/v1/orders/{order["id"]}', headers=ha).json()
    for key in ("payer_snapshot", "total", "base_total", "notes", "customer_id"):
        assert key not in mine, key
    assert mine["customer_name"] is None
    assert mine["capabilities"] == {"manage": False, "assign": False, "inspect": True, "upload": True, "quote": False}
    vehicle = next(row for row in client.get('/api/v1/vehicles', headers=ha).json() if row['id'] == order['vehicle_id'])
    assert vehicle['vin'] is None and vehicle['owner_name'] is None
    admin_vehicle = next(row for row in client.get('/api/v1/vehicles', headers=admin_headers).json() if row['id'] == order['vehicle_id'])
    assert admin_vehicle['vin'] and admin_vehicle['owner_name']
    admin_order = client.get(f'/api/v1/orders/{order["id"]}', headers=admin_headers).json()
    assert admin_order["customer_id"] == order["customer_id"] and admin_order["total"] is not None


def test_mechanic_cannot_reach_admin_only_operations(client, admin_headers, work_order, make_mechanic):
    order, _, customer = work_order
    assert client.post(f'/api/v1/orders/{order["id"]}/approval', headers=customer, json={'approved': True}).status_code == 200
    a, ha = make_mechanic()
    assign(client, admin_headers, order, a)
    _, bay, _ = create_layout(client, admin_headers)
    for method, path, body in (
        ("patch", f'/api/v1/orders/{order["id"]}/status?status=delivered', None),
        ("patch", f'/api/v1/orders/{order["id"]}/status?status=cancelled', None),
        ("post", f'/api/v1/orders/{order["id"]}/location', {"bay_id": bay['id'], "reason": 'intento'}),
        ("post", f'/api/v1/orders/{order["id"]}/photos/1/publication', {"published": True}),
    ):
        response = getattr(client, method)(path, headers=ha, json=body) if body else getattr(client, method)(path, headers=ha)
        assert response.status_code == 403, f'{method.upper()} {path} -> {response.status_code}'
    assert client.get(f'/api/v1/orders/{order["id"]}/locations', headers=ha).status_code == 403
    assert client.get(f'/api/v1/orders/{order["id"]}/audit', headers=ha).status_code == 403
    assert client.get('/api/v1/staff/mechanics', headers=ha).status_code == 403
    assert client.get('/api/v1/devices', headers=ha).status_code == 403
    assert client.post(f'/api/v1/orders/{order["id"]}/quotes/{order["id"]}/decision',
        headers=ha, json={"option_id": 1, "decision": "approved"}).status_code == 403
    # Cancelar o entregar sigue siendo denegado aunque el trabajo esté completo.
    for item in order['items']:
        client.patch(f'/api/v1/orders/{order["id"]}/items/{item["id"]}', headers=admin_headers, json={"completed": True})
    assert client.patch(f'/api/v1/orders/{order["id"]}/status?status=delivered', headers=ha).status_code == 403
    current = client.get(f'/api/v1/orders/{order["id"]}', headers=admin_headers).json()
    assert current['status'] == 'in_progress' and current['operational_stage'] == 'pending_review'
