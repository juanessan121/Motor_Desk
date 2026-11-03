from copy import deepcopy


def payload():
    return {'format': 'motordesk-registry', 'version': 1, 'customers': [
        {'source_id': 40, 'data': {'national_id': 'REGISTRY-1', 'first_name': 'Ana', 'last_name': 'Local',
         'email': 'registry@example.com', 'has_portal_access': False}}],
        'vehicles': [{'source_id': 90, 'data': {'owner_id': 40, 'plate': 'IMP-1234', 'brand': 'Toyota', 'model': 'Corolla', 'year': 2020}}]}


def test_incremental_registry_and_repeat(client, admin_headers):
    data = payload()
    preview = client.post('/api/v1/registry-transfer/preview', headers=admin_headers, json=data)
    assert preview.status_code == 200 and preview.json()['valid']
    assert client.get('/api/v1/customers', headers=admin_headers).json() == []
    first = client.post('/api/v1/registry-transfer/import', headers=admin_headers, json=data)
    assert first.status_code == 200, first.text
    assert first.json() == {'created_customers': 1, 'created_vehicles': 1}
    repeat = client.post('/api/v1/registry-transfer/import', headers=admin_headers, json=data)
    assert repeat.status_code == 200 and repeat.json()['created_customers'] == 0
    export = client.get('/api/v1/registry-transfer/export', headers=admin_headers).json()
    assert export['customers'][0]['data']['has_portal_access'] is False
    assert client.post('/api/v1/registry-transfer/preview', headers=admin_headers, json=export).json()['unchanged'] == 2


def test_conflicts_do_not_overwrite_or_partially_import(client, admin_headers):
    data = payload()
    assert client.post('/api/v1/registry-transfer/import', headers=admin_headers, json=data).status_code == 200
    changed = deepcopy(data)
    changed['customers'][0]['data']['first_name'] = 'Nombre diferente'
    extra = deepcopy(data['customers'][0]); extra['source_id'] = 41
    extra['data'].update(national_id='REGISTRY-2', email='registry2@example.com')
    changed['customers'].append(extra)
    assert client.post('/api/v1/registry-transfer/import', headers=admin_headers, json=changed).status_code == 409
    rows = client.get('/api/v1/customers', headers=admin_headers).json()
    assert len(rows) == 1 and rows[0]['first_name'] == 'Ana'


def test_invalid_owner_and_accounts_rejected(client, admin_headers):
    data = payload(); data['vehicles'][0]['data']['owner_id'] = 999
    assert client.post('/api/v1/registry-transfer/import', headers=admin_headers, json=data).status_code == 422
    data = payload(); data['customers'][0]['data']['has_portal_access'] = True
    assert client.post('/api/v1/registry-transfer/import', headers=admin_headers, json=data).status_code == 422
