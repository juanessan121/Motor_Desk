"""Compara todas las columnas previas sin imprimir datos privados.

Uso: python scripts/check_workflow_preservation.py --baseline BASE_RESTAURADA
La conexión de destino se toma de DATABASE_URL. No modifica ninguna base.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from app.settings import settings


def schema(connection):
    tables = {}
    for table, column in connection.execute(text("""SELECT table_name, column_name FROM information_schema.columns
            WHERE table_schema = 'public' ORDER BY table_name, ordinal_position""")):
        tables.setdefault(table, []).append(column)
    primary = {}
    for table, column in connection.execute(text("""SELECT tc.table_name, kcu.column_name
            FROM information_schema.table_constraints tc JOIN information_schema.key_column_usage kcu
            ON kcu.constraint_name = tc.constraint_name AND kcu.constraint_schema = tc.constraint_schema
            AND kcu.table_name = tc.table_name
            WHERE tc.table_schema = 'public' AND tc.constraint_type = 'PRIMARY KEY'
            ORDER BY tc.table_name, kcu.ordinal_position""")):
        primary.setdefault(table, []).append(column)
    return tables, primary


def digest(connection, table, columns, primary):
    # Solo identificadores leídos del esquema, escapados por el dialecto.
    quote = connection.dialect.identifier_preparer.quote
    fields = ', '.join(quote(column) for column in columns)
    order = ', '.join(quote(column) for column in primary or columns[:1])
    query = f"SELECT count(*), md5(string_agg(md5(json_build_array({fields})::text), '' ORDER BY {order})) FROM public.{quote(table)}"
    return tuple(connection.execute(text(query)).one())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--baseline', required=True)
    args = parser.parse_args()
    target_url = make_url(settings().database_url)
    baseline = create_engine(target_url.set(database=args.baseline))
    target = create_engine(target_url)
    report = []
    with baseline.connect() as before, target.connect() as after:
        source, primary = schema(before)
        destination, _ = schema(after)
        for name, columns in source.items():
            if name == 'alembic_version':
                continue
            if name not in destination or not set(columns).issubset(destination[name]):
                raise AssertionError('Falta tabla: ' + name)
            # Solo se permite agregar registros de nuevas plantillas. El script
            # se ejecuta antes de instalarlas para exigir igualdad completa.
            left, right = digest(before, name, columns, primary.get(name)), digest(after, name, columns, primary.get(name))
            if left != right:
                raise AssertionError('Los datos previos cambiaron: ' + name)
            report.append({'table': name, 'rows': right[0], 'digest': right[1]})
    print(json.dumps({'preserved': True, 'algorithm': 'MD5 de filas JSON ordenadas (PostgreSQL)', 'tables': report}, indent=2))


if __name__ == '__main__':
    main()
