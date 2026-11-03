"""Entrada única para instalaciones locales, sin depender del .env del proyecto."""
import argparse
import contextlib
import getpass
import json
import os
from pathlib import Path
import secrets
import sys
import threading
import time
import urllib.request
import webbrowser


def resource_root():
    return Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[1]))


@contextlib.contextmanager
def installation_lock(directory):
    lock = (directory / 'instance.lock').open('a+b')
    try:
        lock.seek(0)
        if os.name == 'nt':
            import msvcrt
            if not lock.read(1):
                lock.write(b'0'); lock.flush()
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        lock.close()
        raise RuntimeError('MotorDesk está abierto. Cierre el servidor antes de continuar.')
    try:
        yield
    finally:
        lock.close()


def configure(directory):
    directory.mkdir(parents=True, exist_ok=True)
    key_file = directory / 'server.key'
    if not key_file.exists():
        if (directory / 'motordesk.db').exists():
            raise ValueError('Falta server.key de esta instalación. Recupere la clave original o restaure un respaldo JSON en una carpeta nueva.')
        with key_file.open('x', encoding='utf-8') as stream:
            stream.write(secrets.token_urlsafe(64))
        if os.name != 'nt':
            key_file.chmod(0o600)
    # El fichero .env de desarrollo nunca decide la base ni las integraciones locales.
    os.environ.update(DATABASE_URL='sqlite:///' + (directory / 'motordesk.db').as_posix(),
                      SECRET_KEY=key_file.read_text(encoding='utf-8').strip(),
                      ADMIN_PASSWORD=secrets.token_urlsafe(32), ENVIRONMENT='local',
                      SMTP_HOST='', SMTP_FROM='', SMTP_USERNAME='', SMTP_PASSWORD='',
                      TELEGRAM_BOT_TOKEN='', NOTIFICATION_WORKER='true')
    integrations = directory / 'integrations.json'
    if integrations.exists():
        allowed = {'SMTP_HOST', 'SMTP_PORT', 'SMTP_USERNAME', 'SMTP_PASSWORD', 'SMTP_FROM',
                   'SMTP_STARTTLS', 'TELEGRAM_BOT_TOKEN'}
        values = json.loads(integrations.read_text(encoding='utf-8-sig'))
        if not isinstance(values, dict) or set(values) - allowed:
            raise ValueError('integrations.json contiene opciones no admitidas')
        os.environ.update({k: str(v).lower() if isinstance(v, bool) else str(v) for k, v in values.items()})
    from .settings import settings
    settings.cache_clear()


def setup(factory, name, email, password):
    import copy
    from sqlalchemy import select
    from pydantic import EmailStr, TypeAdapter
    from .models import Workshop, User, AppConfiguration
    from .branding import DEFAULT_CONFIG
    from .security import password_hasher
    from .maintenance_service import seed_templates
    if not 1 <= len(name.strip()) <= 100:
        raise ValueError('Nombre del taller: entre 1 y 100 caracteres')
    email = str(TypeAdapter(EmailStr).validate_python(email)).lower()
    if len(password) < 12 or len(password) > 256:
        raise ValueError('La contraseña debe tener entre 12 y 256 caracteres')
    with factory.begin() as db:
        if db.scalar(select(User.id).where(User.role == 'admin')):
            raise ValueError('La instalación ya tiene administrador')
        db.add(Workshop(id=1, name=name.strip()))
        db.flush()
        user = User(username='admin', email=email, password_hash=password_hasher.hash(password),
                    role='admin', active=True, must_change_password=False, workshop_id=1)
        db.add(user)
        payload = copy.deepcopy(DEFAULT_CONFIG)
        payload['branding']['name'] = name.strip()
        db.add(AppConfiguration(scope='global', payload=payload))
        db.flush()
        seed_templates(db, user)


