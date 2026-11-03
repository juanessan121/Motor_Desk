import os
from pathlib import Path
import subprocess
import sys


def test_static_bundle_revalidates_and_cannot_be_framed(client, tmp_path, monkeypatch):
    from app.settings import settings
    (tmp_path / 'main.dart.js').write_text('/* synthetic bundle */')
    monkeypatch.setattr(settings(), 'web_directory', str(tmp_path))
    response = client.get('/main.dart.js')
    assert response.status_code == 200
    assert response.headers['cache-control'] == 'no-cache'
    assert response.headers['x-frame-options'] == 'DENY'
    assert response.headers['x-content-type-options'] == 'nosniff'


def test_production_disables_interactive_documentation():
    root = Path(__file__).resolve().parents[1]
    env = dict(os.environ, ENVIRONMENT='production', DATABASE_URL='postgresql+psycopg://test:test@127.0.0.1/test',
               SECRET_KEY='synthetic-test-only-' * 4, ADMIN_PASSWORD='synthetic-test-only-admin',
               CORS_ORIGINS='[]', SMTP_HOST='', SMTP_STARTTLS='true', PYTHONPATH=str(root))
    result = subprocess.run([sys.executable, '-c',
        'from app.main import app; assert app.docs_url is None; assert app.redoc_url is None; assert app.openapi_url is None'],
        cwd=root, env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
