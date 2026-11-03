from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.catalog_models import VehiclePart
from app.models import AuditEvent, MaintenanceCatalog, StockItem, StockMovement, User, WorkOrder, Workshop
from app.security import issue_token


@pytest.fixture
def mechanic(factory):
    with factory.begin() as db:
        user = User(workshop_id=1, username='mantenimiento-mecanico', email='mantenimiento@example.test',
                    password_hash='test-only', role='mechanic', must_change_password=False)
        db.add(user); db.flush()
        return user.id, {'Authorization': 'Bearer ' + issue_token(user)}


@pytest.fixture
def part(factory):
    with factory.begin() as db:
        row = VehiclePart(sku='PRUEBA-FLUJO', title='Repuesto de prueba sin compatibilidad inferida')
        db.add(row); db.flush()
        return row.id


def accept(client, order, customer):
    result = client.post(f"/api/v1/orders/{order['id']}/approval", headers=customer, json={'approved': True})
    assert result.status_code == 200, result.text


def detail(client, order, admin):
    return client.get(f"/api/v1/orders/{order['id']}", headers=admin).json()


def update_task(client, order, task, admin, status, notes=None):
    response = client.patch(f"/api/v1/orders/{order['id']}/items/{task['id']}", headers=admin,
        json={'status': status, 'expected_revision': task['revision'], **({'notes': notes} if notes is not None else {})})
    assert response.status_code == 200, response.text
    return response.json()


def complete_and_review(client, order, admin):
    for task in detail(client, order, admin)['items']:
        update_task(client, order, task, admin, 'completed')
    current = detail(client, order, admin)
    assert current['operational_stage'] == 'pending_review'
    reviewed = client.post(f"/api/v1/orders/{order['id']}/execution-review", headers=admin,
        json={'expected_revision': current['revision'], 'note': 'Revisión final con evidencia de prueba'})
    assert reviewed.status_code == 200, reviewed.text
    return reviewed.json()


def test_initial_templates_are_configurable_not_manufacturer_claims(client, admin_headers, work_order):
    order, _, _ = work_order
    first = client.post('/api/v1/catalogs/reference', headers=admin_headers)
    assert first.status_code == 200, first.text
    assert len(first.json()['created_ids']) == 8
    assert client.post('/api/v1/catalogs/reference', headers=admin_headers).json()['created_ids'] == []
    catalogs = client.get('/api/v1/catalogs', headers=admin_headers).json()
    basic = next(row for row in catalogs if row['name'] == 'Mantenimiento preventivo básico')
    assert len(basic['tasks']) == 8 and not basic['price_configured']
    assert {row['interval_km'] for row in catalogs if row['interval_km']} == {5000, 10000, 20000}
    for row in catalogs:
        if row['interval_km']:
            assert 'verificar' in row['schedule_source'].lower()
    # La comprobación de precio se hace en el servidor, no solo en el formulario.
    assert client.patch(f"/api/v1/orders/{order['id']}/status?status=cancelled", headers=admin_headers).status_code == 200
    assert client.post('/api/v1/orders', headers=admin_headers, json={'vehicle_id': order['vehicle_id'], 'catalog_id': basic['id']}).status_code == 409


