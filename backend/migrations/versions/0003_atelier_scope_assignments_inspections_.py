"""atelier_scope_assignments_inspections_bays"""
from alembic import op
import sqlalchemy as sa
import json


revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('workshops',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('layout_revision', sa.Integer(), server_default='1', nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    payload = op.get_bind().execute(sa.text("SELECT payload FROM app_configurations WHERE scope='global'")).scalar()
    if isinstance(payload, str):
        payload = json.loads(payload)
    name = (payload or {}).get('branding', {}).get('name', 'MotorDesk')
    op.bulk_insert(sa.table('workshops', sa.column('id', sa.Integer), sa.column('name', sa.String), sa.column('layout_revision', sa.Integer)),
        [{'id': 1, 'name': name, 'layout_revision': 1}])
    if op.get_bind().dialect.name == 'postgresql':
        op.execute("SELECT setval(pg_get_serial_sequence('workshops','id'), 1, true)")
    op.create_table('workshop_zones',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('workshop_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('kind', sa.String(length=80), nullable=False),
    sa.Column('capacity', sa.Integer(), nullable=False),
    sa.Column('x', sa.Numeric(precision=10, scale=8), nullable=False),
    sa.Column('y', sa.Numeric(precision=10, scale=8), nullable=False),
    sa.Column('width', sa.Numeric(precision=10, scale=8), nullable=False),
    sa.Column('height', sa.Numeric(precision=10, scale=8), nullable=False),
    sa.Column('revision', sa.Integer(), nullable=False),
    sa.Column('active', sa.Boolean(), nullable=False),
    sa.CheckConstraint('capacity > 0', name='zone_capacity'),
    sa.ForeignKeyConstraint(['workshop_id'], ['workshops.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_workshop_zones_workshop_id'), 'workshop_zones', ['workshop_id'], unique=False)
    op.create_table('audit_events',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('workshop_id', sa.Integer(), nullable=False),
    sa.Column('actor_id', sa.Integer(), nullable=False),
    sa.Column('action', sa.String(length=80), nullable=False),
    sa.Column('resource_type', sa.String(length=40), nullable=False),
    sa.Column('resource_id', sa.Integer(), nullable=False),
    sa.Column('payload', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['actor_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['workshop_id'], ['workshops.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_audit_events_resource_id'), 'audit_events', ['resource_id'], unique=False)
    op.create_index(op.f('ix_audit_events_workshop_id'), 'audit_events', ['workshop_id'], unique=False)
    op.create_table('workshop_bays',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('workshop_id', sa.Integer(), nullable=False),
    sa.Column('zone_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('kind', sa.String(length=80), nullable=False),
    sa.Column('capacity', sa.Integer(), nullable=False),
    sa.Column('x', sa.Numeric(precision=10, scale=8), nullable=False),
    sa.Column('y', sa.Numeric(precision=10, scale=8), nullable=False),
    sa.Column('width', sa.Numeric(precision=10, scale=8), nullable=False),
    sa.Column('height', sa.Numeric(precision=10, scale=8), nullable=False),
    sa.Column('revision', sa.Integer(), nullable=False),
    sa.Column('active', sa.Boolean(), nullable=False),
    sa.CheckConstraint('capacity > 0', name='bay_capacity'),
    sa.ForeignKeyConstraint(['workshop_id'], ['workshops.id'], ),
    sa.ForeignKeyConstraint(['zone_id'], ['workshop_zones.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_workshop_bays_workshop_id'), 'workshop_bays', ['workshop_id'], unique=False)
    op.create_index(op.f('ix_workshop_bays_zone_id'), 'workshop_bays', ['zone_id'], unique=False)
    op.create_table('bay_occupancies',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('order_id', sa.Integer(), nullable=False),
    sa.Column('bay_id', sa.Integer(), nullable=False),
    sa.Column('entered_by', sa.Integer(), nullable=False),
    sa.Column('entered_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('exited_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('exited_by', sa.Integer(), nullable=True),
    sa.Column('reason', sa.String(length=250), nullable=False),
    sa.ForeignKeyConstraint(['bay_id'], ['workshop_bays.id'], ),
    sa.ForeignKeyConstraint(['entered_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['exited_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['order_id'], ['work_orders.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_bay_occupancies_bay_id'), 'bay_occupancies', ['bay_id'], unique=False)
    op.create_index(op.f('ix_bay_occupancies_order_id'), 'bay_occupancies', ['order_id'], unique=False)
    op.create_index('one_current_location', 'bay_occupancies', ['order_id'], unique=True, postgresql_where=sa.text('exited_at IS NULL'), sqlite_where=sa.text('exited_at IS NULL'))
    op.create_table('work_assignments',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('order_id', sa.Integer(), nullable=False),
    sa.Column('mechanic_id', sa.Integer(), nullable=False),
    sa.Column('task_ids', sa.JSON(), nullable=False),
    sa.Column('can_quote', sa.Boolean(), nullable=False),
    sa.Column('assigned_by', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('revision', sa.Integer(), nullable=False),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('revoked_by', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['assigned_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['mechanic_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['order_id'], ['work_orders.id'], ),
    sa.ForeignKeyConstraint(['revoked_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_work_assignments_mechanic_id'), 'work_assignments', ['mechanic_id'], unique=False)
    op.create_index(op.f('ix_work_assignments_order_id'), 'work_assignments', ['order_id'], unique=False)
    op.create_index('one_active_assignment', 'work_assignments', ['order_id', 'mechanic_id'], unique=True, postgresql_where=sa.text('revoked_at IS NULL'), sqlite_where=sa.text('revoked_at IS NULL'))
    op.create_table('inspections',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('order_id', sa.Integer(), nullable=False),
    sa.Column('vehicle_id', sa.Integer(), nullable=False),
    sa.Column('task_id', sa.Integer(), nullable=True),
    sa.Column('title', sa.String(length=150), nullable=False),
    sa.Column('template_id', sa.String(length=80), nullable=False),
    sa.Column('created_by', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('revision', sa.Integer(), nullable=False),
    sa.Column('review_status', sa.String(length=20), nullable=False),
    sa.Column('reviewed_by', sa.Integer(), nullable=True),
    sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('published_snapshot', sa.JSON(), nullable=True),
    sa.Column('published_revision', sa.Integer(), nullable=True),
    sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('published_by', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['order_id'], ['work_orders.id'], ),
    sa.ForeignKeyConstraint(['published_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['reviewed_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['task_id'], ['checklist_items.id'], ),
    sa.ForeignKeyConstraint(['vehicle_id'], ['vehicles.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_inspections_order_id'), 'inspections', ['order_id'], unique=False)
    op.create_index(op.f('ix_inspections_vehicle_id'), 'inspections', ['vehicle_id'], unique=False)
    op.create_table('findings',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('inspection_id', sa.Integer(), nullable=False),
    sa.Column('component_id', sa.String(length=80), nullable=False),
    sa.Column('view_id', sa.String(length=80), nullable=False),
    sa.Column('x', sa.Numeric(precision=10, scale=8), nullable=False),
    sa.Column('y', sa.Numeric(precision=10, scale=8), nullable=False),
    sa.Column('polygon', sa.JSON(), nullable=True),
    sa.Column('category', sa.String(length=80), nullable=False),
    sa.Column('severity', sa.String(length=30), nullable=False),
    sa.Column('condition', sa.String(length=20), nullable=False),
    sa.Column('note', sa.Text(), nullable=False),
    sa.Column('created_by', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('active', sa.Boolean(), nullable=False),
    sa.CheckConstraint("condition IN ('no_data','normal','follow_up','issue')", name='finding_condition'),
    sa.CheckConstraint('x >= 0 AND x <= 1 AND y >= 0 AND y <= 1', name='finding_coordinates'),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['inspection_id'], ['inspections.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_findings_inspection_id'), 'findings', ['inspection_id'], unique=False)
    op.create_table('inspection_revisions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('inspection_id', sa.Integer(), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('actor_id', sa.Integer(), nullable=False),
    sa.Column('snapshot', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['actor_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['inspection_id'], ['inspections.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('inspection_id', 'version', name='inspection_version')
    )
    op.create_index(op.f('ix_inspection_revisions_inspection_id'), 'inspection_revisions', ['inspection_id'], unique=False)
    for table, columns in additions().items():
        with op.batch_alter_table(table) as batch:
            for column in columns:
                batch.add_column(column)
            for name, column, target in FOREIGN_KEYS.get(table, []):
                batch.create_foreign_key(name, target, [column], ['id'])
            for column in INDEXES.get(table, []):
                batch.create_index(f'ix_{table}_{column}', [column])

def downgrade():
    for table, columns in reversed(list(additions().items())):
        with op.batch_alter_table(table) as batch:
            for name, column, target in FOREIGN_KEYS.get(table, []):
                batch.drop_constraint(name, type_='foreignkey')
            for column in INDEXES.get(table, []):
                batch.drop_index(f'ix_{table}_{column}')
            for column in reversed(columns):
                batch.drop_column(column.name)
    op.drop_index(op.f('ix_inspection_revisions_inspection_id'), table_name='inspection_revisions')
    op.drop_table('inspection_revisions')
    op.drop_index(op.f('ix_findings_inspection_id'), table_name='findings')
    op.drop_table('findings')
    op.drop_index(op.f('ix_inspections_vehicle_id'), table_name='inspections')
    op.drop_index(op.f('ix_inspections_order_id'), table_name='inspections')
    op.drop_table('inspections')
    op.drop_index('one_active_assignment', table_name='work_assignments', postgresql_where=sa.text('revoked_at IS NULL'), sqlite_where=sa.text('revoked_at IS NULL'))
    op.drop_index(op.f('ix_work_assignments_order_id'), table_name='work_assignments')
    op.drop_index(op.f('ix_work_assignments_mechanic_id'), table_name='work_assignments')
    op.drop_table('work_assignments')
    op.drop_index('one_current_location', table_name='bay_occupancies', postgresql_where=sa.text('exited_at IS NULL'), sqlite_where=sa.text('exited_at IS NULL'))
    op.drop_index(op.f('ix_bay_occupancies_order_id'), table_name='bay_occupancies')
    op.drop_index(op.f('ix_bay_occupancies_bay_id'), table_name='bay_occupancies')
    op.drop_table('bay_occupancies')
    op.drop_index(op.f('ix_workshop_bays_zone_id'), table_name='workshop_bays')
    op.drop_index(op.f('ix_workshop_bays_workshop_id'), table_name='workshop_bays')
    op.drop_table('workshop_bays')
    op.drop_index(op.f('ix_audit_events_workshop_id'), table_name='audit_events')
    op.drop_index(op.f('ix_audit_events_resource_id'), table_name='audit_events')
    op.drop_table('audit_events')
    op.drop_index(op.f('ix_workshop_zones_workshop_id'), table_name='workshop_zones')
    op.drop_table('workshop_zones')
    op.drop_table('workshops')


def additions():
    scope = lambda: sa.Column('workshop_id', sa.Integer(), server_default='1', nullable=False)
    return {
        'customers': [scope()],
        'extra_quotes': [sa.Column('task_id', sa.Integer(), nullable=True)],
        'intake_photos': [sa.Column('task_id', sa.Integer()), sa.Column('inspection_id', sa.Integer()), sa.Column('finding_id', sa.Integer()), sa.Column('published_at', sa.DateTime(timezone=True)), sa.Column('published_by', sa.Integer())],
        'maintenance_catalogs': [scope()],
        'users': [scope()],
        'vehicles': [scope(), sa.Column('template_id', sa.String(80), nullable=False, server_default='sedan-neutral-v1')],
        'work_orders': [scope(), sa.Column('base_approval', sa.String(20), nullable=False, server_default='pending'), sa.Column('base_approved_at', sa.DateTime(timezone=True)), sa.Column('base_approved_by', sa.Integer())],
    }


FOREIGN_KEYS = {
    'customers': [('fk_customers_workshop', 'workshop_id', 'workshops')],
    'extra_quotes': [('fk_quote_task', 'task_id', 'checklist_items')],
    'intake_photos': [('fk_photo_task', 'task_id', 'checklist_items'), ('fk_photo_inspection', 'inspection_id', 'inspections'), ('fk_photo_finding', 'finding_id', 'findings'), ('fk_photo_publisher', 'published_by', 'users')],
    'maintenance_catalogs': [('fk_catalogs_workshop', 'workshop_id', 'workshops')],
    'users': [('fk_users_workshop', 'workshop_id', 'workshops')],
    'vehicles': [('fk_vehicles_workshop', 'workshop_id', 'workshops')],
    'work_orders': [('fk_orders_workshop', 'workshop_id', 'workshops'), ('fk_order_base_approver', 'base_approved_by', 'users')],
}
INDEXES = {table: ['workshop_id'] for table in ('customers', 'maintenance_catalogs', 'users', 'vehicles', 'work_orders')}
INDEXES['intake_photos'] = ['inspection_id', 'task_id']
