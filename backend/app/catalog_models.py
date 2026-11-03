"""Catálogo de referencia vehicular: marcas, modelos, generaciones, motores y repuestos.

Es un catálogo de consulta, independiente del taller: no contiene clientes ni
trabajos. Se puebla desde fuentes abiertas con `python -m app.catalog_import`.

Los embeddings viven en `catalog_embeddings` en lugar de repetirse en cada
tabla: así se puede reindexar por versión de modelo sin tocar el catálogo
relacional, y el índice vectorial se construye sobre una sola columna.
"""
from __future__ import annotations

from datetime import datetime, timezone

from pgvector.sqlalchemy import Vector as PgVector
from sqlalchemy import (
    Boolean, CheckConstraint, DateTime, Float, ForeignKey, Index, Integer,
    JSON, LargeBinary, String, Text, TypeDecorator, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base
from .embeddings import EMBEDDING_DIMENSIONS, pack, unpack

ENTITY_MAKE = "make"
ENTITY_MODEL = "model"
ENTITY_GENERATION = "generation"
ENTITY_ENGINE = "engine"
ENTITY_PART = "part"
EMBEDDED_ENTITIES = (ENTITY_MAKE, ENTITY_MODEL, ENTITY_GENERATION, ENTITY_ENGINE, ENTITY_PART)


def postgres_only(*indexes: Index) -> tuple[Index, ...]:
    """Indices que solo existen en PostgreSQL (HNSW y trigram).

    La migración 0004 los crea con SQL directo. Declararlos aquí, marcados con
    `ddl_if`, hace que `alembic check` vea el esquema real y que un
    `autogenerate` posterior no proponga borrar el índice vectorial. En SQLite
    (pruebas) no se emiten.
    """
    for index in indexes:
        index.ddl_if(dialect="postgresql")
    return indexes


def trgm_index(name: str, column: str) -> Index:
    return Index(name, column, postgresql_using="gin", postgresql_ops={column: "gin_trgm_ops"})


def utcnow():
    return datetime.now(timezone.utc)


class EmbeddingVector(TypeDecorator):
    """Vector nativo en PostgreSQL (indexable con HNSW) y bytes en SQLite.

    Las pruebas corren en SQLite, donde no existe el tipo `vector`; allí se
    guardan los float32 empaquetados para que el catálogo siga siendo usable.
    """

    impl = LargeBinary
    cache_ok = True

    def __init__(self, dimensions: int | None = None, **kwargs):
        self.dimensions = dimensions or EMBEDDING_DIMENSIONS
        super().__init__(**kwargs)

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PgVector(self.dimensions))
        return dialect.type_descriptor(LargeBinary())

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, (bytes, bytearray)):
            return bytes(value)
        if dialect.name == "postgresql":
            return [float(item) for item in value]
        return pack(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, (bytes, bytearray)):
            return unpack(value)
        return [float(item) for item in value]


