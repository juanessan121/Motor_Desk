"""Lanzador opcional Docker del ZIP; configuración privada fuera del programa."""
import argparse
import getpass
import os
from pathlib import Path
import secrets
import subprocess
import sys
import webbrowser


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8010)
    parser.add_argument('--stop', action='store_true')
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error('Puerto entre 1024 y 65535')
    root = Path(__file__).resolve().parents[1]
    private = Path(os.environ.get('LOCALAPPDATA', Path.home() / '.local/share')) / 'MotorDeskDocker'
    private.mkdir(parents=True, exist_ok=True)
    config = private / 'server.env'
    subprocess.run(['docker', 'info'], check=True, stdout=subprocess.DEVNULL)
    if not config.exists():
        if args.stop:
            return
        print('Primera ejecución con Docker. Usuario administrador: admin.')
        password = getpass.getpass('Nueva contraseña (mínimo 12 caracteres): ')
        if len(password) < 12 or len(password) > 200 or any(c in password for c in '\r\n'):
            raise ValueError('Contraseña inválida')
        if password != getpass.getpass('Repita la contraseña: '):
            raise ValueError('Las contraseñas no coinciden')
        # Compose no interpola valores dentro de comillas simples en --env-file.
        if "'" in password or '\\' in password:
            raise ValueError('Este configurador no admite comillas simples ni barras invertidas')
        with config.open('x', encoding='utf-8') as out:
            out.write(f"SECRET_KEY={secrets.token_urlsafe(64)}\nPOSTGRES_PASSWORD={secrets.token_urlsafe(32)}\nADMIN_PASSWORD='{password}'\nENVIRONMENT=production\nCORS_ORIGINS=[]\n")
        if os.name != 'nt':
            config.chmod(0o600)
    env = dict(os.environ, MOTORDESK_DOCKER_ENV=str(config), MOTORDESK_PORT=str(args.port))
    command = ['docker', 'compose', '-p', 'motordesk-portable', '--env-file', str(config), '-f', str(root / 'compose.portable.yaml')]
    if args.stop:
        subprocess.run([*command, 'stop'], env=env, check=True)
        return
    subprocess.run([*command, 'up', '-d', '--build', '--wait', '--wait-timeout', '300'], env=env, check=True)
    url = f'http://127.0.0.1:{args.port}'
    print(f'MotorDesk disponible en {url}. Los datos permanecen en el volumen Docker.')
    webbrowser.open(url)


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f'No se pudo iniciar. Abra Docker Desktop y revise la configuración. {type(error).__name__}', file=sys.stderr)
        sys.exit(1)
