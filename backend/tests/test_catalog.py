"""Pruebas del catálogo de referencia: glosario, procedencia e idempotencia.

El importador nunca se había ejecutado, así que nada de esto estaba cubierto.
Estas pruebas no necesitan red ni las fuentes reales: trabajan sobre el módulo
de glosario y sobre la base en memoria del fixture `factory`.
"""
import pytest
from datetime import datetime, timezone

from app.catalog_import import SessionLocal
from app.catalog_models import (
    ENTITY_MAKE, ORIGIN_IMPORTED, ORIGIN_MANUAL, CatalogRecordMeta,
    CatalogPartTerm, VehicleMake, VehiclePart,
)
from app.catalog_import import normalize, register_meta, slugify, system_of, upsert
from app.parts_glossary import SYNONYMS, translate


class TestGlosario:
    """El nombre en español se compone a partir del slug en inglés."""

    @pytest.mark.parametrize("slug,esperado", [
        ("alternator", "Alternador"),
        ("spark-plug", "Bujía"),
        ("brake-disc", "Disco de freno"),
        ("timing-kit", "Kit de distribución"),
        ("coolant-expansion-tank", "Depósito de expansión"),
        ("oil-filter", "Filtro de aceite"),
        ("exhaust-manifold-gasket", "Junta de colector de escape"),
        ("wheel-bearing", "Rodamiento de rueda"),
    ])
    def test_terminos_conocidos(self, slug, esperado):
        nombre, _sistema, revision = translate(slug)
        assert nombre == esperado
        assert revision is False

    @pytest.mark.parametrize("slug,esperado", [
        # En español el modificador va detrás del sustantivo...
        ("rear-shock-absorber", "Amortiguador trasero"),
        # ...y concuerda en género con él: "pastilla" es femenino.
        ("front-left-brake-pad", "Pastilla de freno delantera izquierda"),
        # La fuente escribe "left front" y "front left" indistintamente.
        ("left-front-fog-light", "Luz antiniebla delantero izquierdo"),
        # "side" forma parte del sustantivo, no lo precede.
        ("left-side-mirror", "Espejo lateral izquierdo"),
        # Varias palabras de posición a la vez.
        ("rear-right-hydraulic-strut", "Hidráulico amortiguador trasero derecho"),
    ])
    def test_orden_y_genero(self, slug, esperado):
        nombre, _sistema, revision = translate(slug)
        assert nombre == esperado
        assert revision is False

    def test_palabra_desconocida_se_marca_para_revision(self):
        # No se inventa: se traduce lo que se puede y se avisa.
        nombre, _sistema, revision = translate("zzz-unknown-token")
        assert revision is True
        assert nombre  # existe, pero pendiente de que alguien lo confirme

    def test_sin_palabras_devuelve_none(self):
        nombre, _sistema, revision = translate("")
        assert nombre is None
        assert revision is True

    def test_siglas_se_conservan(self):
        nombre, _sistema, revision = translate("abs-sensor")
        assert nombre == "Sensor ABS"
        assert revision is False

    @pytest.mark.parametrize("texto,sistema", [
        ("Ignition coil", "electrico"),
        ("Brake pad set", "frenos"),
        ("Air filter", "climatizacion"),
        ("Front shock absorber", "suspension"),
        ("Timing belt kit", "motor"),
        ("Exhaust manifold gasket", "escape"),
        ("Wheel bearing", "neumaticos"),
    ])
    def test_clasificacion_por_sistema(self, texto, sistema):
        assert system_of(texto) == sistema

    def test_sistema_desconocido_es_none_no_inventado(self):
        # `None` significa "sin clasificar". No se asigna un sistema por
        # defecto ni se deduce uno de una palabra cualquiera.
        nombre, sistema, revision = translate("zzz-qqq")
        assert sistema is None
        assert revision is True
        # Un sistema conocido sí se clasifica aunque la traducción sea dudosa.
        _nombre, sistema, _revision = translate("engine-zzz-qqq")
        assert sistema == "motor"

    def test_sinonimos_solo_para_terminos_verificados(self):
        nombre, _sistema, _revision = translate("brake-pad")
        assert nombre == "Pastilla de freno"
        assert "balata" in SYNONYMS["pastilla de freno"]
        # Un término sin entrada devuelve vacío, no una suposición.
        assert SYNONYMS.get("xyz") is None