class CatalogSource(Base):
    """Procedencia y licencia de cada fuente importada."""

    __tablename__ = "catalog_sources"
    source_key: Mapped[str] = mapped_column(String(60), primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    url: Mapped[str] = mapped_column(String(300))
    license: Mapped[str] = mapped_column(String(60))
    license_url: Mapped[str] = mapped_column(String(300), default="")
    attribution: Mapped[str] = mapped_column(Text, default="")
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    content_hash: Mapped[str] = mapped_column(String(64), default="")
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class VehicleMake(Base):
    __tablename__ = "catalog_makes"
    __table_args__ = postgres_only(trgm_index("ix_catalog_makes_trgm", "name"))
    id: Mapped[int] = mapped_column(primary_key=True)
    # `unique=True` + `index=True` colapsa en un único índice único, que es lo
    # que declara la migración 0004. Ver nota sobre el duplicado en esa revisión.
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    country: Mapped[str | None] = mapped_column(String(80))
    logo_url: Mapped[str | None] = mapped_column(String(400))
    models: Mapped[list["VehicleModel"]] = relationship(back_populates="make")


class VehicleModel(Base):
    __tablename__ = "catalog_models"
    __table_args__ = postgres_only(trgm_index("ix_catalog_models_trgm", "name"))
    id: Mapped[int] = mapped_column(primary_key=True)
    make_id: Mapped[int] = mapped_column(ForeignKey("catalog_makes.id"), index=True)
    slug: Mapped[str] = mapped_column(String(160), unique="catalog_models_slug_key", index=True)
    name: Mapped[str] = mapped_column(String(160))
    year_start: Mapped[int | None] = mapped_column(Integer)
    year_end: Mapped[int | None] = mapped_column(Integer)
    make: Mapped[VehicleMake] = relationship(back_populates="models")
    generations: Mapped[list["VehicleGeneration"]] = relationship(back_populates="model")


class VehicleGeneration(Base):
    __tablename__ = "catalog_generations"
    id: Mapped[int] = mapped_column(primary_key=True)
    model_id: Mapped[int] = mapped_column(ForeignKey("catalog_models.id"), index=True)
    slug: Mapped[str] = mapped_column(String(200), unique="catalog_generations_slug_key", index=True)
    name: Mapped[str] = mapped_column(String(200))
    year_start: Mapped[int | None] = mapped_column(Integer)
    year_end: Mapped[int | None] = mapped_column(Integer)
    body_type: Mapped[str | None] = mapped_column(String(80))
    model: Mapped[VehicleModel] = relationship(back_populates="generations")


class VehicleEngine(Base):
    __tablename__ = "catalog_engines"
    id: Mapped[int] = mapped_column(primary_key=True)
    generation_id: Mapped[int] = mapped_column(ForeignKey("catalog_generations.id"), index=True)
    slug: Mapped[str] = mapped_column(String(240), unique="catalog_engines_slug_key", index=True)
    label: Mapped[str] = mapped_column(String(240))
    fuel_type: Mapped[str | None] = mapped_column(String(80))
    cylinders: Mapped[int | None] = mapped_column(Integer)
    displacement_cc: Mapped[float | None] = mapped_column(Float)
    power_hp: Mapped[float | None] = mapped_column(Float)
    torque_nm: Mapped[float | None] = mapped_column(Float)
    transmission: Mapped[str | None] = mapped_column(String(255))
    drivetrain: Mapped[str | None] = mapped_column(String(80))
    zero_to_100_s: Mapped[float | None] = mapped_column(Float)
    top_speed_kmh: Mapped[float | None] = mapped_column(Float)
    fuel_economy_l100: Mapped[float | None] = mapped_column(Float)
    length_mm: Mapped[float | None] = mapped_column(Float)
    width_mm: Mapped[float | None] = mapped_column(Float)
    height_mm: Mapped[float | None] = mapped_column(Float)
    wheelbase_mm: Mapped[float | None] = mapped_column(Float)
    curb_weight_kg: Mapped[float | None] = mapped_column(Float)


class VehicleEngineSpec(Base):
    """Especificaciones crudas tal cual las publica la fuente (ODbL)."""

    __tablename__ = "catalog_engine_specs"
    __table_args__ = (Index("ix_engine_specs_engine_key", "engine_id", "key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    engine_id: Mapped[int] = mapped_column(ForeignKey("catalog_engines.id"), index=True)
    key: Mapped[str] = mapped_column(String(160))
    value: Mapped[str] = mapped_column(Text)


class VehiclePart(Base):
    __tablename__ = "catalog_parts"
    __table_args__ = postgres_only(trgm_index("ix_catalog_parts_trgm", "title"))
    id: Mapped[int] = mapped_column(primary_key=True)
    sku: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    mpn: Mapped[str | None] = mapped_column(String(80))
    title: Mapped[str] = mapped_column(String(200))
    brand: Mapped[str | None] = mapped_column(String(120), index=True)
    category: Mapped[str | None] = mapped_column(String(120), index=True)


class VehiclePartFit(Base):
    """Compatibilidad repuesto <-> modelo/año declarada por la fuente."""

    __tablename__ = "catalog_part_fits"
    __table_args__ = (UniqueConstraint("part_id", "source_key", "model_id", name="part_fit"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    part_id: Mapped[int] = mapped_column(ForeignKey("catalog_parts.id"), index=True)
    model_id: Mapped[int | None] = mapped_column(ForeignKey("catalog_models.id"), index=True)
    source_key: Mapped[str] = mapped_column(String(120), index=True)
    year_from: Mapped[int | None] = mapped_column(Integer)
    year_to: Mapped[int | None] = mapped_column(Integer)


class CatalogEmbedding(Base):
    """Vector de búsqueda por entidad. La clave permite reindexar por versión."""

    __tablename__ = "catalog_embeddings"
    __table_args__ = (
        Index("ix_catalog_embeddings_model", "model_key"),
        *postgres_only(Index(
            "ix_catalog_embeddings_hnsw", "vector",
            postgresql_using="hnsw", postgresql_ops={"vector": "vector_cosine_ops"},
        )),
    )
    entity_type: Mapped[str] = mapped_column(String(20), primary_key=True)
    entity_id: Mapped[int] = mapped_column(primary_key=True)
    model_key: Mapped[str] = mapped_column(String(80))
    vector: Mapped[list] = mapped_column(EmbeddingVector())


ENTITY_TYPES = ("make", "model", "generation", "engine", "part")
ORIGIN_IMPORTED = "imported"
ORIGIN_MANUAL = "manual"
ORIGIN_VERIFIED = "verified"
ORIGIN_NEEDS_REVIEW = "needs_review"
RECORD_ORIGINS = (ORIGIN_IMPORTED, ORIGIN_MANUAL, ORIGIN_VERIFIED, ORIGIN_NEEDS_REVIEW)


class CatalogRecordMeta(Base):
    """Procedencia por registro: qué fuente lo trajo y quién lo añadió.

    Sin esta tabla no se puede distinguir un dato importado de uno escrito a
    mano, ni proteger el manual de la siguiente importación.
    """

    __tablename__ = "catalog_record_meta"
    __table_args__ = (
        CheckConstraint(f"entity_type IN {ENTITY_TYPES!r}", name="catalog_meta_entity"),
        CheckConstraint(f"origin IN {RECORD_ORIGINS!r}", name="catalog_meta_origin"),
        Index("ix_catalog_record_meta_source", "source_key"),
        Index("ix_catalog_record_meta_origin", "origin"),
    )
    entity_type: Mapped[str] = mapped_column(String(20), primary_key=True)
    entity_id: Mapped[int] = mapped_column(primary_key=True)
    source_key: Mapped[str] = mapped_column(String(60))
    origin: Mapped[str] = mapped_column(String(20))
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revision: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_note: Mapped[str] = mapped_column(String(1000), default="", server_default="")


class CatalogPartTerm(Base):
    """Nombre en español, sistema mecánico y sinónimos de un repuesto.

    `review_required` marca lo que el glosario no resolvió con respaldo. La
    interfaz lo muestra como pendiente de revisión; nunca como verificado.
    """

    __tablename__ = "catalog_part_terms"
    __table_args__ = (
        Index("ix_catalog_part_terms_name", "name_es"),
        Index("ix_catalog_part_terms_system", "system"),
    )
    part_id: Mapped[int] = mapped_column(ForeignKey("catalog_parts.id"), primary_key=True)
    source_key: Mapped[str] = mapped_column(String(60), primary_key=True)
    name_es: Mapped[str] = mapped_column(String(200))
    system: Mapped[str | None] = mapped_column(String(40))
    synonyms: Mapped[list | None] = mapped_column(JSON, nullable=True)
    keywords: Mapped[list | None] = mapped_column(JSON, nullable=True)
    review_required: Mapped[bool] = mapped_column(Boolean)
    translated_by: Mapped[str] = mapped_column(String(40))
    translated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CatalogAlias(Base):
    """Alias verificados. Evitan crear fabricantes duplicados por el nombre."""

    __tablename__ = "catalog_aliases"
    __table_args__ = (
        CheckConstraint(f"entity_type IN {ENTITY_TYPES!r}", name="catalog_alias_entity"),
        Index("ix_catalog_aliases_entity", "entity_type", "entity_id"),
        Index("ix_catalog_aliases_normalized", "normalized"),
    )
    alias: Mapped[str] = mapped_column(String(120), primary_key=True)
    normalized: Mapped[str] = mapped_column(String(120))
    entity_type: Mapped[str] = mapped_column(String(20))
    entity_id: Mapped[int] = mapped_column(Integer)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    source_key: Mapped[str | None] = mapped_column(String(60))
