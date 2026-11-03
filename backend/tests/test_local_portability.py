import json
from pathlib import Path
import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import sessionmaker
from app.database import make_engine
from app.local import setup, installation_lock
from app.local_schema import initialize_database
from app.local_backup import export_backup, restore_backup
from app.models import User, Customer, Notification, MaintenanceCatalog
from app.security import verify_password, encrypt_payload, decrypt_payload


def fresh(path):
    engine = make_engine('sqlite:///' + path.as_posix())
    initialize_database(engine)
    return engine, sessionmaker(bind=engine, expire_on_commit=False)


def test_first_run_persistence_and_backup(tmp_path):
    path = tmp_path / 'original.db'
    engine, factory = fresh(path)
    setup(factory, 'Taller independiente', 'admin@example.com', 'contraseña-única-12345')
    with pytest.raises(ValueError, match='ya tiene'):
        setup(factory, 'Otro taller', 'admin@example.com', 'contraseña-única-12345')
    with factory.begin() as db:
        admin = db.scalar(select(User))
        assert verify_password('contraseña-única-12345', admin.password_hash)
        assert not admin.must_change_password
        assert len(list(db.scalars(select(MaintenanceCatalog)))) == 8
        db.add(Customer(workshop_id=1, national_id='LOCAL-01', first_name='Ana', last_name='Prueba', email='ana@example.com'))
        db.add(Notification(user_id=admin.id, kind='credentials', channel='email',
                            encrypted_payload=encrypt_payload({'body': 'SECRET-ACTIVATION-TOKEN'})))
        db.add(Notification(user_id=admin.id, kind='ready', channel='email',
                            encrypted_payload=encrypt_payload({'title': 'Listo', 'body': 'Su vehículo está listo', 'to': 'ana@example.com'})))
    engine.dispose()
    engine, factory = fresh(path)
    with factory() as db:
        assert db.scalar(select(Customer)).first_name == 'Ana'
    backup = tmp_path / 'backup.json'
    export_backup(engine, backup)
    raw = backup.read_text(encoding='utf-8')
    assert 'SECRET-ACTIVATION-TOKEN' not in raw
    assert 'contraseña-única-12345' not in raw
    with pytest.raises(FileExistsError):
        export_backup(engine, backup)
    restored = tmp_path / 'restored.db'
    restore_backup(backup, restored)
    other, sessions = fresh(restored)
    with sessions() as db:
        assert db.scalar(select(Customer)).first_name == 'Ana'
        notice = db.scalar(select(Notification).where(Notification.kind == 'ready'))
        assert decrypt_payload(notice.encrypted_payload)['body'] == 'Su vehículo está listo'
        assert db.scalar(select(Notification).where(Notification.kind == 'credentials')).status == 'failed'
    with pytest.raises(ValueError, match='existe'):
        restore_backup(backup, restored)
    other.dispose(); engine.dispose()


def test_invalid_backup_never_publishes_destination(tmp_path):
    engine, factory = fresh(tmp_path / 'source.db')
    setup(factory, 'Taller', 'admin@example.com', 'password-local-long')
    source = tmp_path / 'backup.json'
    export_backup(engine, source)
    payload = json.loads(source.read_text(encoding='utf-8'))
    payload['tables']['users'][0]['workshop_id'] = 99999
    source.write_text(json.dumps(payload), encoding='utf-8')
    target = tmp_path / 'bad.db'
    with pytest.raises(ValueError, match='Referencias inválidas'):
        restore_backup(source, target)
    assert not target.exists()
    engine.dispose()


def test_reject_unknown_sqlite_schema(tmp_path):
    engine = make_engine('sqlite:///' + (tmp_path / 'unknown.db').as_posix())
    with engine.begin() as db:
        db.execute(text('CREATE TABLE something (id INTEGER PRIMARY KEY)'))
    with pytest.raises(ValueError, match='incompatible'):
        initialize_database(engine)
    engine.dispose()


def test_only_one_local_instance(tmp_path):
    with installation_lock(tmp_path):
        with pytest.raises(RuntimeError, match='abierto'):
            with installation_lock(tmp_path):
                pytest.fail('Segunda instancia permitida')

