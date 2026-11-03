"""Actualiza documentación y checksums de una distribución ya construida/probada."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
from zipfile import ZipFile, ZIP_DEFLATED

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('directory', type=Path)
args = parser.parse_args()
directory = args.directory.resolve()
if not directory.is_relative_to(root / 'dist') or not (directory / 'runtime/python.exe').is_file():
    parser.error('Seleccione una distribución con runtime dentro de dist')
for name, target in [('instalacion_local.md', 'LEEME.md'), ('portabilidad_resultados.md', 'portabilidad_resultados.md'),
                     ('avance_prompt_maestro.md', 'avance_prompt_maestro.md'), ('matriz_prompt_maestro.md', 'matriz_prompt_maestro.md'),
                     ('notificaciones_distribucion.md', 'notificaciones_distribucion.md')]:
    shutil.copy2(root / 'docs' / name, directory / target)
output = root / 'dist/MotorDesk-Windows-Runtime-x64.zip'
with ZipFile(output, 'w', ZIP_DEFLATED) as archive:
    for path in directory.rglob('*'):
        if path.is_file() and '__pycache__' not in path.parts:
            archive.write(path, 'MotorDesk/' + path.relative_to(directory).as_posix())
artifacts = []
for path in [output, root / 'dist/MotorDesk-Tecnico.zip']:
    with ZipFile(path) as archive:
        if archive.testzip():
            raise RuntimeError('ZIP corrupto: ' + path.name)
        forbidden = {'.env', 'server.key', 'motordesk.db', 'integrations.json', 'local.properties', 'key.properties'}
        if any(Path(name).name in forbidden for name in archive.namelist()):
            raise RuntimeError('Archivo privado inesperado en ' + path.name)
    artifacts.append({'name': path.name, 'bytes': path.stat().st_size, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
(root / 'dist/SHA256SUMS.txt').write_text(''.join(f"{item['sha256']}  {item['name']}\n" for item in artifacts), encoding='ascii')
(root / 'dist/release-manifest.json').write_text(json.dumps({'artifacts': artifacts,
    'report': 'docs/notificaciones_distribucion.md', 'scope': 'Avance del prompt maestro; consultar matriz de pendientes'}, indent=2), encoding='utf-8')
print(json.dumps(artifacts, indent=2))