def test_a_basic_eight_activity_service_end_to_end(client, admin_headers, work_order, mechanic):
    previous, _, customer = work_order
    assert client.patch(f"/api/v1/orders/{previous['id']}/status?status=cancelled", headers=admin_headers).status_code == 200
    client.post('/api/v1/catalogs/reference', headers=admin_headers)
    basic = next(row for row in client.get('/api/v1/catalogs', headers=admin_headers).json()
                 if row['name'] == 'Mantenimiento preventivo básico')
    configured = client.put(f"/api/v1/catalogs/{basic['id']}", headers=admin_headers, json={
        'name': basic['name'], 'description': basic['description'], 'base_price': '25.50', 'price_configured': True,
        'tasks': basic['task_details'], 'expected_revision': basic['revision'],
    })
    assert configured.status_code == 200, configured.text
    created = client.post('/api/v1/orders', headers=admin_headers, json={
        'vehicle_id': previous['vehicle_id'], 'catalog_id': basic['id'], 'mechanic_id': mechanic[0],
        'mileage': 50000, 'symptoms': 'Preventivo solicitado y especificaciones por comprobar', 'request_key': str(uuid4()),
    })
    assert created.status_code == 201, created.text
    order = created.json()
    assert len(order['items']) == 8 and order['templates'][0]['revision'] == 2
    accept(client, order, customer)
    current = detail(client, order, mechanic[1])
    assert current['operational_stage'] == 'assigned' and len(current['items']) == 8
    for index in range(8):
        current = update_task(client, order, current['items'][index], mechanic[1], 'completed')
        assert current['progress'] == round((index + 1) / 8, 4)
    assert current['operational_stage'] == 'pending_review' and current['status'] == 'in_progress'
    full = detail(client, order, admin_headers)
    reviewed = client.post(f"/api/v1/orders/{order['id']}/execution-review", headers=admin_headers,
        json={'expected_revision': full['revision'], 'note': 'Ocho actividades comprobadas por administración'})
    assert reviewed.status_code == 200 and reviewed.json()['status'] == 'ready', reviewed.text
    delivered = client.patch(f"/api/v1/orders/{order['id']}/status?status=delivered", headers=admin_headers)
    assert delivered.status_code == 200
    history = client.get(f"/api/v1/vehicles/{order['vehicle_id']}/history", headers=customer).json()[0]
    assert len(history['checklist']) == 8 and history['intake_mileage'] == 50000
    assert history['templates'][0]['revision'] == 2


def test_a_multiservice_receipt_snapshot_assignment_and_retry(client, admin_headers, work_order, mechanic, factory):
    old, _, _ = work_order
    assert client.patch(f"/api/v1/orders/{old['id']}/status?status=cancelled", headers=admin_headers).status_code == 200
    second = client.post('/api/v1/catalogs', headers=admin_headers, json={'name': 'Servicio complementario', 'base_price': '12.50',
        'tasks': [{'label': 'Comprobar con el fabricante', 'required': False, 'estimated_minutes': 15}]}).json()
    catalog_id = client.get('/api/v1/catalogs', headers=admin_headers).json()[1]['id']
    body = {'vehicle_id': old['vehicle_id'], 'catalog_ids': [catalog_id, second['id']], 'mileage': 51000,
            'mechanic_id': mechanic[0], 'request_key': str(uuid4()), 'symptoms': 'Síntoma técnico documentado', 'priority': 'urgent'}
    result = client.post('/api/v1/orders', headers=admin_headers, json=body)
    assert result.status_code == 201, result.text
    order = result.json()
    assert len(order['items']) == 3 and len(order['templates']) == 2
    assert order['intake_mileage'] == 51000 and order['total'] == '129.49'
    replay = client.post('/api/v1/orders', headers=admin_headers, json=body)
    assert replay.status_code == 201 and replay.json()['id'] == order['id']
    assert client.post('/api/v1/orders', headers=admin_headers, json={**body, 'symptoms': 'Otro contenido'}).status_code == 409
    mine = client.get('/api/v1/orders', headers=mechanic[1]).json()[0]
    assert len(mine['items']) == 3 and mine['symptoms'] == body['symptoms']
    assert all('base_price' not in template for template in mine['templates'])
    with factory() as db:
        assert db.scalar(select(func.count(WorkOrder.id))) == 2


