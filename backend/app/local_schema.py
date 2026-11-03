"""SQLite local: baseline versionada, separada de las migraciones PostgreSQL.

No se actualiza silenciosamente una base con esquema desconocido.
"""
from sqlalchemy import inspect, text
from .database import Base
from . import models  # noqa: F401

LOCAL_SCHEMA = 2


def initialize_database(engine):
    if engine.dialect.name != 'sqlite':
        raise ValueError('El lanzador local requiere SQLite')
    tables = inspect(engine).get_table_names()
    if tables:
        with engine.connect() as connection:
            version = connection.scalar(text('PRAGMA user_version'))
        if version == 1:
            # No tabla referencia notifications. Recrear solo esta tabla en una
            # transacción permite retirar NOT NULL sin perder filas ni claves.
            from sqlalchemy.schema import CreateTable
            table = Base.metadata.tables['notifications']
            old_columns = {col['name'] for col in inspect(engine).get_columns('notifications')}
            if old_columns != set(table.columns.keys()) - {'customer_id'}:
                raise ValueError('Esquema v1 desconocido; no se puede migrar notifications')
            for name, definition in Base.metadata.tables.items():
                if name == 'notifications':
                    continue
                if name not in tables or {col['name'] for col in inspect(engine).get_columns(name)} != set(definition.columns.keys()):
                    raise ValueError(f'Esquema v1 incompatible en {name}; no se modifica la base')
            ddl = str(CreateTable(table).compile(engine)).replace('CREATE TABLE notifications', 'CREATE TABLE notifications_v2', 1)
            with engine.connect() as connection:
                connection.exec_driver_sql('BEGIN IMMEDIATE')
                connection.exec_driver_sql(ddl)
                columns = ', '.join('"' + col + '"' for col in sorted(old_columns))
                connection.exec_driver_sql(f'INSERT INTO notifications_v2 ({columns}) SELECT {columns} FROM notifications')
                connection.exec_driver_sql('UPDATE notifications_v2 SET customer_id = (SELECT id FROM customers WHERE customers.user_id = notifications_v2.user_id)')
                connection.exec_driver_sql('DROP TABLE notifications')
                connection.exec_driver_sql('ALTER TABLE notifications_v2 RENAME TO notifications')
                for index in table.indexes:
                    index.create(connection)
                if connection.exec_driver_sql('PRAGMA foreign_key_check').first():
                    raise ValueError('Migración rechazada por integridad referencial')
                connection.exec_driver_sql(f'PRAGMA user_version={LOCAL_SCHEMA}')
                connection.commit()
            version = LOCAL_SCHEMA
        if version != LOCAL_SCHEMA:
            raise ValueError(f'Esquema local {version} incompatible; restaure con su versión original')
        missing = set(Base.metadata.tables) - set(tables)
        if missing:
            raise ValueError('Base incompleta: ' + ', '.join(sorted(missing)))
        inspector = inspect(engine)
        for name, table in Base.metadata.tables.items():
            actual = {col['name'] for col in inspector.get_columns(name)}
            if actual != set(table.columns.keys()):
                raise ValueError(f'Esquema incompatible en {name}; requiere migración explícita')
        return
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(text(f'PRAGMA user_version={LOCAL_SCHEMA}'))
