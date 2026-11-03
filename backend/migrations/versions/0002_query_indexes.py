"""Índices de relaciones y unicidad de orden abierta, también a nivel de BD."""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

RELATION_INDEXES = (
    ("catalog_tasks", "catalog_id"),
    ("extra_quotes", "order_id"),
    ("quote_options", "quote_id"),
    ("checklist_items", "order_id"),
    ("intake_photos", "order_id"),
)


def upgrade():
    for table, column in RELATION_INDEXES:
        op.create_index(f"ix_{table}_{column}", table, [column])
    op.create_index(
        "one_open_order_per_vehicle", "work_orders", ["vehicle_id"], unique=True,
        postgresql_where=sa.text("status IN ('in_progress','ready')"),
        sqlite_where=sa.text("status IN ('in_progress','ready')"),
    )


def downgrade():
    op.drop_index("one_open_order_per_vehicle", table_name="work_orders")
    for table, column in reversed(RELATION_INDEXES):
        op.drop_index(f"ix_{table}_{column}", table_name=table)
