from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models import Customer, Notification, User, Workshop, WorkOrder
from app.notifications import enqueue
from app.security import issue_token


def test_offline_notifications_without_portal(client, admin_headers, factory):
    customer = client.post('/api/v1/customers', headers=admin_headers, json={
        'national_id': 'SIN-PORTAL', 'first_name': 'Ana', 'last_name': 'Local',
        'email': 'ana@example.com', 'has_portal_access': False,
    }).json()
    with factory.begin() as db:
        c = db.get(Customer, customer['id'])
        for kind in ('order_created', 'ready', 'payment'):
            enqueue(db, c, kind, 'Evento del taller', 'Mensaje disponible sin internet')
    rows = client.get('/api/v1/notifications', headers=admin_headers).json()
    assert len(rows) == 3
    assert all(r['customer_id'] == customer['id'] and r['status'] == 'pending' and r['body'] for r in rows)
    assert len(client.get('/api/v1/export/workshop-data', headers=admin_headers).json()['notificaciones']) == 3
    assert client.post(f"/api/v1/notifications/{rows[0]['id']}/archive", headers=admin_headers).status_code == 200


def test_no_portal_complete_service(client, admin_headers, factory):
    customer = client.post('/api/v1/customers', headers=admin_headers, json={
        'national_id': 'PRESENCIAL', 'first_name': 'Ana', 'last_name': 'Local',
        'email': 'presencial@example.com', 'has_portal_access': False,
    }).json()
    vehicle = client.post('/api/v1/vehicles', headers=admin_headers, json={
        'owner_id': customer['id'], 'plate': 'PRE-1234', 'brand': 'Toyota', 'model': 'Corolla', 'year': 2020,
    }).json()
    template = client.post('/api/v1/catalogs', headers=admin_headers, json={
        'name': 'Inspección local', 'base_price': '100.10', 'tasks': ['Inspección'],
    }).json()
    order = client.post('/api/v1/orders', headers=admin_headers, json={
        'vehicle_id': vehicle['id'], 'catalog_id': template['id'],
    }).json()
    path = f"/api/v1/orders/{order['id']}"
    approval = {'approved': True, 'note': 'Cliente autoriza presencialmente el servicio y su costo', 'expected_revision': order['revision']}
    assert client.post(path + '/recorded-approval', headers=admin_headers, json=approval).status_code == 200
    assert client.post(path + '/recorded-approval', headers=admin_headers, json=approval).status_code == 409
    item = order['items'][0]
    executed = client.patch(path + f"/items/{item['id']}", headers=admin_headers, json={'status': 'completed', 'expected_revision': item['revision']}).json()
    reviewed = client.post(path + '/execution-review', headers=admin_headers, json={'expected_revision': executed['revision'], 'note': 'Revisión final completada'})
    assert reviewed.status_code == 200, reviewed.text
    delivered = client.patch(path + '/status?status=delivered', headers=admin_headers)
    assert delivered.status_code == 200, delivered.text
    assert delivered.json()['cost_status'] == 'final'
    assert delivered.json()['total'] == delivered.json()['total_amount'] == '115.12'
    rows = client.get('/api/v1/notifications', headers=admin_headers).json()
    assert {r['kind'] for r in rows} == {'order_created', 'vehicle_ready', 'payment_info'}
    assert all(r['status'] == 'pending' and r['customer_id'] == customer['id'] for r in rows)
    exported = client.get('/api/v1/export/workshop-data', headers=admin_headers).json()
    assert exported['mantenimientos'][0]['costos']['total'] == 115.12
    history = exported['seguimiento_estados'][0]['historial_real']
    assert history[-1]['estado_anterior'] == 'ready' and history[-1]['estado_nuevo'] == 'delivered'


def test_notification_archive_tenant_and_export_role(client, admin_headers, factory):
    with factory.begin() as db:
        other = Workshop(name='Otro'); db.add(other); db.flush()
        customer = Customer(workshop_id=other.id, national_id='OTRO', first_name='Privado', last_name='Otro', email='otro@example.com')
        db.add(customer); db.flush()
        row = enqueue(db, customer, 'ready', 'Privado', 'No divulgar')
        db.flush(); notice_id = row.id
        mechanic = User(username='m-limitado', email='m@example.com', password_hash='unused', role='mechanic', workshop_id=1, must_change_password=False)
        db.add(mechanic); db.flush()
        headers = {'Authorization': 'Bearer ' + issue_token(mechanic)}
    assert client.post(f'/api/v1/notifications/{notice_id}/archive', headers=admin_headers).status_code == 404
    assert client.post(f'/api/v1/notifications/{notice_id}/retry', headers=admin_headers).status_code == 404
    assert client.get('/api/v1/export/workshop-data', headers=headers).status_code == 403


