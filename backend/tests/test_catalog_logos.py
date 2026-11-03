"""Logotipos de marca: el parámetro `logo` debe decidir la respuesta.

Regresión: `_make_json` incluía siempre `logo_url` y `makes()` lo sobreescribía
con un segundo diccionario. Funcionaba por casualidad: si alguien reordenaba
esos dos dicts, el filtro `logo=false` devolvería todas las URL.
"""
from app.catalog_models import VehicleMake


class _Admin:
    id = 1
    role = "admin"
    workshop_id = 1


class TestLogoDeMarca:
    def _marca(self, db, nombre="Prueba", logo="https://ejemplo.test/logo.png"):
        marca = VehicleMake(slug=nombre.lower(), name=nombre, logo_url=logo)
        db.add(marca)
        db.commit()
        return marca

    def test_sin_logo_no_devuelve_la_url(self, factory):
        from app.catalog_routes import makes

        with factory() as db:
            self._marca(db)
            resultado = makes(db, _Admin(), "", False, 200)
            assert resultado[0]["logo_url"] is None

    def test_con_logo_devuelve_la_url(self, factory):
        from app.catalog_routes import makes

        with factory() as db:
            self._marca(db)
            resultado = makes(db, _Admin(), "", True, 200)
            assert resultado[0]["logo_url"] == "https://ejemplo.test/logo.png"

    def test_el_resto_de_datos_no_cambia(self, factory):
        from app.catalog_routes import makes

        with factory() as db:
            self._marca(db, "Kia Motor")
            con = makes(db, _Admin(), "", True, 200)[0]
            sin = makes(db, _Admin(), "", False, 200)[0]
            # Quitar el logo no puede quitar ni añadir otros campos.
            assert set(con) == set(sin)
            assert {k: v for k, v in con.items() if k != "logo_url"} == \
                   {k: v for k, v in sin.items() if k != "logo_url"}

    def test_una_marca_sin_logo_devuelve_null(self, factory):
        from app.catalog_routes import makes

        with factory() as db:
            self._marca(db, "SinLogo", logo=None)
            resultado = makes(db, _Admin(), "", True, 200)
            assert resultado[0]["logo_url"] is None

    def test_el_endpoint_respeta_el_parametro(self, client, admin_headers,
                                              factory):
        """Lo que ve la interfaz real, no solo la función interna."""
        with factory() as db:
            self._marca(db, "Hyundai")
            db.commit()
        con = client.get("/api/v1/catalog/makes?logo=true",
                         headers=admin_headers).json()
        sin = client.get("/api/v1/catalog/makes",
                         headers=admin_headers).json()
        hyundai_con = next(r for r in con if r["name"] == "Hyundai")
        hyundai_sin = next(r for r in sin if r["name"] == "Hyundai")
        assert hyundai_con["logo_url"] == "https://ejemplo.test/logo.png"
        assert hyundai_sin["logo_url"] is None

    def test_una_consulta_no_trae_logos_por_defecto(self, client,
                                                    admin_headers, factory):
        """El selector en cascada pide 165 filas sin necesitar 165 URLs."""
        with factory() as db:
            self._marca(db, "Hyundai")
            db.commit()
        respuesta = client.get("/api/v1/catalog/makes",
                               headers=admin_headers)
        assert respuesta.status_code == 200
        assert all(r["logo_url"] is None for r in respuesta.json())