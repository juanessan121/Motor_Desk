from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest


def require_postgres(factory):
    with factory() as db:
        if db.get_bind().dialect.name != "postgresql":
            pytest.skip("Los bloqueos concurrentes requieren PostgreSQL real")


def test_simultaneous_quote_decisions_approve_only_once(client, admin_headers, work_order, factory):
    require_postgres(factory)
    order, _, headers = work_order
    response = client.post(f'/api/v1/orders/{order["id"]}/quotes', headers=admin_headers, json={
        "title": "Pastillas", "options": [{"label": "Original", "price": "25.20"}],
    })
    quote = response.json()["quotes"][0]
    barrier = Barrier(2)
    def decide():
        barrier.wait(timeout=10)
        return client.post(f'/api/v1/orders/{order["id"]}/quotes/{quote["id"]}/decision', headers=headers, json={"decision": "approved", "option_id": quote["options"][0]["id"]}).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _: decide(), range(2)))
    assert sorted(outcomes) == [200, 409]
    current = client.get(f'/api/v1/orders/{order["id"]}', headers=headers).json()
    assert current["total"] == "144.10"
    assert len(current["items"]) == 3


def test_simultaneous_orders_do_not_duplicate_open_vehicle_order(client, admin_headers, work_order, factory):
    require_postgres(factory)
    order, _, _ = work_order
    client.patch(f'/api/v1/orders/{order["id"]}/status?status=cancelled', headers=admin_headers)
    catalog = client.get("/api/v1/catalogs", headers=admin_headers).json()[0]
    barrier = Barrier(2)
    def create():
        barrier.wait(timeout=10)
        return client.post('/api/v1/orders', headers=admin_headers, json={"vehicle_id": order["vehicle_id"], "catalog_id": catalog["id"]}).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _: create(), range(2)))
    assert sorted(outcomes) == [201, 409]
