"""Compara la base configurada con una restauración aislada, solo lectura.

Uso: python backend/scripts/verify_entrega08_preservation.py motordesk_migration_check_...
No imprime cuentas, contraseñas ni datos de clientes; solo el resultado.
La copia debe proceder del respaldo de continuación de Entrega 8 (0008).
"""
import json
from pathlib import Path
import sys

from dotenv import dotenv_values
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


def main():
    database = sys.argv[1]
    if not database.startswith('motordesk_migration_check_'):
        raise SystemExit('Se requiere una copia aislada con prefijo motordesk_migration_check_')
    root = Path(__file__).resolve().parents[2]
    url = make_url(dotenv_values(root / '.env')['DATABASE_URL'].replace('@localhost:', '@127.0.0.1:'))
    queries = {
        'accounts': 'SELECT id,workshop_id,username,email,password_hash,role,active,must_change_password,token_version FROM users ORDER BY id',
        'vehicles': 'SELECT id,workshop_id,owner_id,plate,vin,brand,model,year,mileage,active,catalog_make_id,catalog_model_id,catalog_generation_id FROM vehicles ORDER BY id',
        'orders': 'SELECT id,vehicle_id,customer_id,base_total,status,payer_snapshot FROM work_orders ORDER BY id',
        'branding': 'SELECT scope,payload,revision FROM app_configurations ORDER BY scope',
        'provenance': 'SELECT entity_type,entity_id,source_key,origin,created_by,created_at FROM catalog_record_meta ORDER BY entity_type,entity_id',
    }
    def snapshot(target):
        engine = create_engine(target, connect_args={'connect_timeout': 10})
        try:
            with engine.connect() as connection:
                return {key: connection.execute(text(query)).fetchall() for key, query in queries.items()}
        finally:
            engine.dispose()
    before = snapshot(url.set(database=database))
    after = snapshot(url)
    results = {key: before[key] == after[key] for key in queries}
    print(json.dumps({'unchanged': results, 'vehicle_count': len(after['vehicles'])}))
    if not all(results.values()):
        raise SystemExit('Se encontraron diferencias: revisar sin sobrescribir la base')


if __name__ == '__main__':
    main()
