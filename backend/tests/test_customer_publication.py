"""Publicación de notas y clasificación de actividad para el cliente.

Las notas de una orden son privadas hasta que un administrador las publique
explícitamente. Los eventos de la bandeja del cliente se clasifican y filtran
por permisos de cuenta y dispositivo.
"""
from app.models import InboxEvent


def _orden_de_prueba(client, admin_headers, customer_headers, plate, notes=None):
    customer, _ = customer_headers
    vehicle = client.post("/api/v1/vehicles", headers=admin_headers, json={
        "owner_id": customer["id"], "plate": plate, "brand": "Toyota",
        "model": "Corolla", "year": 2018, "mileage": 1000,
    }).json()
    catalog = client.post("/api/v1/catalogs", headers=admin_headers, json={
        "name": "Servicio de prueba", "base_price": "100.00", "tasks": ["Aceite"],
    }).json()
    resp = client.post("/api/v1/orders", headers=admin_headers, json={
        "vehicle_id": vehicle["id"], "catalog_id": catalog["id"],
        "notes": notes or "",
    })
    assert resp.status_code == 201, resp.text
    orden = resp.json()
    task_id = orden["items"][0]["id"] if orden["items"] else None
    return vehicle["id"], orden["id"], task_id


def test_cliente_no_puede_publicar_notas(client, admin_headers, make_customer):
    customer, headers = make_customer()
    _, order_id, _ = _orden_de_prueba(client, admin_headers, (customer, headers), "NOTE001")
    response = client.post(f"/api/v1/orders/{order_id}/notes/publication", headers=headers, json={
        "published": True, "expected_published": False,
    })
    assert response.status_code == 403


def test_admin_publica_notas_y_cliente_las_ve(client, admin_headers, make_customer):
    customer, customer_headers = make_customer()
    _, order_id, _ = _orden_de_prueba(client, admin_headers,
                                      (customer, customer_headers), "NOTE002",
                                      notes="Revisar frenos delanteros.")

    before = client.get(f"/api/v1/orders/{order_id}", headers=customer_headers).json()
    assert before["notes"] == ""
    assert before["notes_published"] is False

    response = client.post(f"/api/v1/orders/{order_id}/notes/publication", headers=admin_headers, json={
        "published": True, "expected_published": False,
    })
    assert response.status_code == 200, response.text
    assert response.json()["notes_published"] is True

    after = client.get(f"/api/v1/orders/{order_id}", headers=customer_headers).json()
    assert after["notes"] == "Revisar frenos delanteros."
    assert after["notes_published"] is True

    withdrawn = client.post(f"/api/v1/orders/{order_id}/notes/publication", headers=admin_headers, json={
        "published": False, "expected_published": True,
    })
    assert withdrawn.status_code == 200
    again = client.get(f"/api/v1/orders/{order_id}", headers=customer_headers).json()
    assert again["notes"] == ""
    assert again["notes_published"] is False


def test_notas_vacías_no_se_publican(client, admin_headers, make_customer):
    customer, _ = make_customer()
    _, order_id, _ = _orden_de_prueba(client, admin_headers, (customer, None), "NOTE003")
    response = client.post(f"/api/v1/orders/{order_id}/notes/publication", headers=admin_headers, json={
        "published": True, "expected_published": False,
    })
    assert response.status_code == 409


def test_republicación_con_revisión_desfasada(client, admin_headers, make_customer):
    customer, _ = make_customer()
    _, order_id, _ = _orden_de_prueba(client, admin_headers, (customer, None), "NOTE004",
                                      notes="Nota de repetición.")
    client.post(f"/api/v1/orders/{order_id}/notes/publication", headers=admin_headers, json={
        "published": True, "expected_published": False,
    })
    # El estado ya es publicado: esperar "no publicado" choca.
    response = client.post(f"/api/v1/orders/{order_id}/notes/publication", headers=admin_headers, json={
        "published": False, "expected_published": False,
    })
    assert response.status_code == 409


def test_paginación_de_notificaciones_del_cliente(client, admin_headers, make_customer):
    customer, headers = make_customer()
    _, order_id, _ = _orden_de_prueba(client, admin_headers, (customer, headers), "NOTE007")
    primera = client.get("/api/v1/notifications", headers=headers, params={"limit": 5, "offset": 0})
    assert primera.status_code == 200
    assert len(primera.json()) <= 5
    segunda = client.get("/api/v1/notifications", headers=headers, params={"limit": 5, "offset": 5})
    assert segunda.status_code == 200
