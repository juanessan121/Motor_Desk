import pytest
from sqlalchemy import select

from app.catalog_models import CatalogPartTerm, CatalogRecordMeta, VehiclePart
from app.models import AuditEvent, User, Workshop
from app.security import issue_token


@pytest.fixture
def mechanic(factory):
    with factory.begin() as db:
        user = User(username='proponente', email='proponente@example.test', password_hash='test-only',
                    role='mechanic', workshop_id=1, must_change_password=False)
        db.add(user)
        db.flush()
        return user.id, {'Authorization': 'Bearer ' + issue_token(user)}


def proposal(client, headers, entity, **data):
    response = client.post(f'/api/v1/catalog/{entity}', headers=headers, json=data)
    assert response.status_code == 201, response.text
    return response.json()


def test_pendientes_verificacion_revision_y_auditoria(client, admin_headers, mechanic, factory):
    user_id, headers = mechanic
    part = proposal(client, headers, 'parts', title='Repuesto propuesto', sku='revision-1',
                    name_es='Repuesto propuesto', synonyms=['alternativa'])
    assert part['origin'] == 'needs_review'
    queue = client.get('/api/v1/catalog/review-queue', headers=admin_headers).json()
    assert queue['total'] == 1
    row = queue['items'][0]
    assert row['created_by'] == user_id and row['terms'][0]['review_required']
    path = f"/api/v1/catalog/review-queue/part/{part['id']}"
    pending = client.post(path, headers=admin_headers, json={
        'expected_revision': row['revision'], 'decision': 'keep_pending', 'note': 'Falta comprobar el código',
    })
    assert pending.status_code == 200, pending.text
    assert pending.json()['revision'] == 2 and pending.json()['origin'] == 'needs_review'
    # Una pantalla desactualizada no puede confirmar sobre una revisión ajena.
    assert client.post(path, headers=admin_headers, json={
        'expected_revision': 1, 'decision': 'verify',
    }).status_code == 409
    approved = client.post(path, headers=admin_headers, json={
        'expected_revision': 2, 'decision': 'verify', 'note': 'Código contrastado con ficha del fabricante',
    })
    assert approved.status_code == 200, approved.text
    assert approved.json()['origin'] == 'verified'
    assert approved.json()['reviewed_by'] is not None
    assert approved.json()['reviewed_at'] is not None
    assert not approved.json()['terms'][0]['review_required']
    assert client.get('/api/v1/catalog/review-queue', headers=admin_headers).json()['total'] == 0
    history = client.get('/api/v1/catalog/review-queue?state=verified', headers=admin_headers).json()
    assert history['total'] == 1 and history['items'][0]['revision'] == 3
    with factory() as db:
        events = list(db.scalars(select(AuditEvent).where(AuditEvent.action == 'catalog.record_reviewed')))
        assert len(events) == 2
        assert events[-1].payload['before']['origin'] == 'needs_review'
        assert events[-1].payload['previous_revision'] == 2
        assert db.get(VehiclePart, part['id']) is not None
    # Repetir el POST no aprueba ni audita por segunda vez.
    assert client.post(path, headers=admin_headers, json={
        'expected_revision': 3, 'decision': 'verify',
    }).status_code == 409


def test_no_certifica_traducciones_importadas(client, admin_headers, mechanic, factory):
    _, headers = mechanic
    part = proposal(client, headers, 'parts', title='Con traducción', sku='revision-2', name_es='Pieza manual')
    with factory.begin() as db:
        db.add(CatalogPartTerm(part_id=part['id'], source_key='otra-fuente', name_es='Nombre importado',
                               review_required=True, translated_by='prueba'))
    response = client.post(f"/api/v1/catalog/review-queue/part/{part['id']}", headers=admin_headers,
                           json={'expected_revision': 1, 'decision': 'verify'})
    assert response.status_code == 200, response.text
    with factory() as db:
        assert db.get(CatalogPartTerm, (part['id'], 'otra-fuente')).review_required


