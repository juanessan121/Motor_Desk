import os
import re
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["SECRET_KEY"] = "test-only-key-not-for-production-0000000000000000000000"
os.environ["ADMIN_PASSWORD"] = "test-only-admin-password"
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["NOTIFICATION_WORKER"] = "false"
os.environ["ENVIRONMENT"] = "development"
os.environ["SMTP_HOST"] = ""
os.environ["SMTP_FROM"] = ""
os.environ["TELEGRAM_BOT_TOKEN"] = ""

from app import bootstrap, dependencies, notifications, security
from app.database import Base
from app.main import app
from app.models import Notification
from app.security import decrypt_payload


@pytest.fixture
def factory(monkeypatch):
    url = os.environ.get("TEST_DATABASE_URL")
    admin_engine = None
    schema = None
    if url:
        if not url.startswith("postgresql"):
            raise ValueError("TEST_DATABASE_URL debe apuntar a PostgreSQL de pruebas")
        url = url.replace("@localhost:", "@127.0.0.1:")
        schema = "test_" + uuid4().hex
        admin_engine = create_engine(url, isolation_level="AUTOCOMMIT", connect_args={"connect_timeout": 10})
        with admin_engine.connect() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        # pgvector se instala en public; las tablas de prueba se crean y
        # consultan primero en el esquema aleatorio aislado.
        engine = create_engine(url, connect_args={"options": f"-csearch_path={schema},public", "connect_timeout": 10})
        # Sin traducción explícita, create_all(checkfirst=True) detectaría
        # tablas homónimas de public y las reutilizaría en vez de aislarlas.
        engine = engine.execution_options(schema_translate_map={None: schema})
    else:
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        from sqlalchemy import event
        @event.listens_for(engine, "connect")
        def foreign_keys(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    for module in (bootstrap, dependencies, notifications):
        monkeypatch.setattr(module, "SessionLocal", factory)
    security._attempts.clear()
    bootstrap.bootstrap()
    yield factory
    engine.dispose()
    if admin_engine:
        with admin_engine.connect() as connection:
            # Solo se elimina el esquema aleatorio creado por esta prueba.
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin_engine.dispose()


@pytest.fixture
def client(factory):
    with TestClient(app) as client:
        yield client


@pytest.fixture
def admin_headers(client):
    response = client.post("/api/v1/auth/login", json={"username": "admin", "password": "test-only-admin-password"})
    assert response.status_code == 200, response.text
    headers = {"Authorization": "Bearer " + response.json()["access_token"]}
    response = client.post("/api/v1/auth/password", headers=headers, json={"current_password": "test-only-admin-password", "new_password": "changed-admin-password-123"})
    assert response.status_code == 200, response.text
    return {"Authorization": "Bearer " + response.json()["access_token"]}


@pytest.fixture
def make_customer(client, admin_headers, factory):
    def create(suffix="1", device=None):
        response = client.post("/api/v1/customers", headers=admin_headers, json={
            "national_id": "100000" + suffix, "first_name": "Cliente", "last_name": suffix,
            "email": f"cliente{suffix}@example.com", "address": "Quito", "phone": "0990000000",
        })
        assert response.status_code == 201, response.text
        customer = response.json()
        with factory() as db:
            notification = db.scalar(select(Notification).where(Notification.user_id == customer["user_id"]))
            payload = decrypt_payload(notification.encrypted_payload)
        password = re.search(r"Contraseña temporal: (\S+)", payload["body"])[1]
        headers = {"X-Device-Id": device or str(uuid4())}
        login = client.post("/api/v1/auth/login", headers=headers, json={"username": customer["username"], "password": password})
        assert login.status_code == 200, login.text
        headers["Authorization"] = "Bearer " + login.json()["access_token"]
        change = client.post("/api/v1/auth/password", headers=headers, json={"current_password": password, "new_password": "new-customer-password-123"})
        assert change.status_code == 200, change.text
        headers["Authorization"] = "Bearer " + change.json()["access_token"]
        return customer, headers
    return create


@pytest.fixture
def work_order(client, admin_headers, make_customer):
    customer, headers = make_customer()
    vehicle = client.post("/api/v1/vehicles", headers=admin_headers, json={
        "owner_id": customer["id"], "plate": "abc-123", "brand": "Toyota", "model": "Corolla", "year": 2020, "mileage": 50000,
    })
    assert vehicle.status_code == 201, vehicle.text
    catalog = client.post("/api/v1/catalogs", headers=admin_headers, json={
        "name": "Mantenimiento 50.000 km", "base_price": "100.10", "tasks": ["Aceite", "Filtros"],
    })
    assert catalog.status_code == 201, catalog.text
    order = client.post("/api/v1/orders", headers=admin_headers, json={"vehicle_id": vehicle.json()["id"], "catalog_id": catalog.json()["id"]})
    assert order.status_code == 201, order.text
    return order.json(), customer, headers
