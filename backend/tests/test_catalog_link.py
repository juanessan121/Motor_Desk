"""Enlace de vehículos con el catálogo.

La regla que más importa aquí no es la que enlaza: es la que **se abstiene**.
Un enlace equivocado hace que el Pasaporte muestre un motor que no es el del
coche, con toda la apariencia de un dato verificado. Cada prueba de ambigüedad
existe para ese fallo.
"""
import pytest

from app.catalog_link import resolve_vehicle
from app.catalog_models import VehicleGeneration, VehicleMake, VehicleModel
from app.models import Vehicle


def _catalogo(db, marcas=(), modelos=(), generaciones=()):
    for slug, name, logo in marcas:
        db.add(VehicleMake(slug=slug, name=name, country=None, logo_url=logo))
    db.flush()
    for slug, name, make, y0, y1 in modelos:
        db.add(VehicleModel(slug=slug, name=name, make_id=make.id,
                            year_start=y0, year_end=y1))
    db.flush()
    for slug, name, model, y0, y1 in generaciones:
        db.add(VehicleGeneration(slug=slug, name=name, model_id=model.id,
                                 year_start=y0, year_end=y1))
    db.commit()


class TestResolucionSimple:
    def test_enlaza_marca_y_modelo(self, factory):
        with factory() as db:
            marca = VehicleMake(slug="toyota", name="Toyota", country=None,
                                logo_url=None)
            db.add(marca)
            db.flush()
            modelo = VehicleModel(slug="corolla", name="Corolla",
                                  make_id=marca.id, year_start=None,
                                  year_end=None)
            db.add(modelo)
            db.commit()

            match = resolve_vehicle(db, "Toyota", "Corolla", 2018)
            assert match.make_id == marca.id
            assert match.model_id == modelo.id
            assert match.make_name == 'Toyota'
            assert match.model_name == 'Corolla'

    def test_normaliza_mayusculas_espacios_y_tildes(self, factory):
        with factory() as db:
            marca = VehicleMake(slug="renault", name="Renault", country=None,
                                logo_url=None)
            db.add(marca)
            db.flush()
            db.add(VehicleModel(slug="logan", name="Logan", make_id=marca.id,
                                year_start=None, year_end=None))
            db.commit()
            for escrito in [("RENAULT", "LOGAN"), (" renault ", " logan ")]:
                match = resolve_vehicle(db, escrito[0], escrito[1], 2018)
                assert match.make_id == marca.id, escrito
                assert match.model_id is not None, escrito

    def test_acepta_el_slug_como_marca(self, factory):
        with factory() as db:
            marca = VehicleMake(slug="land-rover", name="Land Rover",
                                country=None, logo_url=None)
            db.add(marca)
            db.commit()
            assert resolve_vehicle(db, "land rover", "Discovery").make_id == marca.id

    def test_no_enlaza_modelos_por_prefijo(self, factory):
        """Un prefijo no basta para persistir la identificación del modelo."""
        with factory() as db:
            marca = VehicleMake(slug="toyota", name="Toyota", country=None,
                                logo_url=None)
            db.add(marca)
            db.flush()
            db.add(VehicleModel(slug="corolla", name="Corolla", make_id=marca.id,
                                year_start=None, year_end=None))
            db.commit()
            match = resolve_vehicle(db, "Toyota", "Corolla 1.8", 2018)
            assert match.model_id is None
            assert match.make_id == marca.id