class TestSlugsDeMotor:
    """El slug de motor debe numerar por generación del catálogo.

    Varias generaciones de la fuente pueden terminar fusionadas en una sola
    del catálogo. Si el contador fuera por generación de origen, dos fuentes
    distintas producirían el mismo slug `G--0` y `upsert` las fusionaría:
    en la primera importación real se perdieron 1 067 variantes de 30 535.
    """

    def test_contador_por_generacion_del_catalogo(self):
        from app.catalog_import import engine_rows

        # Las generaciones 10 y 20 de la fuente quedaron fusionadas en la 7.
        pairs = [(10, 100), (10, 101), (20, 200), (20, 201)]

        class Src:
            def execute(self, _query):
                return [dict(source_generation_id=s, id=e, generation_id=s)
                        for s, e in pairs]

        generated = list(engine_rows(Src(), {10: 7, 20: 7}))
        slugs = [row["slug"] for row in generated]
        assert len(set(slugs)) == len(slugs), "dos motores comparten slug"
        assert slugs == ["7--0", "7--1", "7--2", "7--3"]


class TestPuntuacionHibrida:
    """Lo textual debe ganar siempre a lo semántico.

    El reparto anterior `(1-peso)*rango` contra `peso*similitud` hacía que
    cualquier coincidencia semántica desplazara a todas las textuales, y se
    midió que la búsqueda híbrida era PEOR que la textual (63,6 % frente a
    90,9 %). Estos tests fijan el invariante para que no vuelva a pasar.
    """

    def test_bandas_separadas(self):
        from app.catalog_routes import SEMANTIC_CEILING, TEXT_FLOOR

        assert TEXT_FLOOR > SEMANTIC_CEILING, (
            "una coincidencia textual en el peor puesto debe superar a la mejor "
            "coincidencia semántica")

    def test_texto_no_pierde_contra_semantica(self):
        from app.catalog_routes import SEMANTIC_CEILING, TEXT_FLOOR

        # Peor caso textual: último resultado de una lista larga.
        peor_texto = 1.0 - TEXT_FLOOR
        # Mejor caso semántico: similitud 1 y peso 1.
        mejor_semantica = SEMANTIC_CEILING
        assert peor_texto > mejor_semantica

    def test_peso_cero_excluye_la_semantica(self, factory):
        # Con peso 0 el usuario pide solo texto; los candidatos semánticos se
        # colaban en el ranking con puntuación 0.
        from app.catalog_routes import search

        with factory() as db:
            make = VehicleMake(slug="prueba", name="Prueba")
            db.add(make)
            db.flush()
            part = VehiclePart(sku="carapi:prueba", title="Пружина", category="suspension")
            db.add(part)
            db.flush()
            db.add(CatalogPartTerm(part_id=part.id, source_key="part_terms",
                                   name_es="Resorte de suspensión", system="suspension",
                                   synonyms=None, keywords=None, review_required=False,
                                   translated_by="test", translated_at=datetime.now(timezone.utc)))
            db.commit()

            resultado = search(db, _Admin(), q="zzzzque-no-existe", type="part",
                               limit=12, semantic_weight=0.0)
            # Sin coincidencias textuales y con peso 0 no debe devolver nada,
            # aunque el modelo semántico proponja candidatos.
            assert resultado["results"]["part"] == []


class _Admin:
    id, role, workshop_id, must_change_password = 1, "admin", 1, False


