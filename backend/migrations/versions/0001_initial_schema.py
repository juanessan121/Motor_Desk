"""initial_schema"""
from alembic import op
import sqlalchemy as sa


revision = '0001'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('maintenance_catalogs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=150), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('base_price', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('active', sa.Boolean(), nullable=False),
    sa.CheckConstraint('base_price >= 0', name='catalog_price'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('users',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('username', sa.String(length=100), nullable=False),
    sa.Column('email', sa.String(length=254), nullable=False),
    sa.Column('password_hash', sa.Text(), nullable=False),
    sa.Column('role', sa.String(length=20), nullable=False),
    sa.Column('active', sa.Boolean(), nullable=False),
    sa.Column('must_change_password', sa.Boolean(), nullable=False),
    sa.Column('token_version', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("role IN ('admin','mechanic','customer')", name='user_role'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('email'),
    sa.UniqueConstraint('username')
    )
    op.create_table('app_configurations',
    sa.Column('scope', sa.String(length=100), nullable=False),
    sa.Column('payload', sa.JSON(), nullable=False),
    sa.Column('revision', sa.Integer(), nullable=False),
    sa.Column('updated_by', sa.Integer(), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('scope')
    )
    op.create_table('catalog_tasks',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('catalog_id', sa.Integer(), nullable=False),
    sa.Column('label', sa.String(length=250), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['catalog_id'], ['maintenance_catalogs.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('customers',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('national_id', sa.String(length=40), nullable=False),
    sa.Column('first_name', sa.String(length=100), nullable=False),
    sa.Column('last_name', sa.String(length=100), nullable=False),
    sa.Column('address', sa.String(length=300), nullable=False),
    sa.Column('phone', sa.String(length=40), nullable=False),
    sa.Column('email', sa.String(length=254), nullable=False),
    sa.Column('telegram_chat_id', sa.String(length=40), nullable=True),
    sa.Column('notification_channel', sa.String(length=20), nullable=False),
    sa.Column('active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("notification_channel IN ('email','telegram')", name='customer_channel'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('email'),
    sa.UniqueConstraint('national_id'),
    sa.UniqueConstraint('user_id')
    )
    op.create_table('devices',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('device_key', sa.String(length=36), nullable=False),
    sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'device_key', name='user_device')
    )
    with op.batch_alter_table('devices', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_devices_user_id'), ['user_id'], unique=False)

    op.create_table('notifications',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('kind', sa.String(length=50), nullable=False),
    sa.Column('channel', sa.String(length=20), nullable=False),
    sa.Column('encrypted_payload', sa.Text(), nullable=True),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('attempts', sa.Integer(), nullable=False),
    sa.Column('next_attempt_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('last_error', sa.String(length=250), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("status IN ('pending','sent','failed')", name='notification_status'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('notifications', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_notifications_user_id'), ['user_id'], unique=False)
        batch_op.create_index('notification_due', ['status', 'next_attempt_at'], unique=False)

    op.create_table('vehicles',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('owner_id', sa.Integer(), nullable=False),
    sa.Column('plate', sa.String(length=20), nullable=False),
    sa.Column('vin', sa.String(length=40), nullable=True),
    sa.Column('brand', sa.String(length=80), nullable=False),
    sa.Column('model', sa.String(length=100), nullable=False),
    sa.Column('year', sa.Integer(), nullable=False),
    sa.Column('mileage', sa.Integer(), nullable=False),
    sa.Column('active', sa.Boolean(), nullable=False),
    sa.CheckConstraint('mileage >= 0', name='vehicle_mileage'),
    sa.CheckConstraint('year >= 1900 AND year <= 2200', name='vehicle_year'),
    sa.ForeignKeyConstraint(['owner_id'], ['customers.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('plate'),
    sa.UniqueConstraint('vin')
    )
    with op.batch_alter_table('vehicles', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_vehicles_owner_id'), ['owner_id'], unique=False)

    op.create_table('ownership_history',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('vehicle_id', sa.Integer(), nullable=False),
    sa.Column('previous_owner_id', sa.Integer(), nullable=True),
    sa.Column('new_owner_id', sa.Integer(), nullable=False),
    sa.Column('changed_by', sa.Integer(), nullable=False),
    sa.Column('changed_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['changed_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['new_owner_id'], ['customers.id'], ),
    sa.ForeignKeyConstraint(['previous_owner_id'], ['customers.id'], ),
    sa.ForeignKeyConstraint(['vehicle_id'], ['vehicles.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('ownership_history', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_ownership_history_vehicle_id'), ['vehicle_id'], unique=False)

    op.create_table('work_orders',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('vehicle_id', sa.Integer(), nullable=False),
    sa.Column('customer_id', sa.Integer(), nullable=False),
    sa.Column('catalog_id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=150), nullable=False),
    sa.Column('payer_snapshot', sa.JSON(), nullable=False),
    sa.Column('base_total', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('notes', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('ready_notified_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("status IN ('in_progress','ready','delivered','cancelled')", name='order_status'),
    sa.CheckConstraint('base_total >= 0', name='order_total'),
    sa.ForeignKeyConstraint(['catalog_id'], ['maintenance_catalogs.id'], ),
    sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ),
    sa.ForeignKeyConstraint(['vehicle_id'], ['vehicles.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('work_orders', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_work_orders_customer_id'), ['customer_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_work_orders_vehicle_id'), ['vehicle_id'], unique=False)

    op.create_table('extra_quotes',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('order_id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('decision', sa.String(length=20), nullable=False),
    sa.Column('selected_option_id', sa.Integer(), nullable=True),
    sa.Column('decided_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("decision IN ('pending','approved','rejected')", name='quote_decision'),
    sa.ForeignKeyConstraint(['order_id'], ['work_orders.id'], ),
    sa.ForeignKeyConstraint(['selected_option_id'], ['quote_options.id'], name='fk_selected_option', use_alter=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('inbox_events',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('body', sa.Text(), nullable=False),
    sa.Column('order_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['order_id'], ['work_orders.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('inbox_events', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_inbox_events_user_id'), ['user_id'], unique=False)

    op.create_table('intake_photos',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('order_id', sa.Integer(), nullable=False),
    sa.Column('uploaded_by', sa.Integer(), nullable=False),
    sa.Column('caption', sa.String(length=250), nullable=False),
    sa.Column('content', sa.LargeBinary(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['order_id'], ['work_orders.id'], ),
    sa.ForeignKeyConstraint(['uploaded_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('checklist_items',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('order_id', sa.Integer(), nullable=False),
    sa.Column('quote_id', sa.Integer(), nullable=True),
    sa.Column('label', sa.String(length=350), nullable=False),
    sa.Column('completed', sa.Boolean(), nullable=False),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('completed_by', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['completed_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['order_id'], ['work_orders.id'], ),
    sa.ForeignKeyConstraint(['quote_id'], ['extra_quotes.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('quote_id')
    )
    op.create_table('quote_options',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('quote_id', sa.Integer(), nullable=False),
    sa.Column('label', sa.String(length=150), nullable=False),
    sa.Column('price', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.CheckConstraint('price >= 0', name='option_price'),
    sa.ForeignKeyConstraint(['quote_id'], ['extra_quotes.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    if op.get_bind().dialect.name != 'sqlite':
        op.create_foreign_key('fk_selected_option', 'extra_quotes', 'quote_options', ['selected_option_id'], ['id'])

def downgrade():
    if op.get_bind().dialect.name != 'sqlite':
        op.drop_constraint('fk_selected_option', 'extra_quotes', type_='foreignkey')
    op.drop_table('quote_options')
    op.drop_table('checklist_items')
    op.drop_table('intake_photos')
    with op.batch_alter_table('inbox_events', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_inbox_events_user_id'))

    op.drop_table('inbox_events')
    op.drop_table('extra_quotes')
    with op.batch_alter_table('work_orders', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_work_orders_vehicle_id'))
        batch_op.drop_index(batch_op.f('ix_work_orders_customer_id'))

    op.drop_table('work_orders')
    with op.batch_alter_table('ownership_history', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_ownership_history_vehicle_id'))

    op.drop_table('ownership_history')
    with op.batch_alter_table('vehicles', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_vehicles_owner_id'))

    op.drop_table('vehicles')
    with op.batch_alter_table('notifications', schema=None) as batch_op:
        batch_op.drop_index('notification_due')
        batch_op.drop_index(batch_op.f('ix_notifications_user_id'))

    op.drop_table('notifications')
    with op.batch_alter_table('devices', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_devices_user_id'))

    op.drop_table('devices')
    op.drop_table('customers')
    op.drop_table('catalog_tasks')
    op.drop_table('app_configurations')
    op.drop_table('users')
    op.drop_table('maintenance_catalogs')
