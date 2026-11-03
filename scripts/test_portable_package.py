"""Prueba real del paquete en carpeta independiente; solo datos sintéticos.
No sustituye una VM limpia. Mantiene el resultado para inspección.
"""
import argparse
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from zipfile import ZipFile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--package', type=Path, default=Path('dist/MotorDesk-Windows-x64.zip'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--runtime', action='store_true', help='Prueba del paquete CPython firmado')
    parser.add_argument('--lightweight', action='store_true', help='Instala y prueba el ZIP ligero real')
    parser.add_argument('--source', action='store_true', help='Prueba del lanzador desde código, no certifica el ejecutable')
    args = parser.parse_args()
    target = args.output.resolve()
    target.mkdir(parents=True, exist_ok=False)
    if not args.source:
        with ZipFile(args.package) as archive:
            archive.extractall(target)
    executable = target / 'MotorDesk/MotorDesk.exe'
    runner = [sys.executable, '-m', 'app.local'] if args.source else [str(executable)]
    if args.runtime:
        runner = [str(target/'MotorDesk/runtime/python.exe'), '-I', str(target/'MotorDesk/backend/local_entry.py')]
    if args.lightweight:
        subprocess.run([sys.executable, '-I', str(target/'MotorDesk/iniciar.py'), '--install-only'], check=True, timeout=900)
        python = target / ('MotorDesk/.venv/Scripts/python.exe' if os.name == 'nt' else 'MotorDesk/.venv/bin/python')
        runner = [str(python), '-I', str(target/'MotorDesk/app/backend/local_entry.py')]
    data = target / 'datos taller'
    env = os.environ.copy()
    env['PATH'] = str(Path(env.get('SystemRoot', 'C:/Windows')) / 'System32')
    env.pop('PYTHONPATH', None)
    env.pop('PYTHONHOME', None)
    if args.source:
        env['PYTHONPATH'] = str(Path(__file__).resolve().parents[1] / 'backend')
    if args.runtime:
        probe = subprocess.check_output([runner[0], '-I', '-c',
            'import sys,json,sqlalchemy,pwdlib; print(json.dumps([sys.prefix,sqlalchemy.__file__,pwdlib.__file__]))'],
            cwd=target, env=env, text=True)
        assert all(Path(path).resolve().is_relative_to(target) for path in json.loads(probe)), probe
        launcher = subprocess.run([env.get('COMSPEC', 'cmd.exe'), '/d', '/c', str(target/'MotorDesk/MotorDesk.cmd'), '--help'],
            cwd=target, env=env, capture_output=True, text=True, timeout=30)
        assert launcher.returncode == 0 and '--data-dir' in launcher.stdout, launcher.stderr
    password = secrets.token_urlsafe(24)
    def cli(*params, input=None):
        result = subprocess.run([*runner, *params, '--data-dir', str(data)], input=input,
            text=True, capture_output=True, cwd=target, env=env, timeout=60)
        if result.returncode:
            raise RuntimeError(result.stdout + result.stderr)
        return result.stdout
    cli('init', input=json.dumps({'name': 'Taller de prueba portable', 'email': 'portable@example.com', 'password': password}))
    with socket.socket() as available:
        available.bind(('127.0.0.1', 0)); port = available.getsockname()[1]
    base = f'http://127.0.0.1:{port}'
    token = None
    def request(method, path, body=None):
        headers = {'Content-Type': 'application/json'}
        if token:
            headers['Authorization'] = 'Bearer ' + token
        query = urllib.request.Request(base + path, data=json.dumps(body).encode() if body is not None else None,
                                       headers=headers, method=method)
        with urllib.request.urlopen(query, timeout=20) as response:
            return json.load(response)
    log = (target / 'server.log').open('w', encoding='utf-8')
    def start():
        process = subprocess.Popen([*runner, '--data-dir', str(data), '--port', str(port), '--no-browser'],
            cwd=target, env=env, stdout=log, stderr=log)
        for _ in range(80):
            if process.poll() is not None:
                raise RuntimeError('Servidor terminado; consulte server.log')
            try:
                request('GET', '/api/v1/health'); return process
            except OSError:
                time.sleep(.25)
        process.terminate(); process.wait(timeout=10)
        raise RuntimeError('Servidor no disponible')
    process = start()
    try:
        token = request('POST', '/api/v1/auth/login', {'username': 'admin', 'password': password})['access_token']
        makes = request('GET', '/api/v1/catalog/makes')
        assert makes, 'El catálogo precargado está vacío'
        assert request('GET', f"/api/v1/catalog/models?make_id={makes[0]['id']}")
        assert request('GET', '/api/v1/catalog/parts')['total'] > 0
        with urllib.request.urlopen(base + '/flutter_bootstrap.js') as response:
            assert 'canvaskit' in response.read().decode()
        customer = request('POST', '/api/v1/customers', {'national_id': 'PORTABLE-001', 'first_name': 'Cliente',
            'last_name': 'Sintético', 'email': 'cliente.portable@example.com', 'phone': '0990000000'})
        vehicle = request('POST', '/api/v1/vehicles', {'owner_id': customer['id'], 'plate': 'POR-1234',
            'brand': 'Toyota', 'model': 'Corolla', 'year': 2020, 'mileage': 1000})
        catalog = request('POST', '/api/v1/catalogs', {'name': 'Inspección portable', 'base_price': '20.00', 'tasks': ['Revisar frenos']})
        order = request('POST', '/api/v1/orders', {'vehicle_id': vehicle['id'], 'catalog_id': catalog['id']})
        assert order['items']
        notices = request('GET', '/api/v1/notifications')
        assert notices and all(n['status'] == 'pending' for n in notices)
        payload = request('GET', '/api/v1/export/workshop-data')
        assert len(payload['clientes']) == 1 and len(payload['mantenimientos']) == 1
        assert 'Contraseña temporal:' not in json.dumps(payload)
        (target / 'academico-sintetico.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    finally:
        process.terminate(); process.wait(timeout=15)
    process = start()
    try:
        token = request('POST', '/api/v1/auth/login', {'username': 'admin', 'password': password})['access_token']
        assert len(request('GET', '/api/v1/customers')) == 1
        assert request('GET', f"/api/v1/orders/{order['id']}")['vehicle_id'] == vehicle['id']
    finally:
        process.terminate(); process.wait(timeout=15); log.close()
    cli('check')
    backup = target / 'operativo.json'
    cli('backup', '--file', str(backup))
    data = target / 'datos restaurados'
    cli('restore', '--file', str(backup))
    cli('check')
    print(json.dumps({'result': 'passed', 'mode': 'source' if args.source else ('lightweight' if args.lightweight else ('signed-runtime' if args.runtime else 'package')), 'package': str(args.package), 'directory': str(target),
                      'checks': ['setup', 'login', 'bundled_catalog_selectors', 'web', 'customer', 'vehicle', 'order', 'pending_notifications',
                                 'academic_export', 'restart_persistence', 'integrity', 'backup', 'restore']}, indent=2))


if __name__ == '__main__':
    main()
