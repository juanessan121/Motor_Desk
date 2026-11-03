from alembic import context

# Ambos módulos deben registrarse en Base.metadata. Importar solo `models`
# dejaba las 9 tablas del catálogo fuera del objetivo y un `autogenerate`
# posterior proponía borrar todo el catálogo. `alembic check` lo detecta.
from app import catalog_models, models  # noqa: F401
from app.database import Base, engine

if context.is_offline_mode():
    context.configure(url=str(engine.url), target_metadata=Base.metadata, literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()
else:
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True, render_as_batch=engine.dialect.name == "sqlite")
        with context.begin_transaction():
            context.run_migrations()