def test_b_checklist_exemptions_attention_and_final_review(client, admin_headers, work_order, mechanic):
    order, _, customer = work_order
    task = order['items'][0]
    path = f"/api/v1/orders/{order['id']}/items/{task['id']}"
    assert client.patch(path, headers=admin_headers, json={'status': 'completed', 'expected_revision': task['revision']}).status_code == 409
    assert client.post(f"/api/v1/orders/{order['id']}/assignments", headers=admin_headers,
        json={'mechanic_id': mechanic[0], 'task_ids': [item['id'] for item in order['items']]}).status_code == 201
    accept(client, order, customer)
    assert client.patch(path, headers=mechanic[1], json={'status': 'not_applicable', 'notes': 'No aplica al motor', 'expected_revision': task['revision']}).status_code == 403
    current = update_task(client, order, task, admin_headers, 'in_progress')
    assert current['operational_stage'] == 'in_progress'
    assert client.patch(path, headers=admin_headers, json={'status': 'completed', 'expected_revision': task['revision']}).status_code == 409
    task = current['items'][0]
    assert client.patch(path, headers=admin_headers, json={'status': 'attention', 'expected_revision': task['revision']}).status_code == 422
    current = update_task(client, order, task, admin_headers, 'attention', 'Hallazgo pendiente de resolver')
    assert current['progress'] == 0 and current['status'] != 'ready'
    current = update_task(client, order, current['items'][0], admin_headers, 'not_applicable', 'Excluida por condición confirmada del fabricante')
    current = update_task(client, order, current['items'][1], mechanic[1], 'completed')
    assert current['progress'] == 1 and current['operational_stage'] == 'pending_review'
    assert client.patch(f"/api/v1/orders/{order['id']}/status?status=delivered", headers=admin_headers).status_code == 409
    assert client.post(f"/api/v1/orders/{order['id']}/execution-review", headers=mechanic[1], json={'expected_revision': current['revision'], 'note': 'Intento no autorizado'}).status_code == 403
    original = client.get('/api/v1/catalogs', headers=admin_headers).json()[0]
    assert len(original['tasks']) == 2


def test_d_history_preserves_version_observations_and_extra_tasks(client, admin_headers, work_order, factory):
    order, _, customer = work_order
    accept(client, order, customer)
    added = client.post(f"/api/v1/orders/{order['id']}/items", headers=admin_headers, json={'label': 'Comprobación extraordinaria', 'reason': 'Hallazgo de recepción sin cargo adicional'})
    assert added.status_code == 201, added.text
    before = added.json()['templates']
    catalog = client.get('/api/v1/catalogs', headers=admin_headers).json()[0]
    edited = client.put(f"/api/v1/catalogs/{catalog['id']}", headers=admin_headers,
        json={'name': 'Plantilla nueva', 'base_price': '300.00', 'tasks': ['Actividad futura'], 'expected_revision': catalog['revision']})
    assert edited.status_code == 200, edited.text
    assert client.put(f"/api/v1/catalogs/{catalog['id']}", headers=admin_headers,
        json={'name': 'Edición obsoleta', 'base_price': '1.00', 'tasks': ['Otra'], 'expected_revision': catalog['revision']}).status_code == 409
    versions = client.get(f"/api/v1/catalogs/{catalog['id']}/versions", headers=admin_headers).json()
    assert len(versions) == 2 and versions[-1]['snapshot']['tasks'][0]['label'] == 'Aceite'
    ready = complete_and_review(client, order, admin_headers)
    assert ready['status'] == 'ready' and ready['templates'] == before
    assert ready['base_total'] == '100.10' and len(ready['items']) == 3
    assert client.patch(f"/api/v1/orders/{order['id']}/status?status=delivered", headers=admin_headers).status_code == 200
    assert client.patch(f"/api/v1/orders/{order['id']}/items/{ready['items'][0]['id']}", headers=admin_headers, json={'completed': False}).status_code == 409
    saved = detail(client, order, admin_headers)
    assert saved['items'][-1]['notes'] == 'Hallazgo de recepción sin cargo adicional'
    assert saved['items'][-1]['completed_by'] == 1
    assert saved['templates'] == before


def test_kilometre_suggestion_uses_delivered_history_and_unknowns(client, admin_headers, work_order):
    order, _, customer = work_order
    catalog = client.get('/api/v1/catalogs', headers=admin_headers).json()[0]
    updated = client.put(f"/api/v1/catalogs/{catalog['id']}", headers=admin_headers, json={
        'name': catalog['name'], 'base_price': catalog['base_price'], 'tasks': catalog['tasks'],
        'interval_km': 5000, 'schedule_source': 'Intervalo configurado para prueba; no universal',
    })
    assert updated.status_code == 200
    accept(client, order, customer)
    complete_and_review(client, order, admin_headers)
    client.patch(f"/api/v1/orders/{order['id']}/status?status=delivered", headers=admin_headers)
    path = f"/api/v1/vehicles/{order['vehicle_id']}/maintenance-suggestions"
    before = client.get(path + '?mileage=54999', headers=admin_headers).json()['items'][0]
    due = client.get(path + '?mileage=55000', headers=admin_headers).json()['items'][0]
    assert before['due_at_km'] == 55000 and not before['due'] and due['due']
    assert due['basis'] == 'historial_entregado' and due['applicability_status'] == 'unverified'
    assert client.get(path + '?mileage=1000', headers=admin_headers).status_code == 422


