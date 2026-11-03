"""Actividades reutilizables, activación de acceso, trazabilidad académica y retirada no destructiva de avisos."""
from alembic import op
import sqlalchemy as sa

revision = '0013'
down_revision = '0012'
branch_labels = None
depends_on = None


def upgrade():
    # Clientes: medios de notificación individuales, whatsapp y usuario opcional
    op.add_column('customers', sa.Column('whatsapp', sa.String(40), nullable=False, server_default=''))
    op.add_column('customers', sa.Column('notifications_enabled', sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column('customers', sa.Column('email_notifications_enabled', sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column('customers', sa.Column('telegram_notifications_enabled', sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column('customers', sa.Column('whatsapp_notifications_enabled', sa.Boolean(), nullable=False, server_default=sa.true()))
    op.alter_column('customers', 'user_id', existing_type=sa.Integer(), nullable=True)

    # Actualizar restricción de canales para permitir whatsapp
    with op.batch_alter_table('customers') as batch_op:
        try:
            batch_op.drop_constraint('customer_channel', type_='check')
        except Exception:
            pass
        batch_op.create_check_constraint('customer_channel', "notification_channel IN ('email','telegram','whatsapp')")

    # Vehículos: color y tipo de combustible
    op.add_column('vehicles', sa.Column('color', sa.String(40), nullable=False, server_default=''))
    op.add_column('vehicles', sa.Column('fuel_type', sa.String(40), nullable=False, server_default='gasolina'))

    # Órdenes de trabajo: campos académicos y cálculo transparente
    op.add_column('work_orders', sa.Column('order_code', sa.String(40), nullable=True))
    op.add_column('work_orders', sa.Column('maintenance_type', sa.String(40), nullable=False, server_default='preventivo'))
    op.add_column('work_orders', sa.Column('problem_description', sa.Text(), nullable=False, server_default=''))
    op.add_column('work_orders', sa.Column('technical_diagnosis', sa.Text(), nullable=False, server_default=''))
    op.add_column('work_orders', sa.Column('labor_cost', sa.Numeric(12, 2), nullable=True))
    op.add_column('work_orders', sa.Column('parts_cost', sa.Numeric(12, 2), nullable=True))
    op.add_column('work_orders', sa.Column('tax_rate', sa.Numeric(5, 4), nullable=False, server_default='0.15'))
    op.add_column('work_orders', sa.Column('tax_amount', sa.Numeric(12, 2), nullable=True))
    op.add_column('work_orders', sa.Column('total_amount', sa.Numeric(12, 2), nullable=True))
    op.add_column('work_orders', sa.Column('delay_reason', sa.Text(), nullable=True))
    op.add_column('work_orders', sa.Column('estimated_delivery_date', sa.DateTime(timezone=True), nullable=True))
    op.add_column('work_orders', sa.Column('delivered_at', sa.DateTime(timezone=True), nullable=True))

    # Notificaciones: archivo y relación con orden
    op.add_column('notifications', sa.Column('order_id', sa.Integer(), sa.ForeignKey('work_orders.id'), nullable=True))
    op.add_column('notifications', sa.Column('archived_at', sa.DateTime(timezone=True)))
    op.add_column('notifications', sa.Column('archived_by', sa.Integer(), sa.ForeignKey('users.id')))

    op.alter_column('findings', 'x', existing_type=sa.Numeric(10, 8), nullable=True)
    op.alter_column('findings', 'y', existing_type=sa.Numeric(10, 8), nullable=True)

    # Catálogo central de actividades reutilizables
    op.create_table('maintenance_activities',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('workshop_id', sa.Integer(), sa.ForeignKey('workshops.id'), nullable=False),
        sa.Column('label', sa.String(250), nullable=False),
        sa.Column('normalized_label', sa.String(250), nullable=False),
        sa.Column('description', sa.Text(), nullable=False, server_default=''),
        sa.Column('system', sa.String(80), nullable=False, server_default='general'),
        sa.Column('technical_notes', sa.Text(), nullable=False, server_default=''),
        sa.Column('required', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('estimated_minutes', sa.Integer()),
        sa.Column('suggested_part_ids', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('revision', sa.Integer(), nullable=False, server_default='1'),
        sa.UniqueConstraint('workshop_id', 'normalized_label', name='uq_maintenance_activity'))
    op.create_index('ix_maintenance_activities_workshop_id', 'maintenance_activities', ['workshop_id'])

    op.add_column('catalog_tasks', sa.Column('activity_id', sa.Integer(), sa.ForeignKey('maintenance_activities.id')))
    op.add_column('catalog_tasks', sa.Column('system', sa.String(80), nullable=False, server_default='general'))
    op.add_column('catalog_tasks', sa.Column('technical_notes', sa.Text(), nullable=False, server_default=''))

    # Tokens de activación y recuperación de acceso de clientes
    op.create_table('customer_access_grants',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('token_hash', sa.String(64), nullable=False, unique=True),
        sa.Column('token_version', sa.Integer(), nullable=False),
        sa.Column('created_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('consumed_at', sa.DateTime(timezone=True)))
    op.create_index('ix_customer_access_grants_user_id', 'customer_access_grants', ['user_id'])


def downgrade():
    raise RuntimeError('Recuperación mediante respaldo en otra base; no se elimina historial operativo')
