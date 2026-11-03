"""vehicle_catalog_and_vector_search"""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    postgres = bind.dialect.name == 'postgresql'

    # Sin pgvector la tabla sigue siendo utilizable: el vector cae a BYTEA.
    if postgres:
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
        op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # La unicidad de `slug`/`sku` se declara UNA sola vez, como índice único
    # (`op.create_index(..., unique=True)`). Declarar además un
    # `UniqueConstraint` sobre la misma columna generaba un segundo índice
    # redundante que `alembic check` reportaba como deriva permanente.

    op.create_table('catalog_sources',
    sa.Column('source_key', sa.String(length=60), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('url', sa.String(length=300), nullable=False),
    sa.Column('license', sa.String(length=60), nullable=False),
    sa.Column('license_url', sa.String(length=300), nullable=False),
    sa.Column('attribution', sa.Text(), nullable=False),
    sa.Column('row_count', sa.Integer(), nullable=False),
    sa.Column('content_hash', sa.String(length=64), nullable=False),
    sa.Column('fetched_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('source_key')
    )
    op.create_table('catalog_makes',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('slug', sa.String(length=80), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('country', sa.String(length=80), nullable=True),
    sa.Column('logo_url', sa.String(length=400), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_catalog_makes_slug'), 'catalog_makes', ['slug'], unique=True)
    op.create_table('catalog_models',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('make_id', sa.Integer(), nullable=False),
    sa.Column('slug', sa.String(length=160), nullable=False),
    sa.Column('name', sa.String(length=160), nullable=False),
    sa.Column('year_start', sa.Integer(), nullable=True),
    sa.Column('year_end', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['make_id'], ['catalog_makes.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_catalog_models_make_id'), 'catalog_models', ['make_id'], unique=False)
    op.create_index(op.f('ix_catalog_models_slug'), 'catalog_models', ['slug'], unique=True)
    op.create_table('catalog_generations',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('model_id', sa.Integer(), nullable=False),
    sa.Column('slug', sa.String(length=200), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('year_start', sa.Integer(), nullable=True),
    sa.Column('year_end', sa.Integer(), nullable=True),
    sa.Column('body_type', sa.String(length=80), nullable=True),
    sa.ForeignKeyConstraint(['model_id'], ['catalog_models.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_catalog_generations_model_id'), 'catalog_generations', ['model_id'], unique=False)
    op.create_index(op.f('ix_catalog_generations_slug'), 'catalog_generations', ['slug'], unique=True)
    op.create_table('catalog_engines',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('generation_id', sa.Integer(), nullable=False),
    sa.Column('slug', sa.String(length=240), nullable=False),
    sa.Column('label', sa.String(length=240), nullable=False),
    sa.Column('fuel_type', sa.String(length=80), nullable=True),
    sa.Column('cylinders', sa.Integer(), nullable=True),
    sa.Column('displacement_cc', sa.Float(), nullable=True),
    sa.Column('power_hp', sa.Float(), nullable=True),
    sa.Column('torque_nm', sa.Float(), nullable=True),
    sa.Column('transmission', sa.String(length=80), nullable=True),
    sa.Column('drivetrain', sa.String(length=80), nullable=True),
    sa.Column('zero_to_100_s', sa.Float(), nullable=True),
    sa.Column('top_speed_kmh', sa.Float(), nullable=True),
    sa.Column('fuel_economy_l100', sa.Float(), nullable=True),
    sa.Column('length_mm', sa.Float(), nullable=True),
    sa.Column('width_mm', sa.Float(), nullable=True),
    sa.Column('height_mm', sa.Float(), nullable=True),
    sa.Column('wheelbase_mm', sa.Float(), nullable=True),
    sa.Column('curb_weight_kg', sa.Float(), nullable=True),
    sa.ForeignKeyConstraint(['generation_id'], ['catalog_generations.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_catalog_engines_generation_id'), 'catalog_engines', ['generation_id'], unique=False)
    op.create_index(op.f('ix_catalog_engines_slug'), 'catalog_engines', ['slug'], unique=True)
    op.create_table('catalog_engine_specs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('engine_id', sa.Integer(), nullable=False),
    sa.Column('key', sa.String(length=160), nullable=False),
    sa.Column('value', sa.Text(), nullable=False),
    sa.ForeignKeyConstraint(['engine_id'], ['catalog_engines.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_catalog_engine_specs_engine_id'), 'catalog_engine_specs', ['engine_id'], unique=False)
    op.create_index('ix_engine_specs_engine_key', 'catalog_engine_specs', ['engine_id', 'key'], unique=False)
    op.create_table('catalog_parts',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('sku', sa.String(length=80), nullable=False),
    sa.Column('mpn', sa.String(length=80), nullable=True),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('brand', sa.String(length=120), nullable=True),
    sa.Column('category', sa.String(length=120), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_catalog_parts_sku'), 'catalog_parts', ['sku'], unique=True)
    op.create_index(op.f('ix_catalog_parts_brand'), 'catalog_parts', ['brand'], unique=False)
    op.create_index(op.f('ix_catalog_parts_category'), 'catalog_parts', ['category'], unique=False)
    op.create_table('catalog_part_fits',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('part_id', sa.Integer(), nullable=False),
    sa.Column('model_id', sa.Integer(), nullable=True),
    sa.Column('source_key', sa.String(length=120), nullable=False),
    sa.Column('year_from', sa.Integer(), nullable=True),
    sa.Column('year_to', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['model_id'], ['catalog_models.id'], ),
    sa.ForeignKeyConstraint(['part_id'], ['catalog_parts.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('part_id', 'source_key', 'model_id', name='part_fit')
    )
    op.create_index(op.f('ix_catalog_part_fits_model_id'), 'catalog_part_fits', ['model_id'], unique=False)
    op.create_index(op.f('ix_catalog_part_fits_part_id'), 'catalog_part_fits', ['part_id'], unique=False)
    op.create_index(op.f('ix_catalog_part_fits_source_key'), 'catalog_part_fits', ['source_key'], unique=False)

    embeddings = op.create_table('catalog_embeddings',
    sa.Column('entity_type', sa.String(length=20), nullable=False),
    sa.Column('entity_id', sa.Integer(), nullable=False),
    sa.Column('model_key', sa.String(length=80), nullable=False),
    sa.Column('vector', Vector(384) if postgres else sa.LargeBinary(), nullable=False),
    sa.PrimaryKeyConstraint('entity_type', 'entity_id')
    )
    op.create_index('ix_catalog_embeddings_model', 'catalog_embeddings', ['model_key'], unique=False)

    if postgres:
        # Búsqueda por vecinos más cercanos sobre el catálogo indexado.
        op.execute(
            "CREATE INDEX ix_catalog_embeddings_hnsw ON catalog_embeddings "
            "USING hnsw (vector vector_cosine_ops)"
        )
        # Búsqueda textual difusa para consultas exactas o con acentos.
        op.execute("CREATE INDEX ix_catalog_makes_trgm ON catalog_makes USING gin (name gin_trgm_ops)")
        op.execute("CREATE INDEX ix_catalog_models_trgm ON catalog_models USING gin (name gin_trgm_ops)")
        op.execute("CREATE INDEX ix_catalog_parts_trgm ON catalog_parts USING gin (title gin_trgm_ops)")


def downgrade():
    op.drop_table('catalog_embeddings')
    op.drop_index(op.f('ix_catalog_part_fits_source_key'), table_name='catalog_part_fits')
    op.drop_index(op.f('ix_catalog_part_fits_part_id'), table_name='catalog_part_fits')
    op.drop_index(op.f('ix_catalog_part_fits_model_id'), table_name='catalog_part_fits')
    op.drop_table('catalog_part_fits')
    op.drop_index(op.f('ix_catalog_parts_category'), table_name='catalog_parts')
    op.drop_index(op.f('ix_catalog_parts_brand'), table_name='catalog_parts')
    op.drop_index(op.f('ix_catalog_parts_sku'), table_name='catalog_parts')
    op.drop_table('catalog_parts')
    op.drop_index('ix_engine_specs_engine_key', table_name='catalog_engine_specs')
    op.drop_index(op.f('ix_catalog_engine_specs_engine_id'), table_name='catalog_engine_specs')
    op.drop_table('catalog_engine_specs')
    op.drop_index(op.f('ix_catalog_engines_slug'), table_name='catalog_engines')
    op.drop_index(op.f('ix_catalog_engines_generation_id'), table_name='catalog_engines')
    op.drop_table('catalog_engines')
    op.drop_index(op.f('ix_catalog_generations_slug'), table_name='catalog_generations')
    op.drop_index(op.f('ix_catalog_generations_model_id'), table_name='catalog_generations')
    op.drop_table('catalog_generations')
    op.drop_index(op.f('ix_catalog_models_slug'), table_name='catalog_models')
    op.drop_index(op.f('ix_catalog_models_make_id'), table_name='catalog_models')
    op.drop_table('catalog_models')
    op.drop_index(op.f('ix_catalog_makes_slug'), table_name='catalog_makes')
    op.drop_table('catalog_makes')
    op.drop_table('catalog_sources')