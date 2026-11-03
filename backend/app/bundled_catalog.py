"""Carga inicial offline solo en catálogos vacíos, sin sobrescribir correcciones."""
from pathlib import Path
from sqlalchemy import select
from .catalog_models import CatalogSource, VehicleMake, VehiclePart
from .catalog_import import content_hash, import_vehicles, import_part_terms, record_source


def seed_bundled_catalog(factory, directory=None):
    directory = Path(directory) if directory else Path(__file__).parent / 'resources/catalog'
    result = {}
    for key, filename, model in [('vehicles', 'vehicles.sqlite', VehicleMake), ('part_terms', 'part_terms.json', VehiclePart)]:
        path = directory / filename
        if not path.exists():
            continue
        with factory.begin() as db:
            # Una instalación ya poblada requiere actualización explícita;
            # arrancar o actualizar el programa no reescribe su catálogo.
            if db.get(CatalogSource, key) or db.scalar(select(model.id).limit(1)):
                continue
            print(f'Preparando catálogo local: {key}...', flush=True)
            count = import_vehicles(db, path, with_specs=False) if key == 'vehicles' else import_part_terms(db, path)[0]
            record_source(db, key, content_hash(path), count)
            result[key] = count
    return result
