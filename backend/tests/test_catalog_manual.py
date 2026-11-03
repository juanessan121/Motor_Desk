"""Registro manual del catálogo y configuración regional de Ecuador.

Estas rutas nacieron porque se comprobó que Chevrolet Sail, Optra y Lanos no
están en ninguna fuente. El catálogo es global y no se puede cerrar: lo que
falte lo registra el taller, con autor y procedencia.
"""
import pytest

from app.catalog_models import (
    ENTITY_MAKE, ENTITY_MODEL, ENTITY_PART, ORIGIN_MANUAL, ORIGIN_NEEDS_REVIEW,
    CatalogRecordMeta,
)
from app.regional import (
    format_plate, normalize_plate, normalize_text, regional_config,
    validate_national_id, validate_plate,
)


class TestValidacionPlaca:
    """Las placas ecuatorianas tienen excepciones legítimas: la validación
    avisa, no bloquea el registro del vehículo."""

    @pytest.mark.parametrize("placa", ["PGE4576", "pbe-1234", "ABC123", "PBE123", "CD1234"])
    def test_admite_formatos_ecuanianos(self, placa):
        aceptada, motivo = validate_plate(placa)
        assert aceptada, motivo

    def test_normaliza_para_comparar(self):
        assert normalize_plate("pbe-1234") == normalize_plate("PBE1234")
        assert normalize_plate(" pbe 1234 ") == "PBE1234"

    def test_admite_formato_inusual_con_aviso(self):
        # Un registro provisional del trámite no puede bloquear al taller.
        aceptada, motivo = validate_plate("1234")
        assert aceptada
        assert "revisión" in motivo or "patrón" in motivo

    def test_rechaza_vacio_y_excesivamente_largo(self):
        assert validate_plate("")[0] is False
        assert validate_plate("PGE12345678")[0] is False

    def test_no_bloquea_placas_existentes(self):
        # El vehículo de la base de desarrollo debe seguir siendo válido.
        assert validate_plate("PGE4576")[0] is True

    def test_formato_para_mostrar_no_altera_lo_almacenado(self):
        assert format_plate("pbe1234") == "PBE-1234"
        assert format_plate("ABC") == "ABC"


class TestValidacionCedula:
    @staticmethod
    def _digito(cuerpo):
        from app.regional import _check_digit
        return cuerpo + str(_check_digit(cuerpo))

    def test_acepta_cedula_con_digito_correcto(self):
        assert validate_national_id(self._digito("171003406"))[0] is True

    def test_acepta_ruc_de_tipos_validos(self):
        from app.regional import _check_digit
        cuerpo = "171003406500"
        for prefijo in ("00", "15", "17"):
            valor = prefijo + cuerpo[2:]
            assert validate_national_id(valor + str(_check_digit(valor)))[0] is True

    def test_rechaza_ruc_de_tipo_invalido(self):
        from app.regional import _check_digit
        # 2 de tipo + 10 de cuerpo + 1 verificador = 13. El verificador es
        # válido, así que el único motivo del rechazo es el tipo.
        cuerpo = "20" + "1710034065"
        assert validate_national_id(cuerpo + str(_check_digit(cuerpo)))[1] \
            == "Un RUC ecuatoriano empieza por 00, 15 o 17"

    def test_rechaza_digito_verificador_erroneo(self):
        base = self._digito("171003406")
        alterada = base[:-1] + str((int(base[-1]) + 1) % 10)
        assert validate_national_id(alterada)[0] is False

    def test_rechaza_longitud_imposible(self):
        assert validate_national_id("123")[0] is False

    def test_rechaza_digitos_repetidos(self):
        assert validate_national_id("0000000000")[0] is False

    def test_vacio_se_acepta_para_no_bloquear(self):
        assert validate_national_id("") == (True, "")


class TestConfiguracionRegional:
    def test_valores_por_defecto_de_ecuador(self):
        config = regional_config(None)
        assert config["country"] == "EC"
        assert config["locale"] == "es-EC"
        assert config["timezone"] == "America/Guayaquil"
        assert config["currency"] == "USD"
        assert config["date_format"] == "dd/MM/yyyy"
        assert config["distance_unit"] == "km"

    def test_lo_guardado_gana_al_defecto(self):
        config = regional_config({"regional": {"currency": "USD", "timezone": "America/Guayaquil",
                                               "locale": "es-EC"}})
        assert config["country"] == "EC"      # no guardado, viene por defecto
        assert config["locale"] == "es-EC"

    def test_normalizacion_para_detectar_duplicados(self):
        assert normalize_text("Seat León") == normalize_text("seatleon")
        assert normalize_text("CHERY") == normalize_text("chery")


