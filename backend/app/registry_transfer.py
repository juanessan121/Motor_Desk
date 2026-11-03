"""Intercambio incremental de clientes/vehículos; nunca restaura cuentas u órdenes."""
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field, model_validator
from sqlalchemy import select, or_
from .schemas import Input, CustomerInput, VehicleInput
from .models import Customer, Vehicle, User
from .dependencies import Database, admin, invalidate
from .access_policy import audit
from .registry_routes import create_customer, create_vehicle
from .catalog_link import CATALOG_FIELDS

router = APIRouter(prefix='/registry-transfer', tags=['Intercambio de registros'])


class CustomerRecord(Input):
    source_id: int = Field(gt=0)
    data: CustomerInput


class VehicleRecord(Input):
    source_id: int = Field(gt=0)
    data: VehicleInput


class RegistryTransfer(Input):
    format: Literal['motordesk-registry']
    version: Literal[1]
    customers: list[CustomerRecord] = Field(max_length=2000)
    vehicles: list[VehicleRecord] = Field(max_length=5000)

    @model_validator(mode='after')
    def references(self):
        for rows, label in [(self.customers, 'clientes'), (self.vehicles, 'vehículos')]:
            ids = [r.source_id for r in rows]
            if len(ids) != len(set(ids)):
                raise ValueError(f'IDs duplicados de {label}')
        owners = {r.source_id for r in self.customers}
        if any(v.data.owner_id not in owners for v in self.vehicles):
            raise ValueError('Cada propietario debe estar incluido en el archivo')
        if any(c.data.has_portal_access for c in self.customers):
            raise ValueError('La importación no crea cuentas: use has_portal_access=false')
        if any(CATALOG_FIELDS & v.data.model_fields_set for v in self.vehicles):
            raise ValueError('No importe IDs de catálogo de otra instalación')
        for values in ([c.data.national_id for c in self.customers], [str(c.data.email).lower() for c in self.customers],
                       [v.data.plate for v in self.vehicles], [v.data.vin for v in self.vehicles if v.data.vin]):
            if len(values) != len(set(values)):
                raise ValueError('Identificadores naturales duplicados en el archivo')
        return self


def plan(payload, db, user):
    owners, vehicles, errors = {}, {}, []
    for record in payload.customers:
        data = record.data.model_dump(exclude={'has_portal_access'})
        data['email'] = str(data['email']).lower()
        rows = list(db.scalars(select(Customer).where(or_(Customer.national_id == data['national_id'], Customer.email == data['email']))))
        row = rows[0] if len(rows) == 1 else None
        if rows and (row is None or row.workshop_id != user.workshop_id or not row.active or any(getattr(row, k) != v for k, v in data.items())):
            errors.append(f'Cliente {record.source_id}: identidad o datos en conflicto; no se sobrescribe')
        owners[record.source_id] = row
    for record in payload.vehicles:
        data = record.data.model_dump(exclude=CATALOG_FIELDS)
        owner = owners[data.pop('owner_id')]
        rows = list(db.scalars(select(Vehicle).where(or_(Vehicle.plate == data['plate'], Vehicle.vin == data['vin'] if data['vin'] else False))))
        row = rows[0] if len(rows) == 1 else None
        if rows and (row is None or row.workshop_id != user.workshop_id or not row.active or owner is None or row.owner_id != owner.id or any(getattr(row, k) != v for k, v in data.items())):
            errors.append(f'Vehículo {record.source_id}: identidad, propietario o datos en conflicto; no se sobrescribe')
        vehicles[record.source_id] = row
    return owners, vehicles, errors


@router.post('/preview')
def preview(payload: RegistryTransfer, db: Database, user: User = Depends(admin)):
    owners, vehicles, errors = plan(payload, db, user)
    return {'valid': not errors, 'errors': errors, 'new_customers': sum(v is None for v in owners.values()),
            'new_vehicles': sum(v is None for v in vehicles.values()), 'unchanged': sum(v is not None for v in [*owners.values(), *vehicles.values()])}


@router.post('/import')
def apply_import(payload: RegistryTransfer, db: Database, user: User = Depends(admin)):
    owners, vehicles, errors = plan(payload, db, user)
    if errors:
        raise HTTPException(409, {'errors': errors})
    created_customers = created_vehicles = 0
    mapping = {}
    for record in payload.customers:
        row = owners[record.source_id]
        if row is None:
            result = create_customer(record.data, db, user)
            mapping[record.source_id] = result['id']
            created_customers += 1
        else:
            mapping[record.source_id] = row.id
    for record in payload.vehicles:
        if vehicles[record.source_id] is None:
            data = record.data.model_dump(exclude=CATALOG_FIELDS)
            data['owner_id'] = mapping[data['owner_id']]
            create_vehicle(VehicleInput(**data), db, user)
            created_vehicles += 1
    audit(db, user, 'registry.imported', 'workshop', user.workshop_id,
          {'customers': created_customers, 'vehicles': created_vehicles})
    invalidate(db)
    return {'created_customers': created_customers, 'created_vehicles': created_vehicles}


@router.get('/export')
def export_registry(db: Database, user: User = Depends(admin)):
    customers = list(db.scalars(select(Customer).where(Customer.workshop_id == user.workshop_id, Customer.active.is_(True)).order_by(Customer.id)))
    fields = set(CustomerInput.model_fields) - {'has_portal_access'}
    vehicles = db.scalars(select(Vehicle).where(Vehicle.workshop_id == user.workshop_id, Vehicle.active.is_(True), Vehicle.owner_id.in_([c.id for c in customers])).order_by(Vehicle.id))
    return {'format': 'motordesk-registry', 'version': 1,
            'customers': [{'source_id': c.id, 'data': {**{k: getattr(c, k) for k in fields}, 'has_portal_access': False}} for c in customers],
            'vehicles': [{'source_id': v.id, 'data': {k: getattr(v, k) for k in set(VehicleInput.model_fields) - CATALOG_FIELDS}} for v in vehicles]}