def test_c_f_parts_authorization_stock_idempotence_and_permissions(client, admin_headers, work_order, mechanic, part, factory):
    order, _, customer = work_order
    accept(client, order, customer)
    client.post(f"/api/v1/orders/{order['id']}/assignments", headers=admin_headers,
        json={'mechanic_id': mechanic[0], 'task_ids': [order['items'][0]['id']]})
    path = f"/api/v1/orders/{order['id']}/part-requests"
    body = {'task_id': order['items'][0]['id'], 'part_id': part, 'description': 'Repuesto documentado', 'quantity': '2.000',
            'unit': 'unidad', 'reason': 'Hallazgo técnico durante el mantenimiento', 'request_key': str(uuid4())}
    requested = client.post(path, headers=mechanic[1], json=body)
    assert requested.status_code == 201, requested.text
    row = requested.json()
    assert client.post(path, headers=mechanic[1], json=body).json()['id'] == row['id']
    assert client.post(path, headers=mechanic[1], json={**body, 'quantity': '3'}).status_code == 409
    assert detail(client, order, admin_headers)['operational_stage'] == 'waiting'
    assert client.get('/api/v1/stock', headers=mechanic[1]).status_code == 403
    resolution = {'expected_revision': row['revision'], 'decision': 'approve', 'authorization_basis': 'included_base', 'note': 'Incluido en el servicio que el cliente ya aceptó'}
    assert client.post(path + f"/{row['id']}/resolution", headers=mechanic[1], json=resolution).status_code == 403
    approved = client.post(path + f"/{row['id']}/resolution", headers=admin_headers, json=resolution)
    assert approved.status_code == 200, approved.text
    issue_path = path + f"/{row['id']}/issue"
    assert client.post(issue_path, headers=admin_headers, json={'expected_revision': approved.json()['revision']}).status_code == 409
    receipt = {'part_id': part, 'quantity': '3', 'unit': 'unidad', 'reason': 'Entrada física de prueba verificada', 'request_key': str(uuid4())}
    first = client.post('/api/v1/stock/receipts', headers=admin_headers, json=receipt)
    assert first.status_code == 201, first.text
    assert client.post('/api/v1/stock/receipts', headers=admin_headers, json=receipt).json()['movement_id'] == first.json()['movement_id']
    issued = client.post(issue_path, headers=admin_headers, json={'expected_revision': approved.json()['revision']})
    assert issued.status_code == 200 and issued.json()['status'] == 'issued', issued.text
    assert client.post(issue_path, headers=admin_headers, json={'expected_revision': approved.json()['revision']}).status_code == 200
    with factory() as db:
        assert db.scalar(select(StockItem.quantity)) == Decimal('1.000')
        assert db.scalar(select(func.count(StockMovement.id))) == 2
    # El cliente no puede consultar solicitudes internas ni ejecutar entregas.
    assert client.get(path, headers=customer).status_code == 403
    assert client.post(path, headers=mechanic[1], json={**body, 'request_key': str(uuid4()), 'task_id': order['items'][1]['id']}).status_code == 404


