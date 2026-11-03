import pytest

from app.catalog_models import (
    CatalogPartTerm, CatalogRecordMeta, CatalogSource, VehicleEngine,
    VehicleGeneration, VehicleMake, VehicleModel, VehiclePart, VehiclePartFit,
)
from app.models import User, Workshop
from app.security import issue_token


@pytest.fixture
def catalog(factory):
    with factory.begin() as db:
        db.add(CatalogSource(source_key='test-parts', title='Fuente verificable', url='https://example.test/data',
                              license='MIT', attribution='Fuente de prueba'))
        make = VehicleMake(slug='marca-test', name='Marca de catálogo', logo_url='https://example.test/logo.png')
        db.add(make); db.flush()
        model = VehicleModel(slug='modelo-test', name='Modelo de catálogo', make_id=make.id)
        db.add(model); db.flush()
        generation = VehicleGeneration(slug='gen-test', name='Primera', model_id=model.id, year_start=2010, year_end=2020)
        db.add(generation); db.flush()
        engine = VehicleEngine(slug='engine-test', label='1.6 Prueba', generation_id=generation.id, power_hp=120)
        db.add(engine)
        parts = []
        for sku, title, spanish, system in (
            ('OEM-123', 'Brake pad', 'Pastillas de freno', 'frenos'),
            ('GEN-456', 'Alternator', 'Alternador', 'electrico'),
            ('REF-789', 'Radiator', 'Radiador', 'refrigeracion'),
        ):
            part = VehiclePart(sku=sku, title=title, category=system, brand='Fabricante de referencia')
            db.add(part); db.flush()
            db.add(CatalogPartTerm(part_id=part.id, source_key='test-parts', name_es=spanish,
                system=system, synonyms=['balatas'] if system == 'frenos' else [],
                review_required=False, translated_by='glosario'))
            db.add(CatalogRecordMeta(entity_type='part', entity_id=part.id, source_key='test-parts', origin='imported'))
            parts.append(part.id)
        db.add(VehiclePartFit(part_id=parts[0], model_id=model.id, source_key='test-parts', year_from=2012, year_to=2018))
        db.flush()
        return dict(make=make.id, model=model.id, generation=generation.id, engine=engine.id, parts=parts)


@pytest.mark.parametrize('query', ['Pastillas', 'Brake', 'balatas', 'OEM-123', 'frenos'])
def test_part_search_spanish_original_code_synonym(client, admin_headers, catalog, query):
    result = client.get('/api/v1/catalog/parts', headers=admin_headers, params={'q': query})
    assert result.status_code == 200, result.text
    assert result.json()['total'] == 1
    assert result.json()['items'][0]['id'] == catalog['parts'][0]
    assert result.json()['items'][0]['name_es'] == 'Pastillas de freno'


def test_page_filters_and_detail(client, admin_headers, catalog):
    first = client.get('/api/v1/catalog/parts?limit=2', headers=admin_headers).json()
    second = client.get('/api/v1/catalog/parts?limit=2&offset=2', headers=admin_headers).json()
    assert first['total'] == 3 and len(first['items']) == 2 and len(second['items']) == 1
    assert not {p['id'] for p in first['items']} & {p['id'] for p in second['items']}
    for params in ({'system': 'electrico'}, {'category': 'electrico'}, {'q': 'GEN-456', 'source': 'test-parts'}):
        result = client.get('/api/v1/catalog/parts', headers=admin_headers, params=params).json()
        assert result['total'] == 1 and result['items'][0]['id'] == catalog['parts'][1]
    filters = client.get('/api/v1/catalog/parts/filters', headers=admin_headers)
    assert filters.status_code == 200, filters.text
    assert 'frenos' in filters.json()['systems']
    detail = client.get(f"/api/v1/catalog/records/part/{catalog['parts'][0]}", headers=admin_headers).json()
    assert detail['source']['license'] == 'MIT'
    assert detail['details'][0]['model_id'] == catalog['model']
    assert all(key not in detail['record'] for key in ('stock', 'quantity', 'price'))


