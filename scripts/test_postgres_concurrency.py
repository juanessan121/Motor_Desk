"""Concurrencia en una base PostgreSQL desechable, sin tocar bases existentes."""
import os
import secrets
import subprocess
import sys
import time

password = secrets.token_urlsafe(24)
env = dict(os.environ, POSTGRES_PASSWORD=password)
container = subprocess.check_output(['docker', 'run', '--rm', '-d', '-p', '127.0.0.1::5432', '-e', 'POSTGRES_PASSWORD', 'pgvector/pgvector:0.8.7-pg17'], env=env, text=True).strip()
try:
    for _ in range(60):
        if subprocess.run(['docker', 'exec', container, 'pg_isready', '-U', 'postgres'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0:
            break
        time.sleep(1)
    else:
        raise RuntimeError('PostgreSQL de prueba no disponible')
    subprocess.run(['docker', 'exec', container, 'psql', '-U', 'postgres', '-c', 'CREATE EXTENSION IF NOT EXISTS pg_trgm; CREATE EXTENSION IF NOT EXISTS vector;'], check=True)
    port = subprocess.check_output(['docker', 'port', container, '5432'], text=True).strip().split(':')[-1]
    env = dict(os.environ, TEST_DATABASE_URL=f'postgresql+psycopg://postgres:{password}@127.0.0.1:{port}/postgres')
    result = subprocess.run([sys.executable, '-m', 'pytest', 'backend/tests/test_concurrency.py', 'backend/tests/test_maintenance_workflow.py::test_simultaneous_issue_decrements_stock_only_once', '-q'], env=env)
    sys.exit(result.returncode)
finally:
    subprocess.run(['docker', 'rm', '-f', container], stdout=subprocess.DEVNULL, check=True)