class TestSeAbstiene:
    """Lo que el resolutor NO debe hacer."""

    def test_marca_desconocida_no_inventa(self, factory):
        with factory() as db:
            _catalogo(db, marcas=[("toyota", "Toyota", None)])
            match = resolve_vehicle(db, "Zapata", "Modelo", 2018)
            assert match.make_id is None
            assert 'no está en el catálogo' in match.reason

    def test_no_resuelve_por_prefijo_de_marca(self, factory):
        """«Kia Motors» no es «Kia»: el error sería silencioso."""
        with factory() as db:
            _catalogo(db, marcas=[("kia", "Kia", None)])
            match = resolve_vehicle(db, "Kia Motors", "Rio", 2018)
            assert match.make_id is None, 'un prefijo no es una coincidencia'

    def test_no_confunde_marcas_que_se_contienen(self, factory):
        with factory() as db:
            _catalogo(db, marcas=[("mg", "MG", None), ("mg-rover", "MG Rover", None)])
            # «MG» es una marca distinta de «MG Rover», no un prefijo suyo.
            match = resolve_vehicle(db, "MG", "ZR", 2018)
            assert match.make_name == "MG"
            mg = db.query(VehicleMake).filter_by(slug="mg").one()
            assert match.make_id == mg.id

    def test_modelo_ambiguo_no_elige(self, factory):
        with factory() as db:
            marca = VehicleMake(slug="bmw", name="BMW", country=None, logo_url=None)
            db.add(marca)
            db.flush()
            for slug in ("serie1", "serie2"):
                db.add(VehicleModel(slug=slug, name="Serie 3", make_id=marca.id,
                                    year_start=None, year_end=None))
            db.commit()
            match = resolve_vehicle(db, "BMW", "Serie 3", 2020)
            assert match.make_id == marca.id
            assert match.model_id is None, 'dos fichas del mismo nombre no se eligen'
            assert 'coincide con 2' in match.reason

    def test_generacion_ambigua_no_elige(self, factory):
        """Un Corolla tiene muchas: decir cuál para un 2018 sería inventarlo."""
        with factory() as db:
            marca = VehicleMake(slug="toyota", name="Toyota", country=None,
                                logo_url=None)
            db.add(marca)
            db.flush()
            modelo = VehicleModel(slug="corolla", name="Corolla",
                                  make_id=marca.id, year_start=None,
                                  year_end=None)
            db.add(modelo)
            db.flush()
            for slug in ("e120", "e140"):
                db.add(VehicleGeneration(slug=slug, name=slug, model_id=modelo.id,
                                         year_start=None, year_end=None))
            db.commit()
            match = resolve_vehicle(db, "Toyota", "Corolla", 2018)
            assert match.model_id == modelo.id
            assert match.generation_id is None

    def test_generacion_unica_sin_fechas_no_se_inventa(self, factory):
        with factory() as db:
            marca = VehicleMake(slug="toyota", name="Toyota", country=None,
                                logo_url=None)
            db.add(marca)
            db.flush()
            modelo = VehicleModel(slug="corolla", name="Corolla",
                                  make_id=marca.id, year_start=None,
                                  year_end=None)
            db.add(modelo)
            db.flush()
            generacion = VehicleGeneration(slug="unica", name="Única",
                                           model_id=modelo.id, year_start=None,
                                           year_end=None)
            db.add(generacion)
            db.commit()
            match = resolve_vehicle(db, "Toyota", "Corolla", 2018)
            assert match.generation_id is None

    def test_el_ano_fuera_del_rango_no_enlaza(self, factory):
        with factory() as db:
            marca = VehicleMake(slug="toyota", name="Toyota", country=None,
                                logo_url=None)
            db.add(marca)
            db.flush()
            db.add(VehicleModel(slug="corolla", name="Corolla", make_id=marca.id,
                                year_start=2019, year_end=2024))
            db.commit()
            match = resolve_vehicle(db, "Toyota", "Corolla", 2018)
            assert match.model_id is None
            assert 'fuera del rango documentado' in match.reason

    def test_sin_ano_el_rango_no_opone(self, factory):
        """Un catálogo con años no invalida un vehículo si no se sabe el año."""
        with factory() as db:
            marca = VehicleMake(slug="toyota", name="Toyota", country=None,
                                logo_url=None)
            db.add(marca)
            db.flush()
            db.add(VehicleModel(slug="corolla", name="Corolla", make_id=marca.id,
                                year_start=2019, year_end=2024))
            db.commit()
            assert resolve_vehicle(db, "Toyota", "Corolla", None).model_id is not None

    def test_vehiculo_sin_marca_no_rompe(self, factory):
        with factory() as db:
            match = resolve_vehicle(db, "", "", 2020)
            assert not match.linked
            assert 'marca' in match.reason