class TestNormalizacion:
    def test_slugify_deja_solo_kebab(self):
        assert slugify("Wideband oxygen sensor") == "wideband-oxygen-sensor"
        assert slugify("  Air  Filter (Cabin) ") == "air-filter-cabin"

    def test_normalize_ignora_acentos_y_signos(self):
        assert normalize("Chevrolet") == normalize("chevrolet")
        assert normalize("Seat León") == normalize("seatleon")
        assert normalize("Škoda") == normalize("skoda")


class TestUpsert:
    def test_claves_repetidas_se_combinan_y_ensanchan_anos(self, factory):
        from app.catalog_models import VehicleModel
        from sqlalchemy import select

        with factory() as db:
            makes = upsert(db, VehicleMake, [
                {"slug": "toyota", "name": "Toyota", "country": "Japan"}], "slug")
            # La fuente repite `datsun--go` con años distintos; sin combinar
            # el lote violaría el índice único a mitad de la importación.
            ids = upsert(db, VehicleModel, [
                {"make_id": makes["toyota"], "slug": "datsun--go",
                 "name": "Go", "year_start": 1991, "year_end": 1993},
                {"make_id": makes["toyota"], "slug": "datsun--go",
                 "name": "Go", "year_start": 1995, "year_end": 2000},
            ], "slug")
            db.commit()
            assert len(ids) == 1
            row = db.scalar(select(VehicleModel).where(VehicleModel.slug == "datsun--go"))
            assert row.year_start == 1991
            assert row.year_end == 2000

    def test_reimportar_no_duplica_ni_sobrescribe(self, factory):
        from sqlalchemy import select, func

        with factory() as db:
            upsert(db, VehicleMake, [
                {"slug": "toyota", "name": "Toyota", "country": "Japan"}], "slug")
            db.commit()
            # Segunda pasada con el mismo dato, y luego con uno distinto:
            # una reimportación no debe duplicar ni pisar lo ya guardado.
            upsert(db, VehicleMake, [
                {"slug": "toyota", "name": "Toyota (renamed)", "country": "Japan"}], "slug")
            db.commit()
            total = db.scalar(select(func.count(VehicleMake.id)))
            row = db.scalar(select(VehicleMake).where(VehicleMake.slug == "toyota"))
            assert total == 1
            assert row.name == "Toyota"


class TestProcedencia:
    def test_registra_origen_importado(self, factory):
        with factory() as db:
            ids = upsert(db, VehicleMake, [
                {"slug": "toyota", "name": "Toyota", "country": "Japan"}], "slug")
            register_meta(db, ENTITY_MAKE, ids.values(), "vehicles")
            db.commit()
            row = db.get(CatalogRecordMeta, (ENTITY_MAKE, ids["toyota"]))
            assert row.origin == ORIGIN_IMPORTED
            assert row.source_key == "vehicles"

    def test_una_reimportacion_no_pisa_un_registro_manual(self, factory):
        with factory() as db:
            ids = upsert(db, VehicleMake, [
                {"slug": "toyota", "name": "Toyota", "country": "Japan"}], "slug")
            db.add(CatalogRecordMeta(
                entity_type=ENTITY_MAKE, entity_id=ids["toyota"],
                source_key="manual", origin=ORIGIN_MANUAL))
            db.commit()
            # La siguiente importación vuelve a pasar por las mismas filas.
            register_meta(db, ENTITY_MAKE, ids.values(), "vehicles")
            db.commit()
            row = db.get(CatalogRecordMeta, (ENTITY_MAKE, ids["toyota"]))
            assert row.origin == ORIGIN_MANUAL
            assert row.source_key == "manual"

    def test_no_registra_duplicados(self, factory):
        with factory() as db:
            ids = upsert(db, VehicleMake, [
                {"slug": "toyota", "name": "Toyota", "country": "Japan"}], "slug")
            first = register_meta(db, ENTITY_MAKE, ids.values(), "vehicles")
            second = register_meta(db, ENTITY_MAKE, ids.values(), "vehicles")
            db.commit()
            assert first == 1
            assert second == 0