"""Smoke PostgreSQL en el proyecto Docker de prueba creado para esta entrega."""
import json
import argparse
from pathlib import Path
import secrets
import subprocess
import time
import urllib.request

parser = argparse.ArgumentParser()
parser.add_argument('--directory', type=Path, default=Path('build/docker-portability'))
args = parser.parse_args()
folder = args.directory
project = (folder/'project.txt').read_text().strip() if (folder/'project.txt').exists() else 'motordesk-portability-20261022'
compose = ['docker', 'compose', '-p', project, '--env-file', str(folder/'test.env'), '-f', str(folder/'compose.yaml')]


def run(*args):
    return subprocess.check_output([*compose, *args], text=True).strip()

port = run('port', 'api', '8000')
base = 'http://' + port
config = dict(line.split('=', 1) for line in (folder/'test.env').read_text().splitlines() if '=' in line)
token = None

def request(method, path, body=None):
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    req = urllib.request.Request(base+path, headers=headers, method=method,
        data=json.dumps(body).encode() if body is not None else None)
    with urllib.request.urlopen(req, timeout=20) as response:
        return json.load(response)

token = request('POST', '/api/v1/auth/login', {'username':'admin', 'password':config['ADMIN_PASSWORD']})['access_token']
password = secrets.token_urlsafe(24)
token = request('POST', '/api/v1/auth/password', {'current_password':config['ADMIN_PASSWORD'], 'new_password':password})['access_token']
customer = request('POST','/api/v1/customers',{'national_id':'DOCKER-001','first_name':'Cliente','last_name':'Sintético','email':'docker@example.com'})
vehicle = request('POST','/api/v1/vehicles',{'owner_id':customer['id'],'plate':'DOC-1234','brand':'Toyota','model':'Corolla','year':2020,'mileage':1000})
catalog = request('POST','/api/v1/catalogs',{'name':'Inspección Docker','base_price':'20.00','tasks':['Revisar frenos']})
order = request('POST','/api/v1/orders',{'vehicle_id':vehicle['id'],'catalog_id':catalog['id']})
assert order['items']
assert all(n['status']=='pending' for n in request('GET','/api/v1/notifications'))
run('restart','db','api')
base = 'http://' + run('port', 'api', '8000')
for _ in range(90):
    try:
        request('GET','/api/v1/health'); break
    except OSError:
        time.sleep(.5)
else:
    raise RuntimeError('Servicios no disponibles tras reinicio')
token = request('POST', '/api/v1/auth/login', {'username':'admin', 'password':password})['access_token']
assert request('GET',f"/api/v1/orders/{order['id']}")['vehicle_id']==vehicle['id']
assert len(request('GET','/api/v1/customers'))==1
run('exec','-T','db','pg_dump','-U','workshop','-d','workshop','-Fc','-f','/tmp/portability.dump')
run('exec','-T','db','createdb','-U','workshop','portability_restored')
run('exec','-T','db','pg_restore','-U','workshop','-d','portability_restored','/tmp/portability.dump')
count = run('exec','-T','db','psql','-U','workshop','-d','portability_restored','-Atc','SELECT count(*) FROM work_orders')
assert count=='1', count
revision = run('exec','-T','db','psql','-U','workshop','-d','workshop','-Atc','SELECT version_num FROM alembic_version')
assert revision=='0015',revision
print(json.dumps({'result':'passed','schema':revision,'checks':['fresh_migrations','login','customer','vehicle','order','pending_notifications','restart','persisted_volume','pg_dump','pg_restore']}))