class TestIntegridad:
    """Lo que la migración promete sobre los datos existentes."""

    def _vehiculo(self, client, admin_headers, make_customer, **extra):
        """Vehículo real creado por la API, no una fila montada a mano.

        Montarlo a mano exigiría replicar la cadena `User -> Customer`, que es
        justo lo que estas pruebas no quieren comprobar.
        """
        customer, _ = make_customer()
        response = client.post("/api/v1/vehicles", headers=admin_headers, json={
            "owner_id": customer["id"], "plate": extra.pop("plate", "abc-123"),
            "brand": extra.pop("brand", "Toyota"),
            "model": extra.pop("model", "Corolla"),
            "year": extra.pop("year", 2018),
            "mileage": extra.pop("mileage", 1000), **extra,
        })
        assert response.status_code == 201, response.text
        return response.json()["id"]

    def test_el_texto_no_se_toca_al_enlazar(self, client, admin_headers,
                                           make_customer, factory):
        with factory() as db:
            marca = VehicleMake(slug="toyota", name="Toyota", country=None,
                                logo_url=None)
            db.add(marca)
            db.flush()
            db.add(VehicleModel(slug="corolla", name="Corolla", make_id=marca.id,
                                year_start=None, year_end=None))
            db.commit()

        # Se escribe con espacios y en mayúsculas: el taller escribe como escribe.
        vehiculo_id = self._vehiculo(client, admin_headers, make_customer,
                                      plate="abc-999", brand=" toyota ",
                                      model="COROLLA")
        with factory() as db:
            vehiculo = db.get(Vehicle, vehiculo_id)
            match = resolve_vehicle(db, vehiculo.brand, vehiculo.model,
                                    vehiculo.year)
            assert match.model_id is not None
            vehiculo.catalog_make_id = match.make_id
            vehiculo.catalog_model_id = match.model_id
            db.commit()
            db.refresh(vehiculo)

            # El enlace no reescribe lo que escribió el taller: el catálogo dice
            # «Toyota» con mayúscula, el registro sigue diciendo «toyota».
            assert vehiculo.brand == 'toyota'
            assert vehiculo.model == 'COROLLA'
            assert vehiculo.catalog_model_id is not None

    def test_un_vehiculo_sin_resolucion_sigue_siendo_valido(
            self, client, admin_headers, make_customer, factory):
        """Un clásico que no está en el catálogo se registra igual."""
        vehiculo_id = self._vehiculo(client, admin_headers, make_customer,
                                      plate="zap-001", brand="Zapata",
                                      model="Model 670")
        with factory() as db:
            vehiculo = db.get(Vehicle, vehiculo_id)
            match = resolve_vehicle(db, vehiculo.brand, vehiculo.model,
                                    vehiculo.year)
            assert not match.linked
            db.commit()
            db.refresh(vehiculo)
            assert vehiculo.id == vehiculo_id
            assert vehiculo.catalog_make_id is None

    def test_el_vehiculo_sobrevive_a_perder_la_ficha(
            self, client, admin_headers, make_customer, factory):
        """`ON DELETE SET NULL`: quitar una fila del catálogo no borra el coche."""
        with factory() as db:
            marca = VehicleMake(slug="toyota", name="Toyota", country=None,
                                logo_url=None)
            db.add(marca)
            db.flush()
            modelo = VehicleModel(slug="corolla", name="Corolla",
                                  make_id=marca.id, year_start=None,
                                  year_end=None)
            db.add(modelo)
            db.commit()
            marca_id, modelo_id = marca.id, modelo.id

        vehiculo_id = self._vehiculo(client, admin_headers, make_customer,
                                      plate="sup-001")
        with factory() as db:
            vehiculo = db.get(Vehicle, vehiculo_id)
            vehiculo.catalog_make_id = marca_id
            vehiculo.catalog_model_id = modelo_id
            db.commit()

        with factory() as db:
            db.delete(db.get(VehicleModel, modelo_id))
            db.commit()

        with factory() as db:
            vehiculo = db.get(Vehicle, vehiculo_id)
            assert vehiculo is not None, 'el vehículo no puede desaparecer'
            assert vehiculo.catalog_model_id is None
            assert vehiculo.catalog_make_id == marca_id
            assert vehiculo.plate == 'SUP-001'

    def test_la_columna_rechaza_una_ficha_inexistente(
            self, client, admin_headers, make_customer, factory):
        """La integridad referencial es real: no se puede apuntar al vacío."""
        from sqlalchemy.exc import IntegrityError

        vehiculo_id = self._vehiculo(client, admin_headers, make_customer,
                                      plate="inv-001")
        with factory() as db:
            vehiculo = db.get(Vehicle, vehiculo_id)
            vehiculo.catalog_model_id = 987654
            with pytest.raises(IntegrityError):
                db.commit()
            db.rollback()
