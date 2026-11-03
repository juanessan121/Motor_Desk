"""record_meta_created_by_fk

`alembic check` detectó que `catalog_record_meta.created_by` estaba declarada
como entero en 0006 pero el modelo la declara como ForeignKey a `users.id`.
El dato no se pierde ni se reescribe: se añade la integridad referencial que
el modelo promete.
"""
from alembic import op
import sqlalchemy as sa

revision = '0007'
down_revision = '0006'
branch_labels = None
depends_on = None


def upgrade():
    op.create_foreign_key(
        'catalog_record_meta_created_by_fkey', 'catalog_record_meta', 'users',
        ['created_by'], ['id'])


def downgrade():
    op.drop_constraint('catalog_record_meta_created_by_fkey', 'catalog_record_meta',
                       type_='foreignkey')