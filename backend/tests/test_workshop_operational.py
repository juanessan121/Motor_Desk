import pytest
from sqlalchemy import select

from app.models import User, WorkshopBay, WorkshopZone
from app.security import issue_token


def template(client, admin):
    current = client.get('/api/v1/workshop/layout', headers=admin).json()
    result = client.post('/api/v1/workshop/layout/template', headers=admin,
                         json={'expected_revision': current['revision']})
    assert result.status_code == 201, result.text
    return result.json()


def test_template_is_explicit_atomic_and_not_reapplied(client, admin_headers, factory):
    before = client.get('/api/v1/workshop/layout', headers=admin_headers).json()
    assert not before['configured'] and not before['bays']
    saved = template(client, admin_headers)
    assert len(saved['zones']) == 1 and len(saved['bays']) == 6
    assert saved['zones'][0]['capacity'] == 6 and saved['orders'] == []
    again = client.post('/api/v1/workshop/layout/template', headers=admin_headers,
                        json={'expected_revision': saved['revision']})
    assert again.status_code == 409
    with factory() as db:
        assert len(list(db.scalars(select(WorkshopBay)))) == 6
        assert len(list(db.scalars(select(WorkshopZone)))) == 1
    assert len(client.get('/api/v1/workshop/layout', headers=admin_headers).json()['bays']) == 6


def test_moves_retain_concurrency_and_real_assignments(client, admin_headers, work_order, factory):
    order, _, _ = work_order
    plan = template(client, admin_headers)
    with factory.begin() as db:
        mech = User(username='responsable', email='responsable@example.test', role='mechanic', workshop_id=1,
                    must_change_password=False, password_hash='test-only')
        db.add(mech); db.flush()
        mech_id = mech.id
        mechanic_headers = {'Authorization': 'Bearer ' + issue_token(mech)}
    assigned = client.post(f"/api/v1/orders/{order['id']}/assignments", headers=admin_headers,
        json={'mechanic_id': mech_id, 'task_ids': [order['items'][0]['id']]})
    assert assigned.status_code == 201, assigned.text
    path = f"/api/v1/orders/{order['id']}/location"
    first = client.post(path, headers=admin_headers, json={'bay_id': plan['bays'][0]['id'], 'reason': 'Ingreso registrado'}).json()
    assert first['order_status'] == order['status']
    current = client.get('/api/v1/workshop/layout', headers=admin_headers).json()
    occupancy = current['bays'][0]['occupancies'][0]
    assert occupancy['mechanics'][0]['username'] == 'responsable'
    assert current['orders'][0]['occupancy_id'] == first['location']['id']
    assert client.post(path, headers=admin_headers, json={
        'bay_id': plan['bays'][1]['id'], 'reason': 'Intento desactualizado', 'expected_occupancy_id': None,
    }).status_code == 409
    moved = client.post(path, headers=admin_headers, json={
        'bay_id': plan['bays'][1]['id'], 'reason': 'Movimiento registrado', 'expected_occupancy_id': first['location']['id'],
    })
    assert moved.status_code == 200, moved.text
    reloaded = client.get('/api/v1/workshop/layout', headers=admin_headers).json()
    assert reloaded['bays'][0]['occupancies'] == [] and reloaded['bays'][1]['occupancies'][0]['order_id'] == order['id']
    assert client.get('/api/v1/workshop/layout', headers=mechanic_headers).status_code == 403
    assert client.post(path, headers=mechanic_headers, json={'bay_id': None, 'reason': 'No autorizado'}).status_code == 403


def test_out_of_service_can_be_restored_but_not_occupied(client, admin_headers, work_order):
    order, _, _ = work_order
    plan = template(client, admin_headers)
    bay = plan['bays'][0]
    payload = {key: bay[key] for key in ('zone_id', 'name', 'kind', 'capacity', 'x', 'y', 'width', 'height')}
    payload.update(active=False, expected_revision=bay['revision'])
    disabled = client.put(f"/api/v1/workshop/bays/{bay['id']}", headers=admin_headers, json=payload)
    assert disabled.status_code == 200, disabled.text
    assert len(client.get('/api/v1/workshop/layout', headers=admin_headers).json()['bays']) == 5
    assert len(client.get('/api/v1/workshop/layout?include_inactive=true', headers=admin_headers).json()['bays']) == 6
    path = f"/api/v1/orders/{order['id']}/location"
    assert client.post(path, headers=admin_headers, json={'bay_id': bay['id'], 'reason': 'No disponible'}).status_code == 409
    payload.update(active=True, expected_revision=disabled.json()['revision'])
    assert client.put(f"/api/v1/workshop/bays/{bay['id']}", headers=admin_headers, json=payload).status_code == 200
    placed = client.post(path, headers=admin_headers, json={'bay_id': bay['id'], 'reason': 'Ingreso autorizado'})
    assert placed.status_code == 200, placed.text
    payload.update(active=False, expected_revision=disabled.json()['revision'] + 1)
    assert client.put(f"/api/v1/workshop/bays/{bay['id']}", headers=admin_headers, json=payload).status_code == 409


def test_attention_requires_reviewed_findings(client, admin_headers, work_order):
    order, _, _ = work_order
    template(client, admin_headers)
    report = client.post('/api/v1/inspections', headers=admin_headers,
                         json={'order_id': order['id'], 'title': 'Observación real de prueba'}).json()
    finding = client.post(f"/api/v1/inspections/{report['id']}/findings", headers=admin_headers, json={
        'expected_revision': report['revision'], 'component_id': 'carroceria', 'view_id': 'inspection_side',
        'x': .2, 'y': .3, 'condition': 'issue', 'category': 'Observación', 'severity': 'minor', 'note': 'Hallazgo documentado',
    })
    assert finding.status_code == 201, finding.text
    assert not client.get('/api/v1/workshop/layout', headers=admin_headers).json()['orders'][0]['attention_required']
    reviewed = client.post(f"/api/v1/inspections/{report['id']}/review", headers=admin_headers,
                           json={'expected_revision': finding.json()['revision']})
    assert reviewed.status_code == 200, reviewed.text
    assert client.get('/api/v1/workshop/layout', headers=admin_headers).json()['orders'][0]['attention_required']
