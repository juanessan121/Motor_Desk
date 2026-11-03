"""Validación adicional de relaciones que JSON Schema no puede expresar."""
def relational_errors(payload):
    errors = []
    def index(collection, key):
        result = {}
        for position, row in enumerate(payload.get(collection, [])):
            value = row.get(key)
            if value in result:
                errors.append(f'{collection}[{position}].{key}: identificador duplicado {value}')
            result[value] = row
        return result
    customers = index('clientes', 'id')
    vehicles = index('vehiculos', 'id')
    orders = index('mantenimientos', 'orden_id')
    index('notificaciones', 'id')
    index('seguimiento_estados', 'orden_id')
    for identifier, vehicle in vehicles.items():
        if vehicle.get('propietario', {}).get('cliente_id') not in customers:
            errors.append(f'vehiculos[{identifier}]: propietario inexistente')
    for identifier, order in orders.items():
        if order.get('vehiculo', {}).get('id') not in vehicles:
            errors.append(f'mantenimientos[{identifier}]: vehículo inexistente')
        if order.get('cliente', {}).get('id') not in customers:
            errors.append(f'mantenimientos[{identifier}]: cliente inexistente')
        activities = [row.get('id') for row in order.get('actividades_incluidas', [])]
        if len(activities) != len(set(activities)):
            errors.append(f'mantenimientos[{identifier}]: actividades duplicadas')
    for collection in ('seguimiento_estados', 'notificaciones'):
        for position, row in enumerate(payload.get(collection, [])):
            if row.get('orden_id') is not None and row['orden_id'] not in orders:
                errors.append(f'{collection}[{position}]: orden inexistente')
    return errors