def test_verificar_jerarquia_en_orden(client, admin_headers, mechanic):
    _, headers = mechanic
    make = proposal(client, admin_headers, 'makes', name='Marca propuesta')
    model = proposal(client, headers, 'models', make_id=make['id'], name='Modelo propuesto')
    generation = proposal(client, headers, 'generations', model_id=model['id'], name='Generación propuesta')
    engine = proposal(client, headers, 'engines', generation_id=generation['id'], label='Motor propuesto')
    def verify(entity, record):
        return client.post(f"/api/v1/catalog/review-queue/{entity}/{record['id']}", headers=admin_headers,
                           json={'expected_revision': 1, 'decision': 'verify'})
    assert verify('generation', generation).status_code == 409
    for entity, record in [('model', model), ('generation', generation), ('engine', engine)]:
        result = verify(entity, record)
        assert result.status_code == 200, result.text
        assert result.json()['origin'] == 'verified'


def test_permisos_y_aislamiento(client, admin_headers, mechanic, make_customer, factory):
    _, headers = mechanic
    part = proposal(client, headers, 'parts', title='Privada de revisión', sku='revision-3')
    _, customer_headers = make_customer()
    path = f"/api/v1/catalog/review-queue/part/{part['id']}"
    for denied in (headers, customer_headers):
        assert client.get('/api/v1/catalog/review-queue', headers=denied).status_code == 403
        assert client.post(path, headers=denied, json={
            'expected_revision': 1, 'decision': 'verify',
        }).status_code == 403
    assert client.get('/api/v1/catalog/review-queue').status_code == 401
    with factory.begin() as db:
        db.add(Workshop(id=2, name='Otro taller'))
        db.flush()
        admin = User(username='otro-admin', email='otro@example.test', password_hash='test-only',
                     role='admin', workshop_id=2, must_change_password=False)
        db.add(admin)
        db.flush()
        other_headers = {'Authorization': 'Bearer ' + issue_token(admin)}
    assert client.get('/api/v1/catalog/review-queue', headers=other_headers).json()['total'] == 0
    assert client.post(path, headers=other_headers, json={
        'expected_revision': 1, 'decision': 'verify',
    }).status_code == 404


@pytest.mark.parametrize('body', [
    {'expected_revision': 1, 'decision': 'keep_pending', 'note': '  '},
    {'expected_revision': 0, 'decision': 'verify'},
    {'expected_revision': 1, 'decision': 'delete'},
])
def test_no_hay_borrado_ni_pendiente_sin_motivo(client, admin_headers, mechanic, body):
    _, headers = mechanic
    part = proposal(client, headers, 'parts', title='Conservar pieza', sku='revision-4')
    response = client.post(f"/api/v1/catalog/review-queue/part/{part['id']}",
                           headers=admin_headers, json=body)
    assert response.status_code == 422


def test_filtros_y_paginacion(client, admin_headers, mechanic):
    _, headers = mechanic
    for index in range(3):
        proposal(client, headers, 'parts', title=f'Pieza {index}', sku=f'pag-{index}')
    response = client.get('/api/v1/catalog/review-queue?entity_type=part&limit=2&offset=2',
                          headers=admin_headers).json()
    assert response['total'] == 3 and len(response['items']) == 1
    assert client.get('/api/v1/catalog/review-queue?entity_type=model', headers=admin_headers).json()['total'] == 0


def test_origen_importado_no_se_revisa_por_esta_cola(client, admin_headers, mechanic, factory):
    _, headers = mechanic
    part = proposal(client, headers, 'parts', title='Importada', sku='revision-importada')
    with factory.begin() as db:
        meta = db.get(CatalogRecordMeta, ('part', part['id']))
        meta.source_key, meta.origin = 'parts', 'imported'
    assert client.get('/api/v1/catalog/review-queue', headers=admin_headers).json()['total'] == 0
    assert client.post(f"/api/v1/catalog/review-queue/part/{part['id']}", headers=admin_headers,
                       json={'expected_revision': 1, 'decision': 'verify'}).status_code == 404