def first_run(factory, *, graphical=False):
    from sqlalchemy import select
    from .models import User
    with factory() as db:
        if db.scalar(select(User.id).where(User.role == 'admin')):
            return
    if graphical:
        from .local_wizard import run_wizard
        run_wizard(factory)
        return
    print('\nBienvenido a MotorDesk. Configuración inicial sin servicios externos.')
    while True:
        name = input('Nombre del taller: ').strip()
        email = input('Correo del administrador: ').strip()
        password = getpass.getpass('Contraseña del administrador (mínimo 12 caracteres): ')
        if password != getpass.getpass('Repita la contraseña: '):
            print('Las contraseñas no coinciden.'); continue
        try:
            setup(factory, name, email, password)
            print('Administrador creado. Usuario: admin. Configure precios antes de usar las plantillas.')
            return
        except ValueError as exc:
            print(exc)


def main():
    parser = argparse.ArgumentParser(description='MotorDesk Local')
    parser.add_argument('command', nargs='?', default='serve', choices=['serve', 'backup', 'restore', 'check', 'init'])
    parser.add_argument('--data-dir', type=Path, default=Path(os.environ.get('LOCALAPPDATA', Path.home() / '.local/share')) / 'MotorDesk')
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--file', type=Path)
    parser.add_argument('--web-dir', type=Path)
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args()
    directory = args.data_dir.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    with installation_lock(directory):
        configure(directory)
        from .database import engine, SessionLocal
        from .local_schema import initialize_database
        if args.command == 'restore':
            from .local_backup import restore_backup
            source = args.file or Path(input('Archivo JSON del respaldo: ').strip().strip('"'))
            restore_backup(source, directory / 'motordesk.db')
            print('Restauración validada. Las integraciones deben configurarse por separado.')
            return
        initialize_database(engine)
        if args.command == 'init':
            values = json.load(sys.stdin)
            setup(SessionLocal, values['name'], values['email'], values['password'])
            from .bundled_catalog import seed_bundled_catalog
            seed_bundled_catalog(SessionLocal)
            print('Instalación inicializada')
            return
        if args.command == 'backup':
            from .local_backup import export_backup
            output = args.file or directory / ('respaldo-' + time.strftime('%Y%m%d-%H%M%S') + '.json')
            export_backup(engine, output)
            print(f'Respaldo guardado: {output}')
            return
        if args.command == 'check':
            from sqlalchemy import text
            with engine.connect() as connection:
                if connection.scalar(text('PRAGMA integrity_check')) != 'ok':
                    raise ValueError('La base no superó la comprobación de integridad')
                if connection.execute(text('PRAGMA foreign_key_check')).all():
                    raise ValueError('La base contiene referencias inválidas')
            print('Integridad SQLite y claves foráneas: correctas')
            return
        first_run(SessionLocal, graphical=not args.no_browser)
        from .bundled_catalog import seed_bundled_catalog
        seed_bundled_catalog(SessionLocal)
        root = resource_root()
        web = args.web_dir or (root / 'web' if getattr(sys, 'frozen', False) else root.parent / 'build/web')
        if not (web / 'index.html').is_file():
            raise ValueError('Falta la interfaz compilada. Ejecute flutter build web --release --no-web-resources-cdn o use el paquete completo.')
        from .settings import settings
        settings().web_directory = str(web.resolve())
        url = f'http://127.0.0.1:{args.port}'
        print(f'MotorDesk: {url}\nDatos: {directory}\nCierre con Ctrl+C antes de respaldar o actualizar.')
        if not args.no_browser:
            def open_when_ready():
                for _ in range(60):
                    try:
                        with urllib.request.urlopen(url + '/api/v1/health', timeout=1) as response:
                            if response.status == 200:
                                webbrowser.open(url); return
                    except OSError:
                        time.sleep(.5)
            threading.Thread(target=open_when_ready, daemon=True).start()
        import uvicorn
        uvicorn.run('app.main:app', host='127.0.0.1', port=args.port, workers=1)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, RuntimeError, OSError) as exc:
        print(f'MotorDesk no pudo continuar: {exc}', file=sys.stderr)
        sys.exit(1)
