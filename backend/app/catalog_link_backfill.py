"""Backfill de la referencia al catálogo en los vehículos existentes.

Sin opciones no escribe nada. Informa de las coincidencias y sus motivos.
Nunca reemplaza enlaces existentes, incluidos los elegidos a mano.

Motivo de que sea de solo lectura: enlazar mal un vehículo es un error silencioso
—el Pasaporte pasaría a mostrar un motor que no es el del coche— y en una base
con datos de clientes reales esa corrección es más cara que la carencia.

    docker compose run --rm --no-deps api python -m app.catalog_link_backfill

Con ``--apply`` enlaza de verdad, y solo lo que resuelve sin ambigüedad.
"""
from __future__ import annotations

import argparse

from sqlalchemy import select

from .catalog_link import CATALOG_FIELDS, apply_catalog_match, resolve_vehicle
from .database import SessionLocal
from .models import Vehicle


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true',
                        help='Escribe los enlaces resueltos sin ambigüedad.')
    args = parser.parse_args()

    with SessionLocal() as db:
        vehiculos = db.scalars(select(Vehicle)).all()
        enlazados = 0
        modelos = 0
        conservados = 0
        sin_enlace: list[tuple[str, str]] = []
        for vehiculo in vehiculos:
            if any(getattr(vehiculo, field) is not None for field in CATALOG_FIELDS):
                conservados += 1
                print(f'[conservado] {vehiculo.plate}: ya tiene referencia')
                continue
            match = resolve_vehicle(db, vehiculo.brand, vehiculo.model,
                                    vehiculo.year)
            etiqueta = f'{vehiculo.plate} · {vehiculo.brand} {vehiculo.model}'
            if match.model_id is not None:
                modelos += 1
                generacion = f' → {match.generation_name}' if match.generation_name else ''
                print(f'[modelo] {etiqueta}{generacion}')
            elif match.make_id is not None:
                print(f'[marca]  {etiqueta} → {match.make_name}')
                print(f'          motivo: {match.reason}')
            else:
                sin_enlace.append((etiqueta, match.reason))
                print(f'[—]      {etiqueta}')
                print(f'          motivo: {match.reason}')

            if match.linked:
                enlazados += 1
                if args.apply:
                    apply_catalog_match(db, vehiculo, match)

        if args.apply:
            db.commit()
            print(f'\nEnlazados y guardados: {enlazados} de {len(vehiculos)}')
        else:
            print(f'\nSe enlazarían {enlazados} de {len(vehiculos)} vehículos.')
            print(f'Sin enlace posible: {len(sin_enlace)}')
            if sin_enlace:
                print('\nMotivos de los que quedan fuera:')
                for etiqueta, motivo in sin_enlace:
                    print(f'  {etiqueta}: {motivo}')
            print('\nNada se ha modificado. Use --apply para escribir.')
        print(f'Con modelo: {modelos}; referencias existentes conservadas: {conservados}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
