"""Datos de pruebas de navegador, exclusivamente en una base de validación.

No crea usuarios, puestos ni vehículos en la base de trabajo.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import select
from sqlalchemy.engine import make_url

from app.database import SessionLocal
from app.models import CatalogTask, Customer, MaintenanceCatalog, User, Vehicle, Workshop
from app.security import password_hasher
from app.settings import settings
from app.maintenance_service import DEFAULT_TEMPLATES, save_version


def main():
    name = make_url(settings().database_url).database or ''
    if not name.startswith('motordesk_check_'):
        raise RuntimeError('Este script solo admite bases motordesk_check_ de validación')
    with SessionLocal.begin() as db:
        if db.scalar(select(User.id).where(User.username == 'validacion-flujos-admin')):
            print('La cuenta de validación ya existe; no se modifica su contraseña.')
            return
        workshop = Workshop(name='Validación aislada de flujos — no operativo')
        db.add(workshop); db.flush()
        accounts = {}
        for role, suffix in [('admin', 'admin'), ('mechanic', 'mecanico'), ('customer', 'cliente')]:
            user = User(workshop_id=workshop.id, username='validacion-flujos-' + suffix,
                email=f'validacion-flujos-{suffix}@example.com', role=role, must_change_password=False,
                password_hash=password_hasher.hash('Validacion-Flujos-2026!'))
            db.add(user); db.flush(); accounts[role] = user
        customer = Customer(workshop_id=workshop.id, user_id=accounts['customer'].id,
            national_id='VALIDACION-NO-REAL', first_name='Cliente', last_name='de validación aislada',
            email=accounts['customer'].email, address='Entorno de pruebas', phone='')
        db.add(customer); db.flush()
        db.add(Vehicle(workshop_id=workshop.id, owner_id=customer.id, plate='TST0001',
            brand='Toyota', model='Corolla', year=2020, mileage=10000))
        catalog = MaintenanceCatalog(workshop_id=workshop.id, name='Preventivo básico — validación aislada',
            description='Datos de prueba, no oferta comercial ni programa del fabricante.',
            base_price=30, price_configured=True, interval_km=5000, schedule_source='Referencia de prueba configurable',
            tasks=[CatalogTask(label=label, position=index, required=index != 1) for index, label in enumerate(DEFAULT_TEMPLATES[0][3])])
        db.add(catalog); db.flush()
        save_version(db, catalog, accounts['admin'])
        print('Preparada validación en base aislada; sin cambios en la base operativa.')


if __name__ == '__main__':
    main()
