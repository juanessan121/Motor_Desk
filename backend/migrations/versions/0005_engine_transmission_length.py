"""engine_transmission_length
"""
from alembic import op
import sqlalchemy as sa

# 0005 corrige un dimensionamiento que la importacion de 0004 dejo estrecho.
revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None


def upgrade():
    # `catalog_engines.transmission` se fijo en VARCHAR(80) por analogia con
    # `fuel_type` (maximo real 29). Los datos de gor3a describen caja y modo
    # de conduccion en ese campo: hay valores de 152 caracteres, por lo que la
    # importacion abortaba con StringDataRightTruncation al llegar a engines.
    # Se amplia en lugar de truncar: perder la descripcion seria perder datos.
    op.alter_column(
        'catalog_engines', 'transmission',
        existing_type=sa.String(length=80),
        type_=sa.String(length=255),
        existing_nullable=True,
    )


def downgrade():
    # El recorte solo es seguro si no hay transmisiones de mas de 80
    # caracteres; por eso el downlink comprueba en lugar de truncar en silencio.
    connection = op.get_bind()
    overflow = connection.execute(
        sa.text("SELECT count(*) FROM catalog_engines WHERE length(transmission) > 80")
    ).scalar_one()
    if overflow:
        raise RuntimeError(
            f"No se puede revertir: {overflow} transmisiones exceden 80 caracteres. "
            "Recortarlas perderia informacion de la fuente."
        )
    op.alter_column(
        'catalog_engines', 'transmission',
        existing_type=sa.String(length=255),
        type_=sa.String(length=80),
        existing_nullable=True,
    )