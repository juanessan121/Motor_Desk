"""Respaldo operativo JSON local, sin claves del servidor ni accesos temporales.

Restauración exclusivamente a una base nueva: valida en un archivo temporal,
comprueba todas las FK y publica el resultado solamente al finalizar.
"""
import base64
from datetime import datetime, date
from decimal import Decimal
import json
import os
from pathlib import Path
import tempfile

from sqlalchemy import select, text
from .database import Base, make_engine
from .local_schema import LOCAL_SCHEMA, initialize_database
from .security import decrypt_payload, encrypt_payload

FORMAT = 'motordesk-operational'
EXCLUDED = {'devices', 'customer_access_grants'}
MAX_BYTES = 512 * 1024 * 1024


def encode(value):
    if isinstance(value, bytes):
        return {'$bytes': base64.b64encode(value).decode('ascii')}
    if isinstance(value, (datetime, date)):
        return {'$datetime': value.isoformat()}
    if isinstance(value, Decimal):
        return {'$decimal': str(value)}
    raise TypeError(f'Tipo no soportado: {type(value).__name__}')


def decode(value):
    if set(value) == {'$bytes'}:
        return base64.b64decode(value['$bytes'], validate=True)
    if set(value) == {'$datetime'}:
        return datetime.fromisoformat(value['$datetime'])
    if set(value) == {'$decimal'}:
        return Decimal(value['$decimal'])
    return value


def publish_exclusive(source, destination):
    # Windows: rename es atómico y rechaza un destino existente, también en
    # FAT/exFAT (p. ej. una memoria USB), donde no hay enlaces duros.
    if os.name == 'nt':
        os.rename(source, destination)
    else:
        os.link(source, destination)


def export_backup(engine, destination):
    destination = Path(destination)
    data = {}
    with engine.connect() as db:
        # BEGIN explícito asegura una instantánea consistente en sqlite3.
        db.exec_driver_sql('BEGIN')
        for name, table in Base.metadata.tables.items():
            rows = []
            if name not in EXCLUDED:
                for original in db.execute(select(table)).mappings():
                    row = dict(original)
                    if name == 'notifications':
                        encrypted = row.pop('encrypted_payload')
                        row['delivery_payload'] = None
                        if row['kind'] == 'credentials':
                            if row['status'] != 'sent':
                                row.update(status='failed', blocked_reason=None,
                                           last_error='Acceso temporal excluido del respaldo; genere uno nuevo')
                        elif encrypted:
                            row['delivery_payload'] = decrypt_payload(encrypted)
                    if name == 'users':
                        row['token_version'] += 1
                    rows.append(row)
            data[name] = rows
    payload = {'format': FORMAT, 'schema_version': LOCAL_SCHEMA, 'tables': data}
    # Publicar solo un JSON completo. Un error de disco/serialización no deja
    # un archivo final aparentemente válido y no reemplaza copias existentes.
    with tempfile.TemporaryDirectory(prefix='motordesk-backup-', dir=destination.parent) as folder:
        staged = Path(folder) / 'complete.json'
        with staged.open('x', encoding='utf-8') as stream:
            json.dump(payload, stream, ensure_ascii=False, default=encode)
            stream.flush()
            os.fsync(stream.fileno())
        publish_exclusive(staged, destination)
    return {name: len(rows) for name, rows in data.items()}


def restore_backup(source, destination):
    source, destination = Path(source), Path(destination)
    if destination.exists():
        raise ValueError('Restauración rechazada: la base de destino existe. Use otra carpeta de datos; no se sobrescribe el taller.')
    if source.stat().st_size > MAX_BYTES:
        raise ValueError('Respaldo demasiado grande (máximo 512 MiB)')
    payload = json.loads(source.read_text(encoding='utf-8'), object_hook=decode)
    if isinstance(payload, dict) and payload.get('format') == FORMAT and payload.get('schema_version') == 1:
        tables = payload.get('tables', {})
        customers = {row.get('user_id'): row['id'] for row in tables.get('customers', []) if row.get('user_id')}
        for row in tables.get('notifications', []):
            row['customer_id'] = customers.get(row.get('user_id'))
        payload['schema_version'] = LOCAL_SCHEMA
    if not isinstance(payload, dict) or payload.get('format') != FORMAT or payload.get('schema_version') != LOCAL_SCHEMA:
        raise ValueError('Formato o versión de respaldo incompatible')
    tables = payload.get('tables')
    if not isinstance(tables, dict) or set(tables) != set(Base.metadata.tables):
        raise ValueError('El respaldo no contiene exactamente las tablas requeridas')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='motordesk-restore-', dir=destination.parent) as folder:
        staged = Path(folder) / 'validated.db'
        engine = make_engine('sqlite:///' + staged.as_posix())
        try:
            initialize_database(engine)
            with engine.begin() as db:
                db.execute(text('PRAGMA defer_foreign_keys=ON'))
                for name, rows in tables.items():
                    table = Base.metadata.tables[name]
                    if not isinstance(rows, list) or (name in EXCLUDED and rows):
                        raise ValueError(f'Tabla no válida: {name}')
                    for original in rows:
                        if not isinstance(original, dict):
                            raise ValueError('Registro no válido')
                        row = dict(original)
                        if name == 'notifications':
                            delivery = row.pop('delivery_payload', None)
                            if row.get('kind') == 'credentials' and delivery:
                                raise ValueError('El respaldo contiene accesos temporales')
                            row['encrypted_payload'] = encrypt_payload(delivery) if delivery else None
                        if set(row) != set(table.columns.keys()):
                            raise ValueError(f'Columnas incompatibles: {name}')
                        db.execute(table.insert().values(**row))
                if db.execute(text('PRAGMA foreign_key_check')).all():
                    raise ValueError('Referencias inválidas en el respaldo')
                if db.scalar(text('PRAGMA integrity_check')) != 'ok':
                    raise ValueError('Integridad inválida')
                from .models import User
                if not db.scalar(select(User.id).where(User.role == 'admin', User.active.is_(True))):
                    raise ValueError('El respaldo no contiene un administrador activo')
        finally:
            engine.dispose()
        # Enlace exclusivo en el mismo volumen: publicación atómica sin sobrescribir.
        publish_exclusive(staged, destination)
    return {name: len(rows) for name, rows in tables.items()}
