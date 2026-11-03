"""Paquete técnico por lista permitida: nunca incluye .env, datos ni respaldos."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
root = Path(__file__).resolve().parents[1]
folders = ['android', 'lib', 'web', 'assets', 'test', 'backend/app', 'backend/migrations', 'backend/tests', 'backend/scripts', 'scripts']
files = ['.metadata', 'README.md', 'MotorDesk.cmd', 'compose.yaml', 'compose.portable.yaml', 'integrations.example.json', '.env.example', '.gitignore',
         'pubspec.yaml', 'pubspec.lock', 'analysis_options.yaml', 'backend/requirements.txt',
         'backend/.dockerignore', 'backend/Dockerfile.incremental', 'backend/requirements.lock', 'backend/alembic.ini', 'backend/Dockerfile', 'backend/local_entry.py',
         'docs/notificaciones_distribucion.md', 'docs/requisitos_maestros.md', 'docs/matriz_prompt_maestro.md', 'docs/avance_prompt_maestro.md',
         'docs/ejemplo_academico_sintetico.json', 'docs/instalacion_local.md', 'docs/portabilidad_resultados.md', 'docs/motordesk_workshop_schema.json']
files += ['docs/entrega_produccion.md', 'docs/validacion_entrega_20261103.md', 'docs/release-validation.json', '.github/workflows/verify.yml']
(root / 'dist').mkdir(exist_ok=True)
with ZipFile(root / 'dist/MotorDesk-Tecnico.zip', 'w', ZIP_DEFLATED) as archive:
    for relative in files:
        path = root / relative
        if path.exists():
            archive.write(path, 'MotorDesk/' + relative)
    for folder in folders:
        for path in (root / folder).rglob('*'):
            if path.is_file() and not any(p in {'__pycache__', 'models', '.pytest_cache', '.gradle', '.kotlin', '.cxx', 'build'} for p in path.parts):
                if path.suffix in {'.pyc', '.db', '.key', '.log', '.jks', '.keystore', '.iml'} or path.name in {'.env', 'integrations.json', 'local.properties', 'key.properties', 'google-services.json'}:
                    continue
                archive.write(path, 'MotorDesk/' + path.relative_to(root).as_posix())
print('Paquete técnico: dist/MotorDesk-Tecnico.zip')