def test_extra_cost_requires_client_quote_not_mechanic_or_admin_decision(client, admin_headers, work_order, part):
    order, _, customer = work_order
    accept(client, order, customer)
    path = f"/api/v1/orders/{order['id']}/part-requests"
    row = client.post(path, headers=admin_headers, json={'task_id': order['items'][0]['id'], 'part_id': part,
        'description': 'Repuesto adicional', 'quantity': '1', 'reason': 'Costo fuera del servicio base', 'request_key': str(uuid4())}).json()
    payload = {'expected_revision': row['revision'], 'decision': 'approve', 'authorization_basis': 'approved_quote', 'note': 'Requiere gasto adicional'}
    assert client.post(path + f"/{row['id']}/resolution", headers=admin_headers, json=payload).status_code == 409
    quoted = client.post(f"/api/v1/orders/{order['id']}/quotes", headers=admin_headers,
        json={'task_id': order['items'][0]['id'], 'title': 'Adicional verificable', 'options': [{'label': 'Repuesto local', 'price': '20.00'}]}).json()['quotes'][0]
    quote_path = f"/api/v1/orders/{order['id']}/quotes/{quoted['id']}/decision"
    choice = {'decision': 'approved', 'option_id': quoted['options'][0]['id']}
    assert client.post(quote_path, headers=admin_headers, json=choice).status_code == 403
    assert client.post(quote_path, headers=customer, json=choice).status_code == 200
    assert client.post(path + f"/{row['id']}/resolution", headers=admin_headers, json={**payload, 'quote_id': quoted['id']}).status_code == 200


def test_optional_exemption_and_cross_workshop_stock(client, admin_headers, work_order, mechanic, factory):
    order, _, _ = work_order
    new = client.post(f"/api/v1/orders/{order['id']}/items", headers=admin_headers, json={'label': 'Actividad opcional', 'reason': 'Adaptación documentada'}).json()['items'][-1]
    from app.models import ChecklistItem
    with factory.begin() as db:
        db.get(ChecklistItem, new['id']).required = False
        db.add(Workshop(id=2, name='Otro taller'))
        db.flush()
        other = User(workshop_id=2, username='other-flow', email='other-flow@example.test', password_hash='test', role='admin', must_change_password=False)
        db.add(other); db.flush()
        other_headers = {'Authorization': 'Bearer ' + issue_token(other)}
    client.post(f"/api/v1/orders/{order['id']}/assignments", headers=admin_headers, json={'mechanic_id': mechanic[0], 'task_ids': [new['id']]})
    current = update_task(client, order, new, mechanic[1], 'not_applicable', 'No corresponde al vehículo confirmado')
    assert current['progress'] == 1  # Solo ve su actividad, excluida y conservada.
    assert client.get(f"/api/v1/orders/{order['id']}/part-requests", headers=other_headers).status_code == 404
    assert client.get('/api/v1/stock', headers=other_headers).json() == []


def test_simultaneous_issue_decrements_stock_only_once(client, admin_headers, work_order, part, factory):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    with factory() as db:
        if db.get_bind().dialect.name != 'postgresql':
            pytest.skip('La prueba de concurrencia necesita PostgreSQL real')
    order, _, customer = work_order
    accept(client, order, customer)
    path = f"/api/v1/orders/{order['id']}/part-requests"
    row = client.post(path, headers=admin_headers, json={'task_id': order['items'][0]['id'], 'part_id': part,
        'description': 'Repuesto para entrega concurrente', 'quantity': '1', 'reason': 'Prueba de exclusión transaccional', 'request_key': str(uuid4())}).json()
    approved = client.post(path + f"/{row['id']}/resolution", headers=admin_headers, json={
        'expected_revision': row['revision'], 'decision': 'approve', 'authorization_basis': 'included_base',
        'note': 'Incluido en el alcance base ya aceptado'}).json()
    assert client.post('/api/v1/stock/receipts', headers=admin_headers, json={'part_id': part, 'quantity': '2',
        'reason': 'Ingreso verificado de prueba', 'request_key': str(uuid4())}).status_code == 201
    barrier = Barrier(2)
    def send(_):
        barrier.wait(timeout=10)
        return client.post(path + f"/{row['id']}/issue", headers=admin_headers, json={'expected_revision': approved['revision']}).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(send, range(2))) == [200, 200]
    with factory() as db:
        assert db.scalar(select(StockItem.quantity)) == Decimal('1.000')
        assert db.scalar(select(func.count(StockMovement.id)).where(StockMovement.part_request_id == row['id'])) == 1