def test_compatibility_not_guessed_and_semantics_filtered(client, admin_headers, catalog, monkeypatch):
    from app import catalog_browse_routes as routes
    class Embedder:
        def available(self): return True
        def encode_one(self, _q): return [1.0]
    monkeypatch.setattr(routes, 'embedder', lambda: Embedder())
    monkeypatch.setattr(routes, '_semantic', lambda *_a, **_k: {catalog['parts'][1]: .99, catalog['parts'][0]: .5})
    response = client.get('/api/v1/catalog/parts', headers=admin_headers, params={
        'q': 'pieza para detener el vehículo', 'semantic': True, 'model_id': catalog['model'], 'year': 2015,
    })
    assert response.status_code == 200, response.text
    assert response.json()['mode'] == 'hybrid'
    assert [row['id'] for row in response.json()['items']] == [catalog['parts'][0]]
    assert client.get('/api/v1/catalog/parts', headers=admin_headers,
        params={'model_id': catalog['model'], 'year': 2021}).json()['total'] == 0
    no_fit = client.get('/api/v1/catalog/parts?model_id=999999', headers=admin_headers).json()
    assert no_fit['available'] == 3 and no_fit['empty_reason'] == 'no_documented_fits'


def test_embedding_failure_does_not_break_text(client, admin_headers, catalog, monkeypatch):
    from app import catalog_browse_routes as routes
    class Embedder:
        def available(self): return True
        def encode_one(self, _q): raise RuntimeError('No disponible')
    monkeypatch.setattr(routes, 'embedder', lambda: Embedder())
    result = client.get('/api/v1/catalog/parts?q=balatas&semantic=true', headers=admin_headers)
    assert result.status_code == 200 and result.json()['total'] == 1
    assert result.json()['mode'] == 'text'


def test_automotive_hierarchy_and_logos(client, admin_headers, catalog):
    for entity, params, expected in (
        ('make', {}, 'make'), ('model', {'make_id': catalog['make']}, 'model'),
        ('generation', {'model_id': catalog['model']}, 'generation'),
        ('engine', {'generation_id': catalog['generation']}, 'engine'),
    ):
        result = client.get('/api/v1/catalog/browse', headers=admin_headers, params={'entity': entity, **params})
        assert result.status_code == 200, result.text
        assert result.json()['items'][0]['id'] == catalog[expected]
        if entity == 'make': assert result.json()['items'][0]['logo_url'].startswith('https://')
    assert client.get('/api/v1/catalog/browse?entity=model&make_id=999999', headers=admin_headers).json()['total'] == 0
    assert client.get('/api/v1/catalog/browse?entity=generation&year=2021', headers=admin_headers).json()['total'] == 0


def test_roles_manual_record_and_foreign_pending(client, admin_headers, catalog, factory, make_customer):
    with factory.begin() as db:
        mechanic = User(username='mech-browse', email='browse@example.test', password_hash='test-only',
                         role='mechanic', workshop_id=1, must_change_password=False)
        db.add(mechanic); db.flush()
        headers = {'Authorization': 'Bearer ' + issue_token(mechanic)}
        db.add(Workshop(id=2, name='Otro taller')); db.flush()
        stranger = User(username='other-browse', email='other-browse@example.test', password_hash='test-only',
                        role='mechanic', workshop_id=2, must_change_password=False)
        db.add(stranger); db.flush()
        other_id = stranger.id
    assert client.get('/api/v1/catalog/parts', headers=headers).status_code == 200
    assert client.get('/api/v1/workshop/layout', headers=headers).status_code == 403
    _, customer_headers = make_customer()
    assert client.get('/api/v1/catalog/parts', headers=customer_headers).status_code == 403
    created = client.post('/api/v1/catalog/parts', headers=headers, json={
        'title': 'Componente local', 'name_es': 'Componente local', 'sku': 'LOCAL-EC', 'note': 'Registrado en taller',
    })
    assert created.status_code == 201, created.text
    manual_id = created.json()['id']
    assert client.get('/api/v1/catalog/parts?q=LOCAL-EC', headers=headers).json()['items'][0]['origin'] == 'needs_review'
    with factory.begin() as db:
        db.get(CatalogRecordMeta, ('part', manual_id)).created_by = other_id
    assert client.get('/api/v1/catalog/parts?q=LOCAL-EC', headers=admin_headers).json()['total'] == 0
    assert client.get(f'/api/v1/catalog/records/part/{manual_id}', headers=admin_headers).status_code == 404


def test_empty_differs_from_no_matches(client, admin_headers):
    result = client.get('/api/v1/catalog/parts', headers=admin_headers).json()
    assert result['available'] == 0 and result['empty_reason'] == 'empty_catalog'
