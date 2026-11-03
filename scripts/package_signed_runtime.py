"""Distribución con el runtime CPython firmado, sin generar ejecutables nuevos.
La firma del intérprete se verifica en el script PowerShell antes de copiarlo.
"""
from pathlib import Path
import json
import argparse
import shutil
import sys
import subprocess
from zipfile import ZipFile, ZIP_DEFLATED
root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--output', type=Path, default=root/'dist/MotorDesk-Runtime')
args = parser.parse_args()
output = args.output.resolve()
if output.exists():
    raise SystemExit('El directorio de salida existe; use otro nombre o archive la entrega anterior.')
output.mkdir(parents=True)
runtime = output / 'runtime'
runtime.mkdir()
base = Path(sys.base_prefix)
for path in base.iterdir():
    if path.is_file() and (path.suffix.lower() in {'.exe', '.dll', '.zip'} or path.name == 'LICENSE.txt'):
        if path.name not in {'pythonw.exe', 'python.exe'} and path.suffix == '.exe':
            continue
        shutil.copy2(path, runtime/path.name)
for name in ['Lib', 'DLLs']:
    shutil.copytree(base/name, runtime/name,
        ignore=shutil.ignore_patterns('site-packages', '__pycache__', 'test', 'tests', 'idlelib', 'ensurepip'))
# Copiar las dependencias resueltas, nunca la configuración del entorno virtual.
shutil.copytree(root/'.venv/Lib/site-packages', runtime/'Lib/site-packages',
    ignore=shutil.ignore_patterns('__pycache__', 'tests', 'test', 'pip', 'pip-*', 'onnxruntime', 'onnxruntime-*',
        'tokenizers', 'tokenizers-*', 'PyInstaller', 'pyinstaller*', '_pyinstaller_hooks_contrib'))
for path in (runtime/'Lib/site-packages').glob('*.pth'):
    # No heredar referencias externas ni ejecutar hooks de desarrollo al arrancar.
    path.unlink()
shutil.copytree(root/'backend/app', output/'backend/app', ignore=shutil.ignore_patterns('__pycache__', 'models'))
shutil.copy2(root/'backend/local_entry.py', output/'backend/local_entry.py')
for name in ['Dockerfile', '.dockerignore', 'requirements.txt', 'requirements.lock', 'alembic.ini']:
    shutil.copy2(root/'backend'/name, output/'backend'/name)
for folder in ['migrations', 'scripts']:
    shutil.copytree(root/'backend'/folder, output/'backend'/folder, ignore=shutil.ignore_patterns('__pycache__'))
(output/'scripts').mkdir()
shutil.copy2(root/'scripts/start_packaged_docker.py', output/'scripts/start_packaged_docker.py')
shutil.copy2(root/'compose.portable.yaml', output/'compose.portable.yaml')
for name, args in [('MotorDesk-Docker.cmd',''), ('Detener-Docker.cmd','--stop')]:
    (output/name).write_text('@echo off\r\n"%~dp0runtime\\python.exe" -I "%~dp0scripts\\start_packaged_docker.py" '+args+' %*\r\nif errorlevel 1 pause\r\n', encoding='ascii')
shutil.copytree(root/'build/web', output/'build/web')
for source, name in [('docs/instalacion_local.md','LEEME.md'), ('docs/portabilidad_resultados.md','portabilidad_resultados.md'),
                     ('docs/avance_prompt_maestro.md','avance_prompt_maestro.md'), ('docs/matriz_prompt_maestro.md','matriz_prompt_maestro.md'),
                     ('docs/notificaciones_distribucion.md','notificaciones_distribucion.md'),
                     ('integrations.example.json','integrations.example.json')]:
    shutil.copy2(root/source, output/name)
for name, command in [('MotorDesk.cmd','serve'), ('Respaldar.cmd','backup'), ('Verificar.cmd','check')]:
    (output/name).write_text('@echo off\r\n"%~dp0runtime\\python.exe" -I "%~dp0backend\\local_entry.py" '+command+' %*\r\nif errorlevel 1 pause\r\n', encoding='ascii')
(output/'Restaurar.cmd').write_text('@echo off\r\necho La restauracion requiere una carpeta NUEVA.\r\nset /p "target=Carpeta nueva para los datos: "\r\n"%~dp0runtime\\python.exe" -I "%~dp0backend\\local_entry.py" restore --data-dir "%target%"\r\npause\r\n',encoding='ascii')
(output/'runtime-manifest.json').write_text(json.dumps({'python':sys.version,'platform':sys.platform,
    'entry':'runtime/python.exe -I backend/local_entry.py', 'external_runtime_required':False},indent=2),encoding='utf-8')
subprocess.run([sys.executable, str(root/'scripts/package_licenses.py'), '--output', str(output/'LICENSES')], check=True)
with ZipFile(root/'dist/MotorDesk-Windows-Runtime-x64.zip','w',ZIP_DEFLATED,compresslevel=6) as archive:
    for path in output.rglob('*'):
        if path.is_file():
            archive.write(path, 'MotorDesk/'+path.relative_to(output).as_posix())
print('Paquete creado: dist/MotorDesk-Windows-Runtime-x64.zip')
