"""Entrega reproducible menor a 10 MB, sin runtime ni datos privados."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import shutil
import tarfile
from zipfile import ZipFile, ZIP_STORED

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN = {'.env', 'server.key', 'integrations.json', 'motordesk.db', 'local.properties', 'key.properties'}
SKIP = {'__pycache__', '.pytest_cache', 'models', '.venv', '.git'}
SECRET = re.compile(rb'(github_pat_[A-Za-z0-9_]{30,}|gh[pousr]_[A-Za-z0-9]{30,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=ROOT / 'dist/MotorDesk-Final-10MB.zip')
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(ROOT / 'dist'):
        parser.error('La entrega debe estar dentro de dist')
    package = ROOT / 'build/lightweight-release'
    package.mkdir(parents=True, exist_ok=True)
    files = [ROOT / name for name in [
        'compose.portable.yaml', 'backend/Dockerfile', 'backend/.dockerignore',
        'backend/requirements.txt', 'backend/requirements.lock', 'backend/alembic.ini',
        'backend/local_entry.py', 'scripts/start_packaged_docker.py',
    ]]
    for folder in ['backend/app', 'backend/migrations', 'backend/scripts', 'build/web']:
        files.extend(p for p in (ROOT / folder).rglob('*') if p.is_file())
    if not (ROOT / 'build/web/main.dart.js').is_file():
        raise RuntimeError('Compile la web antes de crear la entrega.')
    manifest = {}
    payload = package / 'aplicacion.tar.xz'
    with tarfile.open(payload, 'w:xz', preset=9) as archive:
        for path in sorted(set(files)):
            relative = path.relative_to(ROOT).as_posix()
            if SKIP.intersection(path.relative_to(ROOT).parts) or path.suffix == '.pyc':
                continue
            if path.name in FORBIDDEN or path.suffix in {'.db', '.dump', '.key', '.log'}:
                raise RuntimeError('Archivo privado rechazado: ' + relative)
            if '/canvaskit/' in relative and relative not in {
                'build/web/canvaskit/canvaskit.js', 'build/web/canvaskit/canvaskit.wasm',
            }:
                continue
            if path.name == 'flutter_service_worker.js':
                continue
            data = path.read_bytes()
            if path.suffix in {'.py', '.js', '.json', '.yaml', '.txt'} and SECRET.search(data):
                raise RuntimeError('Credencial detectada: ' + relative)
            if path.name == 'flutter_bootstrap.js':
                code = data.decode('utf-8')
                pos = code.rfind('_flutter.loader.load(')
                if pos < 0:
                    raise RuntimeError('Bootstrap Flutter no reconocido')
                data = (code[:pos] + '_flutter.loader.load({config: {renderer: "canvaskit", canvasKitVariant: "full"}});\n').encode()
            info = tarfile.TarInfo(relative)
            info.size, info.mode, info.mtime = len(data), 0o644, 0
            archive.addfile(info, io.BytesIO(data))
            manifest[relative] = hashlib.sha256(data).hexdigest()
    (package / 'aplicacion.sha256').write_text(hashlib.sha256(payload.read_bytes()).hexdigest(), encoding='ascii')
    shutil.copyfile(ROOT / 'scripts/lightweight/iniciar.py', package / 'iniciar.py')
    shutil.copyfile(ROOT / 'docs/entrega_produccion.md', package / 'LEEME.md')
    (package / 'MANIFEST.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    launchers = {'MotorDesk.cmd': '', 'MotorDesk-Docker.cmd': '--docker', 'Detener-Docker.cmd': '--docker --stop', 'Verificar.cmd': '--action check'}
    for name, options in launchers.items():
        (package / name).write_text('@echo off\r\ncd /d "%~dp0"\r\npy -3.14 -I "%~dp0iniciar.py" ' + options + ' %*\r\nif errorlevel 1 (\r\n echo Revise el error. Requiere Python 3.14 x64 e Internet para la primera instalacion.\r\n pause\r\n)\r\n', encoding='ascii')
    output.parent.mkdir(exist_ok=True)
    allowed = ['aplicacion.tar.xz', 'aplicacion.sha256', 'iniciar.py', 'LEEME.md', 'MANIFEST.json', *launchers]
    with ZipFile(output, 'w', ZIP_STORED) as archive:
        for name in allowed:
            archive.write(package / name, 'MotorDesk/' + name)
    if output.stat().st_size > 10_000_000:
        raise RuntimeError(f'ZIP excede 10 MB: {output.stat().st_size} bytes')
    with ZipFile(output) as archive:
        if archive.testzip():
            raise RuntimeError('ZIP dañado')
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix('.sha256').write_text(digest + '  ' + output.name + '\n', encoding='ascii')
    print(json.dumps({'file': str(output), 'bytes': output.stat().st_size, 'sha256': digest}, indent=2))


if __name__ == '__main__':
    main()