def test_confirmed_delivery_retains_business_message(factory, monkeypatch):
    import asyncio
    from app import notifications
    from app.models import utcnow
    from app.security import encrypt_payload
    with factory.begin() as db:
        admin = db.scalar(select(User).where(User.role == 'admin'))
        notice = Notification(user_id=admin.id, kind='ready', channel='email',
            encrypted_payload=encrypt_payload({'title': 'Listo', 'body': 'Retire su vehículo', 'to': 'cliente@example.com'}))
        db.add(notice); db.flush(); notice_id = notice.id
    monkeypatch.setattr(notifications.settings(), 'smtp_host', 'fake.local')
    monkeypatch.setattr(notifications.settings(), 'smtp_from', 'taller@example.com')
    calls = []
    async def delivery(*args):
        calls.append(args)
        return 'confirmed-provider-id'
    monkeypatch.setattr(notifications, 'deliver', delivery)
    assert asyncio.run(notifications.process_one())
    assert not asyncio.run(notifications.process_one())
    with factory() as db:
        row = db.get(Notification, notice_id)
        assert row.status == 'sent' and row.sent_at
        assert row.provider_message_id == 'confirmed-provider-id'
        assert row.body == 'Retire su vehículo'
    assert len(calls) == 1

def test_backup_failure_does_not_leave_partial_file(tmp_path, monkeypatch):
    from app import local_backup
    engine, factory = fresh(tmp_path / 'source.db')
    setup(factory, 'Taller', 'admin@example.com', 'password-local-long')
    def failed_encoding(_):
        raise OSError('Disco no disponible')
    monkeypatch.setattr(local_backup, 'encode', failed_encoding)
    target = tmp_path / 'partial.json'
    with pytest.raises(OSError):
        export_backup(engine, target)
    assert not target.exists()
    assert not list(tmp_path.glob('motordesk-backup-*'))
    engine.dispose()


def test_browser_setup_rejects_foreign_origin_and_is_one_time(tmp_path):
    import http.client
    import threading
    from urllib.parse import urlsplit, urlencode
    from app.local_wizard import create_server
    engine, factory = fresh(tmp_path / 'wizard.db')
    server, url = create_server(factory)
    parsed = urlsplit(url)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    def request(method, path, body=None, origin=None):
        connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=5)
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        if origin:
            headers['Origin'] = origin
        connection.request(method, path, urlencode(body) if body else None, headers)
        response = connection.getresponse()
        result = response.status, response.read().decode()
        connection.close()
        return result
    try:
        assert request('GET', '/incorrect-token')[0] == 404
        assert request('GET', parsed.path)[0] == 200
        values = {'name': 'Mi taller', 'email': 'admin@example.com', 'password': 'personal-secret-123', 'confirm': 'personal-secret-123'}
        assert request('POST', parsed.path, values, 'https://foreign.example')[0] == 403
        assert request('POST', parsed.path, {**values, 'confirm': 'different'})[0] == 422
        with factory() as db:
            assert db.scalar(select(User)) is None
        assert request('POST', parsed.path, values)[0] == 200
        assert request('POST', parsed.path, values)[0] == 403
        assert server.completed
        with factory() as db:
            assert verify_password(values['password'], db.scalar(select(User)).password_hash)
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=5); engine.dispose()


def test_real_smtp_protocol_delivery_once(factory, monkeypatch):
    import asyncio
    import socketserver
    import threading
    from app import notifications
    messages = []
    class SMTP(socketserver.StreamRequestHandler):
        def handle(self):
            self.wfile.write(b'220 localhost test server\r\n')
            while line := self.rfile.readline():
                command = line.split(b' ', 1)[0].strip().upper()
                if command == b'DATA':
                    self.wfile.write(b'354 Send message\r\n')
                    body = []
                    while (part := self.rfile.readline()) != b'.\r\n':
                        if not part:
                            return
                        body.append(part)
                    messages.append(b''.join(body))
                    self.wfile.write(b'250 Accepted\r\n')
                elif command == b'QUIT':
                    self.wfile.write(b'221 Bye\r\n'); return
                else:
                    self.wfile.write(b'250 OK\r\n')
    server = socketserver.TCPServer(('127.0.0.1', 0), SMTP)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    config = notifications.settings()
    for key, value in {'smtp_host': '127.0.0.1', 'smtp_port': server.server_address[1],
                       'smtp_from': 'workshop@example.com', 'smtp_username': '', 'smtp_starttls': False}.items():
        monkeypatch.setattr(config, key, value)
    try:
        with factory.begin() as db:
            admin = db.scalar(select(User).where(User.role == 'admin'))
            row = Notification(user_id=admin.id, kind='ready', channel='email',
                encrypted_payload=encrypt_payload({'title':'Inspección lista', 'body':'Mensaje sintético', 'to':'test@example.com'}))
            db.add(row); db.flush(); identifier = row.id
        assert asyncio.run(notifications.process_one())
        assert not asyncio.run(notifications.process_one())
        assert len(messages) == 1
        with factory() as db:
            row = db.get(Notification, identifier)
            assert row.status == 'sent'
            assert row.provider_message_id.encode() in messages[0]
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=5)
