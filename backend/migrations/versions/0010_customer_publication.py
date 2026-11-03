"""Publicación de notas y clasificación de actividad, sin reescribir contenido."""
from alembic import op
import sqlalchemy as sa

revision = '0010'
down_revision = '0009'
branch_labels = None
depends_on = None


def upgrade():
    # No se da por publicada una nota que nunca tuvo consentimiento explícito.
    op.add_column('work_orders', sa.Column('notes_published', sa.Boolean(),
                                          nullable=False, server_default=sa.false()))
    op.add_column('inbox_events', sa.Column('kind', sa.String(50),
                                           nullable=False, server_default='legacy'))
    op.add_column('inbox_events', sa.Column('inspection_id', sa.Integer(), nullable=True))
    op.create_foreign_key('inbox_events_inspection_id_fkey', 'inbox_events', 'inspections',
                          ['inspection_id'], ['id'], ondelete='SET NULL')
    op.create_index('ix_inbox_events_user_id_id', 'inbox_events', ['user_id', 'id'])


def downgrade():
    op.drop_index('ix_inbox_events_user_id_id', table_name='inbox_events')
    op.drop_constraint('inbox_events_inspection_id_fkey', 'inbox_events', type_='foreignkey')
    op.drop_column('inbox_events', 'inspection_id')
    op.drop_column('inbox_events', 'kind')
    op.drop_column('work_orders', 'notes_published')
