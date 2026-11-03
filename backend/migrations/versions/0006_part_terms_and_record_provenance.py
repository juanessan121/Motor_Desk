"""part_terms_and_record_provenance

Capa de enriquecimiento en español y trazabilidad por registro.

`catalog_parts` (0004) guarda el nombre original de la fuente y un `category`
que en realidad era el título en minúsculas: no había traducción, ni sistema
mecánico, ni sinónimos, ni procedencia por registro. Esta revisión lo resuelve
sin tocar ninguna tabla existente ni ninguna de las 25 del taller.
"""
from alembic import op
import sqlalchemy as sa

revision = '0006'
down_revision = '0005'
branch_labels = None
depends_on = None

ENTITY_TYPES = ('make', 'model', 'generation', 'engine', 'part')
ORIGINS = ('imported', 'manual', 'verified', 'needs_review')


def upgrade():
    # Procedencia por registro: qué fuente lo trajo, quién lo añadió, cuándo y
    # si está pendiente de revisión. Sin esto no se puede distinguir un dato
    # corregido a mano de uno importado, ni protegerlo en la siguiente
    # importación.
    op.create_table(
        'catalog_record_meta',
        sa.Column('entity_type', sa.String(length=20), nullable=False),
        sa.Column('entity_id', sa.Integer(), nullable=False),
        sa.Column('source_key', sa.String(length=60), nullable=False),
        sa.Column('origin', sa.String(length=20), nullable=False),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('entity_type', 'entity_id'),
        sa.CheckConstraint(
            "entity_type IN ('make','model','generation','engine','part')",
            name='catalog_meta_entity'),
        sa.CheckConstraint(
            "origin IN ('imported','manual','verified','needs_review')",
            name='catalog_meta_origin'),
    )
    op.create_index('ix_catalog_record_meta_source', 'catalog_record_meta',
                    ['source_key'], unique=False)
    op.create_index('ix_catalog_record_meta_origin', 'catalog_record_meta',
                    ['origin'], unique=False)

    # Traducción al español, sistema mecánico, sinónimos y palabras clave.
    # `review_required` marca lo que el glosario no pudo resolver con respaldo:
    # la interfaz lo muestra como pendiente, nunca como verificado.
    op.create_table(
        'catalog_part_terms',
        sa.Column('part_id', sa.Integer(), nullable=False),
        sa.Column('source_key', sa.String(length=60), nullable=False),
        sa.Column('name_es', sa.String(length=200), nullable=False),
        sa.Column('system', sa.String(length=40), nullable=True),
        sa.Column('synonyms', sa.JSON(), nullable=True),
        sa.Column('keywords', sa.JSON(), nullable=True),
        sa.Column('review_required', sa.Boolean(), nullable=False),
        sa.Column('translated_by', sa.String(length=40), nullable=False),
        sa.Column('translated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['part_id'], ['catalog_parts.id'], ),
        sa.PrimaryKeyConstraint('part_id', 'source_key'),
    )
    op.create_index('ix_catalog_part_terms_name', 'catalog_part_terms',
                    ['name_es'], unique=False)
    op.create_index('ix_catalog_part_terms_system', 'catalog_part_terms',
                    ['system'], unique=False)

    # Alias verificados: permiten que "chevrolet" encuentre "Chevrolet" sin
    # crear fabricantes duplicados. `verified` distingue el alias comprobado
    # del que una persona propose y aún no se ha contrastado.
    op.create_table(
        'catalog_aliases',
        sa.Column('alias', sa.String(length=120), nullable=False),
        sa.Column('normalized', sa.String(length=120), nullable=False),
        sa.Column('entity_type', sa.String(length=20), nullable=False),
        sa.Column('entity_id', sa.Integer(), nullable=False),
        sa.Column('verified', sa.Boolean(), nullable=False),
        sa.Column('source_key', sa.String(length=60), nullable=True),
        sa.PrimaryKeyConstraint('alias'),
        sa.CheckConstraint(
            "entity_type IN ('make','model','generation','engine','part')",
            name='catalog_alias_entity'),
    )
    op.create_index('ix_catalog_aliases_entity', 'catalog_aliases',
                    ['entity_type', 'entity_id'], unique=False)
    op.create_index('ix_catalog_aliases_normalized', 'catalog_aliases',
                    ['normalized'], unique=False)


def downgrade():
    op.drop_table('catalog_aliases')
    op.drop_table('catalog_part_terms')
    op.drop_table('catalog_record_meta')