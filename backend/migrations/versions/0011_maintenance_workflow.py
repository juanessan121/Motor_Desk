"""Versiones de mantenimiento, ejecución y repuestos; conserva datos existentes."""
from alembic import op
import sqlalchemy as sa

revision = '0011'
down_revision = '0010'
branch_labels = None
depends_on = None


def upgrade():
    for table, columns in {
        'maintenance_catalogs': [
            sa.Column('revision', sa.Integer(), nullable=False, server_default='1'),
            sa.Column('system_key', sa.String(60)),
            sa.Column('price_configured', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column('interval_km', sa.Integer()),
            sa.Column('schedule_source', sa.String(500), nullable=False, server_default=''),
            sa.Column('applicability', sa.JSON(), nullable=False, server_default='{}'),
        ],
        'catalog_tasks': [
            sa.Column('description', sa.Text(), nullable=False, server_default=''),
            sa.Column('required', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column('estimated_minutes', sa.Integer()),
            sa.Column('suggested_part_ids', sa.JSON(), nullable=False, server_default='[]'),
        ],
        'work_orders': [
            sa.Column('symptoms', sa.Text(), nullable=False, server_default=''),
            sa.Column('intake_mileage', sa.Integer()),
            sa.Column('template_snapshot', sa.JSON()),
            sa.Column('request_key', sa.String(36)), sa.Column('request_hash', sa.String(64)),
            sa.Column('priority', sa.String(20), nullable=False, server_default='normal'),
            sa.Column('revision', sa.Integer(), nullable=False, server_default='1'),
            sa.Column('review_required', sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column('execution_reviewed_at', sa.DateTime(timezone=True)),
            sa.Column('execution_reviewed_by', sa.Integer(), sa.ForeignKey('users.id')),
        ],
        'checklist_items': [
            sa.Column('description', sa.Text(), nullable=False, server_default=''),
            sa.Column('status', sa.String(24), nullable=False, server_default='pending'),
            sa.Column('notes', sa.Text(), nullable=False, server_default=''),
            sa.Column('required', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column('estimated_minutes', sa.Integer()),
            sa.Column('suggested_part_ids', sa.JSON(), nullable=False, server_default='[]'),
            sa.Column('template_catalog_id', sa.Integer(), sa.ForeignKey('maintenance_catalogs.id')),
            sa.Column('revision', sa.Integer(), nullable=False, server_default='1'),
            sa.Column('updated_by', sa.Integer(), sa.ForeignKey('users.id')),
            sa.Column('updated_at', sa.DateTime(timezone=True)),
        ],
    }.items():
        for column in columns:
            op.add_column(table, column)
    # Se migra solamente el estado que realmente se conoce. No se inventan
    # kilometrajes de recepción ni versiones antiguas de plantilla.
    op.execute("UPDATE checklist_items SET status = 'completed' WHERE completed = true")
    op.create_check_constraint('checklist_status', 'checklist_items',
                               "status IN ('pending','in_progress','completed','not_applicable','attention')")
    op.create_unique_constraint('uq_catalog_system_key', 'maintenance_catalogs', ['workshop_id', 'system_key'])
    op.create_unique_constraint('uq_order_request', 'work_orders', ['workshop_id', 'request_key'])
    op.create_table('maintenance_versions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('catalog_id', sa.Integer(), sa.ForeignKey('maintenance_catalogs.id'), nullable=False),
        sa.Column('revision', sa.Integer(), nullable=False), sa.Column('snapshot', sa.JSON(), nullable=False),
        sa.Column('created_by', sa.Integer(), sa.ForeignKey('users.id')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('catalog_id', 'revision', name='uq_maintenance_version'))
    op.create_index('ix_maintenance_versions_catalog_id', 'maintenance_versions', ['catalog_id'])
    op.create_table('stock_items',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('workshop_id', sa.Integer(), sa.ForeignKey('workshops.id'), nullable=False),
        sa.Column('part_id', sa.Integer(), sa.ForeignKey('catalog_parts.id'), nullable=False),
        sa.Column('quantity', sa.Numeric(12, 3), nullable=False, server_default='0'),
        sa.Column('unit', sa.String(20), nullable=False, server_default='unidad'),
        sa.UniqueConstraint('workshop_id', 'part_id', name='uq_stock_part'),
        sa.CheckConstraint('quantity >= 0', name='stock_nonnegative'))
    op.create_index('ix_stock_items_workshop_id', 'stock_items', ['workshop_id'])
    op.create_table('part_requests',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('order_id', sa.Integer(), sa.ForeignKey('work_orders.id'), nullable=False),
        sa.Column('task_id', sa.Integer(), sa.ForeignKey('checklist_items.id'), nullable=False),
        sa.Column('part_id', sa.Integer(), sa.ForeignKey('catalog_parts.id')),
        sa.Column('description', sa.String(250), nullable=False),
        sa.Column('quantity', sa.Numeric(12, 3), nullable=False),
        sa.Column('unit', sa.String(20), nullable=False, server_default='unidad'),
        sa.Column('reason', sa.String(1000), nullable=False),
        sa.Column('request_key', sa.String(36), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='requested'),
        sa.Column('quote_id', sa.Integer(), sa.ForeignKey('extra_quotes.id')),
        sa.Column('authorization_basis', sa.String(24), nullable=False, server_default=''),
        sa.Column('resolution_note', sa.String(1000), nullable=False, server_default=''),
        sa.Column('created_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('resolved_by', sa.Integer(), sa.ForeignKey('users.id')),
        sa.Column('resolved_at', sa.DateTime(timezone=True)),
        sa.Column('revision', sa.Integer(), nullable=False, server_default='1'),
        sa.UniqueConstraint('order_id', 'request_key', name='uq_part_request_key'),
        sa.CheckConstraint('quantity > 0', name='request_positive'),
        sa.CheckConstraint("status IN ('requested','approved','issued','rejected')", name='part_request_status'))
    op.create_index('ix_part_requests_order_id', 'part_requests', ['order_id'])
    op.create_table('stock_movements',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('workshop_id', sa.Integer(), sa.ForeignKey('workshops.id'), nullable=False),
        sa.Column('stock_item_id', sa.Integer(), sa.ForeignKey('stock_items.id'), nullable=False),
        sa.Column('part_request_id', sa.Integer(), sa.ForeignKey('part_requests.id')),
        sa.Column('delta', sa.Numeric(12, 3), nullable=False),
        sa.Column('request_key', sa.String(36), nullable=False),
        sa.Column('reason', sa.String(1000), nullable=False),
        sa.Column('actor_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('workshop_id', 'request_key', name='uq_stock_movement_key'),
        sa.UniqueConstraint('part_request_id', name='uq_stock_issue_once'),
        sa.CheckConstraint('delta != 0', name='stock_nonzero'))
    op.create_index('ix_stock_movements_workshop_id', 'stock_movements', ['workshop_id'])
    op.create_index('ix_stock_movements_stock_item_id', 'stock_movements', ['stock_item_id'])


def downgrade():
    # Reducir eliminaría trazabilidad ya creada. La recuperación soportada es
    # restaurar el dump previo en una base nueva, no borrar datos operativos.
    raise RuntimeError('Migración aditiva: restaure el respaldo previo en otra base para volver a 0010')
