"""vehicle_catalog_reference

`vehicles` guardaba la marca y el modelo como texto libre, sin ninguna relación
con el catálogo. Eso dejaba tres cosas sin poder hacerse:

- el Pasaporte Digital no podía mostrar generación ni motor reales;
- no se podía buscar «todos los Corolla del taller» sin recorrer cada texto;
- el catálogo y el garaje no tenían nada que decirse.

Se añaden tres columnas opcionales que apuntan al catálogo. **El texto no se
toca ni se borra**: `brand` y `model` siguen siendo lo que el taller escribió
sobre ese coche concreto, y la referencia es solo un enlace. Un vehículo cuyo
modelo no exista en el catálogo —un clásico, uno importado a mano— se queda sin
enlace y sigue funcionando igual.

Las tres son nulables a propósito. `NOT NULL` obligaría a inventar una entrada
del catálogo para cada coche que se escriba, que es justo lo que no se quiere.

`ON DELETE SET NULL` y no `CASCADE` ni `RESTRICT`: el catálogo es compartido y
una importación podría retirar una fila. Que se borre una fila del catálogo no
puede borrar el vehículo de un cliente ni impedir registrar uno nuevo.

La consistencia entre las tres columnas (que el modelo pertenezca a la marca, y
la generación al modelo) no se impone con `CHECK`: eso exigiría un subselect que
Postgres no admite ahí, y por tanto un disparador que se ejecutaría en cada
actualización de la tabla. Se comprueba en la capa de aplicación, donde ya se
escriben los enlaces, y hay pruebas que lo cubren.
"""
from alembic import op
import sqlalchemy as sa

revision = '0008'
down_revision = '0007'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('vehicles', sa.Column('catalog_make_id', sa.Integer(),
                                        nullable=True))
    op.add_column('vehicles', sa.Column('catalog_model_id', sa.Integer(),
                                        nullable=True))
    op.add_column('vehicles', sa.Column('catalog_generation_id', sa.Integer(),
                                        nullable=True))
    # SET NULL: perder una fila del catálogo deja el vehículo sin referencia,
    # nunca lo borra.
    op.create_foreign_key('vehicles_catalog_make_id_fkey', 'vehicles',
                          'catalog_makes', ['catalog_make_id'], ['id'],
                          ondelete='SET NULL')
    op.create_foreign_key('vehicles_catalog_model_id_fkey', 'vehicles',
                          'catalog_models', ['catalog_model_id'], ['id'],
                          ondelete='SET NULL')
    op.create_foreign_key('vehicles_catalog_generation_id_fkey', 'vehicles',
                          'catalog_generations', ['catalog_generation_id'],
                          ['id'], ondelete='SET NULL')
    op.create_index('ix_vehicles_catalog_model_id', 'vehicles',
                    ['catalog_model_id'])
    op.create_index('ix_vehicles_catalog_make_id', 'vehicles',
                    ['catalog_make_id'])


def downgrade():
    op.drop_index('ix_vehicles_catalog_make_id', table_name='vehicles')
    op.drop_index('ix_vehicles_catalog_model_id', table_name='vehicles')
    op.drop_constraint('vehicles_catalog_generation_id_fkey', 'vehicles',
                       type_='foreignkey')
    op.drop_constraint('vehicles_catalog_model_id_fkey', 'vehicles',
                       type_='foreignkey')
    op.drop_constraint('vehicles_catalog_make_id_fkey', 'vehicles',
                       type_='foreignkey')
    op.drop_column('vehicles', 'catalog_generation_id')
    op.drop_column('vehicles', 'catalog_model_id')
    op.drop_column('vehicles', 'catalog_make_id')
