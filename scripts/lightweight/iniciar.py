"""Instalación ligera de MotorDesk; requiere Python 3.14."""
import argparse
import hashlib
import os
from pathlib import Path
import subprocess
import struct
import sys
import tarfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--docker', action='store_true')
    parser.add_argument('--stop', action='store_true')
    parser.add_argument('--extraer', action='store_true')
    parser.add_argument('--install-only', action='store_true')
    parser.add_argument('--action', choices=['serve', 'backup', 'restore', 'check'], default='serve')
    parser.add_argument('--file', type=Path)
    args = parser.parse_args()
    if sys.version_info[:2] != (3, 14) or struct.calcsize('P') != 8:
        raise RuntimeError('Instala Python 3.14 de 64 bits desde python.org.')
    root = Path(__file__).resolve().parent
    payload = root / 'aplicacion.tar.xz'
    digest = hashlib.sha256(payload.read_bytes()).hexdigest()
    expected = (root / 'aplicacion.sha256').read_text().strip()
    if digest != expected:
        raise RuntimeError('El paquete está incompleto o dañado. Vuelve a extraer el ZIP.')
    target = root / 'app'
    marker = target / '.paquete'
    if not marker.exists() or marker.read_text() != digest:
        target.mkdir(exist_ok=True)
        print('Preparando la aplicación y el catálogo completo...', flush=True)
        with tarfile.open(payload, 'r:xz') as archive:
            archive.extractall(target, filter='data')
        marker.write_text(digest)
    if args.extraer:
        print('Extracción e integridad correctas.')
        return
    if args.docker:
        command = [sys.executable, '-I', str(target / 'scripts/start_packaged_docker.py')]
        if args.stop:
            command.append('--stop')
    else:
        venv = root / '.venv'
        python = venv / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
        if not python.exists():
            subprocess.run([sys.executable, '-m', 'venv', str(venv)], check=True)
        lock = target / 'backend/requirements.lock'
        version = hashlib.sha256(lock.read_bytes()).hexdigest()
        ready = venv / '.dependencias'
        if not ready.exists() or ready.read_text() != version:
            print('Instalando dependencias. La primera ejecución necesita Internet...', flush=True)
            subprocess.run([str(python), '-m', 'pip', 'install', '-r', str(lock)], check=True)
            ready.write_text(version)
        if args.install_only:
            print('Dependencias instaladas correctamente.')
            return
        command = [str(python), '-I', str(target / 'backend/local_entry.py'), args.action]
        if args.file:
            command.extend(['--file', str(args.file.resolve())])
    subprocess.run(command, cwd=target, check=True)


if __name__ == '__main__':
    try:
        main()
    except (OSError, RuntimeError, subprocess.CalledProcessError, tarfile.TarError) as error:
        print(f'No se pudo iniciar MotorDesk: {error}', file=sys.stderr)
        sys.exit(1)
