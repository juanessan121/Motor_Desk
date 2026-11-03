"""Exportación reproducible PostgreSQL del modelo completo, sin conectarse a una BD."""
from pathlib import Path
import sys

from sqlalchemy import create_mock_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
# Ambos módulos: sin `catalog_models` el esquema exportado omitía las 12
# tablas del catálogo y quedaba desfasado respecto a Alembic.
from app import catalog_models, models  # noqa: F401
from app.database import Base

statements = []


def collect(sql, *args, **kwargs):
    rendered = str(sql.compile(dialect=engine.dialect)).strip()
    statements.append("\n".join(line.rstrip() for line in rendered.splitlines()) + ";")


engine = create_mock_engine("postgresql+psycopg://", collect)
Base.metadata.create_all(engine)
destination = Path(__file__).resolve().parents[1] / "schema.sql"
destination.write_text(
    "-- MotorDesk · PostgreSQL 17 + pgvector · Exportado desde app/models.py y\n"
    "-- app/catalog_models.py. Incluye índices PostgreSQL HNSW y trigram;\n"
    "-- la extensión pgvector se instala mediante Alembic.\n"
    "-- Usar Alembic como método normal de instalación. No ejecutar ambos métodos.\n"
    "BEGIN;\n\n" + "\n\n".join(statements) + "\n\nCOMMIT;\n",
    encoding="utf-8",
    newline="\n",
)
print(destination)