def test_timeline_does_not_invent_dates(factory, work_order):
    from app.export_routes import build_7_state_timeline
    with factory() as db:
        order = db.get(WorkOrder, work_order[0]['id'])
        order.status = 'delivered'
        timeline = {r['estado']: r for r in build_7_state_timeline(order)}
        assert timeline['recepcionado']['fecha']
        assert timeline['diagnostico'] == {'estado': 'diagnostico', 'alcanzado': False, 'fecha': None}
        assert timeline['entregado']['fecha'] is None


def test_configurable_tax_snapshot(client, admin_headers, work_order, factory):
    config = client.get('/api/v1/config', headers=admin_headers).json()
    payload = {k: config[k] for k in ('branding', 'features', 'regional')}
    payload.update(expected_revision=config['revision'])
    payload['regional']['tax_rate'] = '0.0800'
    saved = client.put('/api/v1/config/global', headers=admin_headers, json=payload)
    assert saved.status_code == 200, saved.text
    original = work_order[0]
    with factory.begin() as db:
        previous = db.get(WorkOrder, original['id'])
        previous.status = 'delivered'
        catalog_id = previous.catalog_id
    result = client.post('/api/v1/orders', headers=admin_headers, json={
        'vehicle_id': original['vehicle_id'], 'catalog_id': catalog_id, 'labor_cost': '100.10', 'parts_cost': '10.00',
    })
    assert result.status_code == 201, result.text
    assert Decimal(result.json()['tax_amount']) == Decimal('8.81')
    assert Decimal(client.get(f"/api/v1/orders/{original['id']}", headers=admin_headers).json()['tax_rate']) == Decimal('0.15')


@pytest.mark.parametrize('rate', ['NaN', 'Infinity', '-0.01', '1.01', '0.12345'])
def test_reject_invalid_tax(rate):
    from app.schemas import ConfigInput
    with pytest.raises(ValueError):
        ConfigInput.valid_tax_rate({'tax_rate': rate})


def test_sqlite_migration_preserves_messages(tmp_path):
    from app.database import make_engine
    from app.local_schema import initialize_database, LOCAL_SCHEMA
    from sqlalchemy.schema import CreateTable
    engine = make_engine('sqlite:///' + (tmp_path / 'migration.db').as_posix())
    initialize_database(engine)
    with engine.begin() as db:
        db.exec_driver_sql('DROP TABLE notifications')
        ddl = str(CreateTable(Notification.__table__).compile(engine))
        ddl = '\n'.join(line for line in ddl.splitlines() if 'customer_id' not in line)
        ddl = ddl.replace('user_id INTEGER,', 'user_id INTEGER NOT NULL,')
        db.exec_driver_sql(ddl)
        db.exec_driver_sql('PRAGMA user_version=1')
        db.exec_driver_sql("INSERT INTO workshops (id, name) VALUES (1, 'Taller anterior')")
        db.exec_driver_sql("INSERT INTO users (id, username, email, password_hash, role, workshop_id, active, must_change_password, token_version, created_at) VALUES (1, 'admin', 'admin@example.com', 'hashed', 'admin', 1, 1, 0, 0, CURRENT_TIMESTAMP)")
        db.exec_driver_sql("INSERT INTO notifications (id, user_id, kind, channel, status, attempts, next_attempt_at, created_at) VALUES (1, 1, 'ready', 'email', 'pending', 2, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)")
    initialize_database(engine)
    with engine.connect() as db:
        assert db.exec_driver_sql('PRAGMA user_version').scalar() == LOCAL_SCHEMA
        assert not db.exec_driver_sql('PRAGMA foreign_key_check').all()
        assert db.exec_driver_sql('SELECT id, user_id, attempts FROM notifications').one() == (1, 1, 2)
    initialize_database(engine)
    engine.dispose()
