"""Regresiones del contrato HTTP: cadena de IDs, edición y aislamiento."""
import pytest

from app.catalog_models import (
    CatalogAlias, CatalogRecordMeta, VehicleEngine, VehicleGeneration, VehicleMake, VehicleModel,
)
from app.catalog_link import resolve_vehicle


@pytest.fixture
def reference(factory):
    with factory() as db:
        make = VehicleMake(name='Referencia', slug='referencia')
        db.add(make)
        db.flush()
        model = VehicleModel(name='Uno', slug='referencia-uno', make_id=make.id)
        db.add(model)
        db.flush()
        generation = VehicleGeneration(name='Primera', slug='referencia-uno-primera',
                                       model_id=model.id, year_start=2010, year_end=2022)
        db.add(generation)
        db.flush()
        engine = VehicleEngine(label='1.6 Prueba', slug='referencia-uno-16',
                               generation_id=generation.id, power_hp=120)
        db.add(engine)
        db.commit()
        return {'make': make.id, 'model': model.id, 'generation': generation.id, 'engine': engine.id}


def body(owner_id, **extra):
    return dict(owner_id=owner_id, brand='Referencia', model='Uno', year=2018,
                plate='REF1234', mileage=1000, **extra)


def test_crear_editar_y_pasaporte_coinciden(client, admin_headers, make_customer, reference):
    customer, customer_headers = make_customer()
    payload = body(customer['id'], catalog_engine_id=reference['engine'])
    result = client.post('/api/v1/vehicles', headers=admin_headers, json=payload)
    assert result.status_code == 201, result.text
    vehicle = result.json()
    ref = vehicle['catalog']
    assert ref['engine']['power_hp'] == 120
    assert ref['generation_id'] == reference['generation']
    assert ref['model_id'] == reference['model']
    # Cliente solo recibe la referencia de su propio vehículo, no el árbol global.
    passport = client.get(f"/api/v1/vehicles/{vehicle['id']}/passport", headers=customer_headers)
    assert passport.status_code == 200, passport.text
    assert passport.json()['vehicle']['catalog'] == ref
    assert client.get('/api/v1/catalog/makes', headers=customer_headers).status_code == 403
    # Un cliente antiguo que solo cambia kilometraje no borra el motor elegido.
    payload.pop('catalog_engine_id')
    payload['mileage'] = 2000
    edited = client.put(f"/api/v1/vehicles/{vehicle['id']}", headers=admin_headers, json=payload)
    assert edited.status_code == 200, edited.text
    assert edited.json()['catalog'] == ref
    # Cambiar identidad limpia relaciones ya cargadas en la misma respuesta.
    payload['brand'], payload['model'] = 'Sin catálogo', 'Especial'
    cleared = client.put(f"/api/v1/vehicles/{vehicle['id']}", headers=admin_headers, json=payload)
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()['catalog'] is None
    assert client.get('/api/v1/vehicles', headers=admin_headers).json()[0]['catalog'] is None


@pytest.mark.parametrize('field', ['make', 'model', 'generation', 'engine'])
def test_rechaza_ids_inexistentes(client, admin_headers, make_customer, field):
    customer, _ = make_customer()
    result = client.post('/api/v1/vehicles', headers=admin_headers,
                         json=body(customer['id'], **{f'catalog_{field}_id': 999999}))
    assert result.status_code == 422, result.text
    assert client.get('/api/v1/vehicles', headers=admin_headers).json() == []


def test_rechaza_cadena_cruzada(client, admin_headers, make_customer, reference, factory):
    customer, _ = make_customer()
    with factory() as db:
        other = VehicleMake(name='Otra', slug='otra')
        db.add(other)
        db.commit()
        other_id = other.id
    result = client.post('/api/v1/vehicles', headers=admin_headers,
                         json=body(customer['id'], catalog_make_id=other_id,
                                   catalog_engine_id=reference['engine']))
    assert result.status_code == 422


@pytest.mark.parametrize('year', [2009, 2023])
def test_no_elige_generacion_fuera_del_rango(factory, reference, year):
    with factory() as db:
        assert resolve_vehicle(db, 'Referencia', 'Uno', year).generation_id is None


def test_no_descarta_generacion_sin_fechas_para_forzar_una_coincidencia(factory, reference):
    with factory() as db:
        db.add(VehicleGeneration(model_id=reference['model'], name='Sin fechas', slug='sin-fechas'))
        db.commit()
        assert resolve_vehicle(db, 'Referencia', 'Uno', 2018).generation_id is None


def test_no_infiere_motor_aunque_solo_exista_uno(client, admin_headers, make_customer, reference):
    customer, _ = make_customer()
    result = client.post('/api/v1/vehicles', headers=admin_headers, json=body(customer['id']))
    assert result.status_code == 201, result.text
    assert result.json()['catalog']['generation_id'] == reference['generation']
    assert result.json()['catalog']['engine'] is None


