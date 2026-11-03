"""Verifica una copia aislada del respaldo; nunca apunta a la base workshop."""
import os
from pathlib import Path
import sys

from alembic import command
from alembic.config import Config
from dotenv import dotenv_values
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

root = Path(__file__).resolve().parents[2]
database = sys.argv[1]
if not database.startswith("motordesk_migration_check_"):
    raise SystemExit("Se requiere una base aislada con prefijo motordesk_migration_check_")
url = make_url(dotenv_values(root / '.env')['DATABASE_URL'].replace('@localhost:', '@127.0.0.1:')).set(database=database)
os.environ['DATABASE_URL'] = url.render_as_string(hide_password=False)
engine = create_engine(url, connect_args={"connect_timeout": 10})
queries = {
    'users': 'SELECT id,password_hash,role,active,must_change_password,token_version FROM users ORDER BY id',
    'vehicles': 'SELECT id,owner_id,plate,vin,brand,model,year,mileage,active FROM vehicles ORDER BY id',
    'orders': 'SELECT id,vehicle_id,customer_id,base_total,status,payer_snapshot FROM work_orders ORDER BY id',
    'configuration': 'SELECT scope,payload,revision FROM app_configurations ORDER BY scope',
    'catalog_provenance': 'SELECT entity_type,entity_id,source_key,origin,created_by,created_at FROM catalog_record_meta ORDER BY entity_type,entity_id',
}
with engine.connect() as connection:
    if not inspect(connection).has_table('catalog_record_meta'):
        # Respaldos previos a 0006 todavía no tienen procedencia del catálogo.
        queries.pop('catalog_provenance')
    before = {key: connection.execute(text(sql)).fetchall() for key, sql in queries.items()}
config = Config(str(root / 'backend' / 'alembic.ini'))
command.upgrade(config, 'head')
with engine.connect() as connection:
    after = {key: connection.execute(text(sql)).fetchall() for key, sql in queries.items()}
assert before == after, 'La migración alteró datos existentes'
command.check(config)
print({'isolated_migration': 'ok', 'passwords_and_accounts_preserved': True,
       'vehicles_orders_and_branding_preserved': True})
