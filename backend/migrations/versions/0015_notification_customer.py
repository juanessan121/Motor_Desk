"""Business notifications do not require a portal account."""
from alembic import op
import sqlalchemy as sa

revision = '0015'
down_revision = '0014'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('notifications', sa.Column('customer_id', sa.Integer(), nullable=True))
    op.create_foreign_key('notification_customer_fk', 'notifications', 'customers', ['customer_id'], ['id'])
    op.create_index('ix_notifications_customer_id', 'notifications', ['customer_id'])
    op.alter_column('notifications', 'user_id', existing_type=sa.Integer(), nullable=True)
    op.execute('UPDATE notifications SET customer_id = customers.id FROM customers WHERE customers.user_id = notifications.user_id')


def downgrade():
    raise RuntimeError('No se eliminan mensajes de clientes sin cuenta; restaure una copia compatible.')
