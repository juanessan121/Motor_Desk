"""Prueba el Compose del paquete con datos sintéticos, nunca el taller existente."""
import argparse
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys

parser = argparse.ArgumentParser()
parser.add_argument('package_directory', type=Path)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
directory = args.output.resolve()
directory.mkdir(parents=True, exist_ok=False)
project = 'motordesk-test-package-' + secrets.token_hex(4)
(directory / 'project.txt').write_text(project, encoding='utf-8')
config_file = directory / 'test.env'
config_file.write_text(f'SECRET_KEY={secrets.token_urlsafe(64)}\nPOSTGRES_PASSWORD={secrets.token_urlsafe(32)}\nADMIN_PASSWORD={secrets.token_urlsafe(24)}\nENVIRONMENT=production\nCORS_ORIGINS=[]\nNOTIFICATION_WORKER=false\n', encoding='utf-8')
env = dict(os.environ, MOTORDESK_DOCKER_ENV=str(config_file), MOTORDESK_PORT='8010')
raw = subprocess.check_output(['docker', 'compose', '--env-file', str(config_file), '-f',
    str(args.package_directory.resolve() / 'compose.portable.yaml'), 'config', '--format', 'json'], env=env, text=True)
config = json.loads(raw)
config.pop('name', None)
for volume in config.get('volumes', {}).values():
    volume.pop('name', None)
for network in config.get('networks', {}).values():
    network.pop('name', None)
config['services']['api']['ports'] = ['127.0.0.1::8000']
# Las rutas resueltas siguen apuntando al contenido real del paquete.
(directory / 'compose.yaml').write_text(json.dumps(config), encoding='utf-8')
command = ['docker', 'compose', '-p', project, '--env-file', str(config_file), '-f', str(directory / 'compose.yaml')]
try:
    subprocess.run([*command, 'up', '-d', '--build', '--wait', '--wait-timeout', '300'], check=True, env=env)
    subprocess.run([sys.executable, str(Path(__file__).with_name('test_docker_portability.py')), '--directory', str(directory)], check=True, env=env)
finally:
    subprocess.run([*command, 'down', '--volumes'], check=True, env=env)