class TestRegistroManual:
    def _catalog(self, client, headers, path, **body):
        return client.post(path, headers=headers, json=body)

    def test_registra_marca_inexistente_con_alias(self, client, admin_headers):
        # Chevrolet Sail no está en el catálogo de fuentes: se registra.
        response = self._catalog(client, admin_headers, "/api/v1/catalog/makes",
                                 name="Prueba Manual", country="Ecuador",
                                 aliases=["PruebaUno", "Prueba Uno", "prueba-uno"])
        assert response.status_code == 201, response.text
        data = response.json()
        assert data["origin"] == "manual"
        # Alias duplicados por normalización se colapsan a uno solo.
        assert len(set(data["aliases"])) == len(data["aliases"])

    def test_la_marca_queda_persistida_con_procedencia(self, client, admin_headers, factory):
        response = self._catalog(client, admin_headers, "/api/v1/catalog/makes",
                                 name="Marca Persistida")
        assert response.status_code == 201
        make_id = response.json()["id"]
        with factory() as db:
            meta = db.get(CatalogRecordMeta, (ENTITY_MAKE, make_id))
            assert meta.origin == ORIGIN_MANUAL
            assert meta.source_key == "manual"

    def test_sugerencias_evitan_duplicar(self, client, admin_headers):
        creado = self._catalog(client, admin_headers, "/api/v1/catalog/makes",
                                name="Sugerible")
        assert creado.status_code == 201
        # Antes de crear otra vez, la interfaz consulta /suggest.
        response = client.get("/api/v1/catalog/suggest?q=Sugerible", headers=admin_headers)
        assert response.status_code == 200
        assert any(item["name"] == "Sugerible" for item in response.json()["makes"])

    def test_cadena_completa_marca_modelo_generacion_motor(self, client, admin_headers):
        marca = self._catalog(client, admin_headers, "/api/v1/catalog/makes", name="Cadena")
        assert marca.status_code == 201
        modelo = self._catalog(client, admin_headers, "/api/v1/catalog/models",
                               make_id=marca.json()["id"], name="Modelo X", year_start=2015)
        assert modelo.status_code == 201, modelo.text
        generacion = self._catalog(client, admin_headers, "/api/v1/catalog/generations",
                                   model_id=modelo.json()["id"], name="Gen 1",
                                   year_start=2015, year_end=2018)
        assert generacion.status_code == 201, generacion.text
        motor = self._catalog(client, admin_headers, "/api/v1/catalog/engines",
                              generation_id=generacion.json()["id"], label="1.6L 16V",
                              power_hp=120)
        assert motor.status_code == 201, motor.text
        assert motor.json()["origin"] == "manual"

    def test_rechaza_relaciones_inexistentes(self, client, admin_headers):
        assert self._catalog(client, admin_headers, "/api/v1/catalog/models",
                             make_id=999999, name="Huerfano").status_code == 404
        assert self._catalog(client, admin_headers, "/api/v1/catalog/generations",
                             model_id=999999, name="Huerfano").status_code == 404
        assert self._catalog(client, admin_headers, "/api/v1/catalog/engines",
                             generation_id=999999, label="Huerfano").status_code == 404

    def test_rechaza_especificaciones_absurdas(self, client, admin_headers):
        marca = self._catalog(client, admin_headers, "/api/v1/catalog/makes", name="Specs")
        modelo = self._catalog(client, admin_headers, "/api/v1/catalog/models",
                               make_id=marca.json()["id"], name="M")
        generacion = self._catalog(client, admin_headers, "/api/v1/catalog/generations",
                                   model_id=modelo.json()["id"], name="G")
        # 2 cc y 1 hp no son un motor: se rechaza antes de ensuciar el catálogo.
        respuesta = self._catalog(client, admin_headers, "/api/v1/catalog/engines",
                                  generation_id=generacion.json()["id"],
                                  label="raro", displacement_cc=2, power_hp=1)
        assert respuesta.status_code == 422

    def test_registra_repuesto_con_traduccion(self, client, admin_headers, factory):
        response = self._catalog(client, admin_headers, "/api/v1/catalog/parts",
                                 title="Rodamiento de rueda|Spanish", sku="prueba-rod",
                                 name_es="Rodamiento de rueda", system="neumaticos",
                                 synonyms=["buje", "rodamiento"])
        assert response.status_code == 201, response.text
        data = response.json()
        assert data["name_es"] == "Rodamiento de rueda"
        assert data["system"] == "neumaticos"
        assert "buje" in data["synonyms"]

    def test_no_duplica_codigo_de_repuesto(self, client, admin_headers):
        primero = self._catalog(client, admin_headers, "/api/v1/catalog/parts",
                                title="Repuesto repetido", sku="dup-1")
        assert primero.status_code == 201
        segundo = self._catalog(client, admin_headers, "/api/v1/catalog/parts",
                                title="Repuesto repetido", sku="dup-1")
        assert segundo.status_code == 409

    def test_cliente_no_registra_nada_en_el_catalogo(self, client, make_customer):
        _customer, headers = make_customer()
        response = client.post("/api/v1/catalog/makes", headers=headers,
                               json={"name": "Intruso"})
        assert response.status_code == 403