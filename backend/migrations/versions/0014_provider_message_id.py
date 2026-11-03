"""Identificador de entrega externa confirmada."""
from alembic import op
import sqlalchemy as sa
revision = '0014'
down_revision = '0013'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('notifications', sa.Column('provider_message_id', sa.String(200), nullable=True))


def downgrade():
    raise RuntimeError('Restaure un respaldo en otra base; no elimine trazabilidad de envíos')
