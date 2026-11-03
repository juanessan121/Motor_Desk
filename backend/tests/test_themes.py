"""Pruebas del sistema visual: catálogo de temas, publicación y config regional."""
import pytest

from app.branding import DEFAULT_THEME, THEMES, theme_palette, themes
from app.models import AppConfiguration


class TestCatalogoDeTemas:
    def test_los_cuatro_temas_del_prompt_existen(self):
        assert set(THEMES) == {
            "pitlane", "carbon-racing", "electric-blue", "heritage-garage"}

    def test_cada_tema_tiene_la_paleta_completa(self):
        requeridas = {
            "navigation", "background", "surface", "text", "secondary_text",
            "primary", "accent", "complementary", "diagnostic",
            "success", "warning", "danger", "unknown",
        }
        for key, paleta in THEMES.items():
            faltan = requeridas - set(paleta)
            assert not faltan, f"el tema {key} no define {faltan}"
            for nombre, valor in paleta.items():
                if nombre in {"label", "description"}:
                    continue
                assert valor.startswith("#") and len(valor) == 7, \
                    f"{key}.{nombre} no es un color hexadecimal"

    def test_paleta_por_defecto_es_pitlane(self):
        assert DEFAULT_THEME == "pitlane"
        assert theme_palette(None) == THEMES["pitlane"]
        assert theme_palette("no-existe") == THEMES["pitlane"]

    def test_el_catalogo_se_expone_con_etiqueta_y_descripcion(self):
        catalogo = themes()
        assert len(catalogo) == 4
        for tema in catalogo:
            assert tema["label"] and tema["description"]

    def test_estados_semanticos_no_se_confunden(self):
        # Normal, seguimiento, incidencia y sin datos son cuatro colores
        # distintos: un estado no puede pintarse igual que otro.
        for key, paleta in THEMES.items():
            estados = {paleta["success"], paleta["warning"],
                       paleta["danger"], paleta["unknown"]}
            assert len(estados) == 4, f"{key} repite colores de estado"


class TestPublicacionDelTema:
    def _config(self, **branding):
        base = {
            "name": "Taller", "tagline": "", "welcome": "", "logo": "",
            "colors": {"primary": "#2563EB", "secondary": "#0D9488",
                       "background": "#F4F6FA", "surface": "#FFFFFF"},
        }
        base.update(branding)
        return {"schema_version": 1, "branding": base,
                "features": {"vehicles": True, "maintenance": True,
                             "quotes": True, "photos": True,
                             "history": True}}

    def _publicar(self, db, **branding):
        """Sobrescribe la configuración global. `bootstrap` ya la crea, así
        que insertar de nuevo violaría la clave primaria."""
        row = db.get(AppConfiguration, "global")
        payload = self._config(**branding)
        if row is None:
            row = AppConfiguration(scope="global", payload=payload)
            db.add(row)
        else:
            row.payload = payload
            row.revision = 1
        db.flush()
        return row

    def test_guardar_el_tema_no_pierde_la_region(self, client, admin_headers, factory):
        """Regresión: el payload se reemplaza entero, así que una clave que el
        cliente no envía se borra. Sin esto, guardar la marca borraba la
        configuración de Ecuador."""
        with factory() as db:
            row = self._publicar(db, theme="heritage-garage")
            row.payload["regional"] = {"country": "EC", "currency": "USD",
                                      "timezone": "America/Guayaquil"}
            db.commit()

        response = client.put("/api/v1/config/global", headers=admin_headers,
                              json={**self._config(theme="carbon-racing"),
                                    "expected_revision": 1})
        assert response.status_code == 200, response.text
        assert response.json()["regional"]["currency"] == "USD"
        assert response.json()["theme_key"] == "carbon-racing"

    def test_el_tema_elegido_llega_resuelto_a_la_interfaz(self, client, admin_headers, factory):
        with factory() as db:
            self._publicar(db, theme="electric-blue")
            db.commit()
        response = client.get("/api/v1/config", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["theme_key"] == "electric-blue"
        # La interfaz no lleva paletas propias: las recibe ya resueltas.
        assert data["theme"]["navigation"] == THEMES["electric-blue"]["navigation"]
        assert data["theme"]["success"] == THEMES["electric-blue"]["success"]

    def test_sin_tema_elegido_manda_el_por_defecto(self, client, admin_headers, factory):
        with factory() as db:
            self._publicar(db)
            db.commit()
        data = client.get("/api/v1/config", headers=admin_headers).json()
        assert data["theme_key"] == DEFAULT_THEME

    def test_tema_desconocido_se_rechaza(self, client, admin_headers, factory):
        with factory() as db:
            self._publicar(db)
            db.commit()
        response = client.put("/api/v1/config/global", headers=admin_headers,
                              json={**self._config(theme="tema-inventado"),
                                    "expected_revision": 1})
        assert response.status_code == 422

    def test_publicar_es_explicito(self, client, admin_headers, factory):
        """Cambiar de tema no publica nada por su cuenta: la revisión sube."""
        with factory() as db:
            self._publicar(db, theme="pitlane")
            db.commit()
            antes = db.get(AppConfiguration, "global").revision
        response = client.put("/api/v1/config/global", headers=admin_headers,
                              json={**self._config(theme="heritage-garage"),
                                    "expected_revision": antes})
        assert response.status_code == 200
        with factory() as db:
            assert db.get(AppConfiguration, "global").revision == antes + 1

    def test_revision_desfasada_se_rechaza(self, client, admin_headers, factory):
        with factory() as db:
            self._publicar(db)
            db.commit()
        response = client.put("/api/v1/config/global", headers=admin_headers,
                              json={**self._config(theme="pitlane"),
                                    "expected_revision": 99})
        assert response.status_code == 409

    def test_editar_el_tema_no_toca_la_identidad_comercial(self, client, admin_headers, factory):
        with factory() as db:
            self._publicar(db, theme="pitlane", name="Taller Norte",
                           logo="https://ejemplo.test/logo.png")
            db.commit()
            revision = db.get(AppConfiguration, "global").revision
        client.put("/api/v1/config/global", headers=admin_headers,
                   json={**self._config(theme="carbon-racing",
                                        name="Taller Norte",
                                        logo="https://ejemplo.test/logo.png"),
                         "expected_revision": revision})
        data = client.get("/api/v1/config", headers=admin_headers).json()
        assert data["branding"]["name"] == "Taller Norte"
        assert data["branding"]["logo"] == "https://ejemplo.test/logo.png"
        assert data["theme_key"] == "carbon-racing"


class TestPermisosDeConfiguracion:
    def test_el_catalogo_de_temas_lo_ve_cualquier_cuenta_autenticada(
            self, client, admin_headers, make_customer):
        _customer, headers = make_customer()
        response = client.get("/api/v1/config/themes", headers=headers)
        assert response.status_code == 200
        assert len(response.json()["themes"]) == 4

    def test_no_lo_ve_sin_autenticar(self, client):
        assert client.get("/api/v1/config/themes").status_code == 401

    def test_publicar_un_tema_es_solo_de_administrador(self, client, make_customer):
        _customer, headers = make_customer()
        response = client.put("/api/v1/config/global", headers=headers, json={
            "schema_version": 1, "expected_revision": 1,
            "branding": {"name": "X", "tagline": "", "welcome": "", "logo": "",
                         "colors": {"primary": "#2563EB", "secondary": "#0D9488",
                                    "background": "#F4F6FA", "surface": "#FFFFFF"},
                         "theme": "heritage-garage"},
            "features": {"vehicles": True, "maintenance": True, "quotes": True,
                         "photos": True, "history": True}})
        assert response.status_code == 403