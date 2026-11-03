"""Motor opcional y revisión auditable de propuestas manuales.

Solo añade columnas; no cambia las referencias, textos ni estados existentes.
"""
from alembic import op
import sqlalchemy as sa

revision = '0009'
down_revision = '0008'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('vehicles', sa.Column('catalog_engine_id', sa.Integer(), nullable=True))
    op.create_foreign_key('vehicles_catalog_engine_id_fkey', 'vehicles',
                          'catalog_engines', ['catalog_engine_id'], ['id'],
                          ondelete='SET NULL')
    op.add_column('catalog_record_meta', sa.Column('revision', sa.Integer(),
                                                 nullable=False, server_default='1'))
    op.add_column('catalog_record_meta', sa.Column('reviewed_by', sa.Integer(), nullable=True))
    op.add_column('catalog_record_meta', sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('catalog_record_meta', sa.Column('review_note', sa.String(1000),
                                                 nullable=False, server_default=''))
    op.create_foreign_key('catalog_record_meta_reviewed_by_fkey', 'catalog_record_meta',
                          'users', ['reviewed_by'], ['id'], ondelete='SET NULL')


def downgrade():
    op.drop_constraint('catalog_record_meta_reviewed_by_fkey', 'catalog_record_meta', type_='foreignkey')
    for column in ('review_note', 'reviewed_at', 'reviewed_by', 'revision'):
        op.drop_column('catalog_record_meta', column)
    op.drop_constraint('vehicles_catalog_engine_id_fkey', 'vehicles', type_='foreignkey')
    op.drop_column('vehicles', 'catalog_engine_id')
