"""Pausa de entregas sin canal o destinatario disponible; no borra mensajes."""
from alembic import op
import sqlalchemy as sa

revision = '0012'
down_revision = '0011'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('notifications', sa.Column('blocked_reason', sa.String(250), nullable=True))


def downgrade():
    raise RuntimeError('Restaure el respaldo previo en otra base; no se eliminan estados de entrega en producción')
