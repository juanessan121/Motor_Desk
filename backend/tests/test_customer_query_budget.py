"""Medición reproducible del listado del cliente con datos solo de prueba.

Ejecutar con -s para ver consultas, tiempo mediano y carga de binarios.
"""
import json
import os
from statistics import median
from time import perf_counter

import pytest
from sqlalchemy import event

from app.models import ChecklistItem, IntakePhoto, WorkOrder, utcnow


@pytest.mark.parametrize('limit', [5, 20])
def test_customer_listing_query_budget(client, admin_headers, work_order, factory, limit):
    original, _, headers = work_order
    with factory.begin() as db:
        source = db.get(WorkOrder, original['id'])
        for index in range(40):
            order = WorkOrder(
                workshop_id=source.workshop_id, vehicle_id=source.vehicle_id,
                customer_id=source.customer_id, catalog_id=source.catalog_id,
                payer_snapshot=dict(source.payer_snapshot), title=f'Servicio documentado {index}',
                base_total=source.base_total, status='delivered',
                items=[ChecklistItem(label='Tarea realizada', completed=True, completed_at=utcnow())],
            )
            db.add(order)
            db.flush()
            db.add(IntakePhoto(order_id=order.id, uploaded_by=1, caption='Evidencia de prueba',
                               content=b'\x00' * 32768, published_at=utcnow(), published_by=1))
    engine = factory.kw['bind']
    times, counts, binary_reads = [], [], []
    statements = []
    def capture(_conn, _cursor, statement, _params, _context, _many):
        statements.append(statement)
    event.listen(engine, 'before_cursor_execute', capture)
    try:
        for _ in range(5):
            statements.clear()
            started = perf_counter()
            response = client.get(f'/api/v1/orders?limit={limit}&offset=0', headers=headers)
            times.append((perf_counter() - started) * 1000)
            assert response.status_code == 200, response.text
            assert len(response.json()) == limit
            counts.append(len(statements))
            binary_reads.append(any('intake_photos.content' in sql for sql in statements))
    finally:
        event.remove(engine, 'before_cursor_execute', capture)
    result = {
        'phase': os.environ.get('MOTORDESK_BENCH_PHASE', 'validation'),
        'database': engine.dialect.name, 'rows': limit,
        'queries': counts, 'median_ms': round(median(times), 2),
        'loaded_photo_content': any(binary_reads),
    }
    print(json.dumps(result))