def test_el_usuario_puede_quitar_referencia(client, admin_headers, make_customer, reference):
    customer, _ = make_customer()
    created = client.post('/api/v1/vehicles', headers=admin_headers, json=body(customer['id'])).json()
    result = client.put(f"/api/v1/vehicles/{created['id']}", headers=admin_headers,
                        json=body(customer['id'], catalog_make_id=None, catalog_model_id=None,
                                  catalog_generation_id=None, catalog_engine_id=None))
    assert result.status_code == 200, result.text
    assert result.json()['catalog'] is None


def test_alias_verificado_y_propuestas_pendientes(factory, reference):
    with factory() as db:
        db.add(CatalogAlias(alias='La referencia', normalized='lareferencia', entity_type='make',
                            entity_id=reference['make'], verified=True, source_key='manual'))
        db.add(CatalogRecordMeta(entity_type='model', entity_id=reference['model'],
                                 source_key='manual', origin='needs_review'))
        db.commit()
        match = resolve_vehicle(db, 'La referencia', 'Uno', 2018)
        assert match.make_id == reference['make']
        assert match.model_id is None


def test_cliente_ajeno_no_recibe_pasaporte(client, admin_headers, make_customer, reference):
    customer, _ = make_customer('1')
    _, stranger = make_customer('2')
    created = client.post('/api/v1/vehicles', headers=admin_headers, json=body(customer['id'])).json()
    assert client.get(f"/api/v1/vehicles/{created['id']}/passport", headers=stranger).status_code == 404


def test_archivar_con_referencias_no_rompe_bloqueo_postgres(client, admin_headers, make_customer, reference):
    customer, _ = make_customer()
    created = client.post('/api/v1/vehicles', headers=admin_headers, json=body(customer['id'])).json()
    result = client.delete(f"/api/v1/vehicles/{created['id']}", headers=admin_headers)
    assert result.status_code == 200, result.text


def test_filtro_de_modelo_respeta_propiedad(client, admin_headers, make_customer, reference):
    customer, own = make_customer('1')
    _, other = make_customer('2')
    client.post('/api/v1/vehicles', headers=admin_headers, json=body(customer['id']))
    path = f"/api/v1/vehicles?catalog_model_id={reference['model']}"
    assert len(client.get(path, headers=admin_headers).json()) == 1
    assert len(client.get(path, headers=own).json()) == 1
    assert client.get(path, headers=other).json() == []
    assert client.get('/api/v1/vehicles?catalog_model_id=999999', headers=admin_headers).json() == []


def test_backfill_no_reemplaza_selecciones_existentes(
        client, admin_headers, make_customer, reference, factory, monkeypatch, capsys):
    from app import catalog_link_backfill
    from app.models import Vehicle
    customer, _ = make_customer()
    chosen = client.post('/api/v1/vehicles', headers=admin_headers,
                         json=body(customer['id'], catalog_engine_id=reference['engine'])).json()
    pending = body(customer['id'], catalog_make_id=None)
    pending['plate'] = 'REF5678'
    unlinked = client.post('/api/v1/vehicles', headers=admin_headers, json=pending).json()
    monkeypatch.setattr(catalog_link_backfill, 'SessionLocal', factory)
    monkeypatch.setattr('sys.argv', ['backfill'])
    assert catalog_link_backfill.main() == 0
    with factory() as db:
        assert db.get(Vehicle, unlinked['id']).catalog_model_id is None
    monkeypatch.setattr('sys.argv', ['backfill', '--apply'])
    assert catalog_link_backfill.main() == 0
    with factory() as db:
        assert db.get(Vehicle, chosen['id']).catalog_engine_id == reference['engine']
        assert db.get(Vehicle, unlinked['id']).catalog_model_id == reference['model']
        assert db.get(Vehicle, unlinked['id']).catalog_engine_id is None
    assert 'conservadas: 1' in capsys.readouterr().out


@pytest.mark.parametrize('changes', [
    {'year': 2009}, {'brand': 'Otra marca'}, {'model': 'Otro modelo'},
])
def test_seleccion_explicita_incoherente_no_guarda(client, admin_headers, make_customer, reference, changes):
    customer, _ = make_customer()
    payload = body(customer['id'], catalog_engine_id=reference['engine'])
    payload.update(changes)
    result = client.post('/api/v1/vehicles', headers=admin_headers, json=payload)
    assert result.status_code == 422
    assert client.get('/api/v1/vehicles', headers=admin_headers).json() == []


@pytest.mark.parametrize('entity', ['make', 'model', 'generation', 'engine'])
def test_propuesta_pendiente_no_se_vincula(client, admin_headers, make_customer, reference, factory, entity):
    customer, _ = make_customer()
    with factory.begin() as db:
        db.add(CatalogRecordMeta(entity_type=entity, entity_id=reference[entity],
                                 source_key='manual', origin='needs_review'))
    result = client.post('/api/v1/vehicles', headers=admin_headers,
                         json=body(customer['id'], catalog_engine_id=reference['engine']))
    assert result.status_code == 409, result.text
    assert client.get('/api/v1/vehicles', headers=admin_headers).json() == []
