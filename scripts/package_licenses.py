"""Incluye avisos de licencias instaladas en el paquete distribuible."""
import importlib.metadata
import argparse
import json
from pathlib import Path
import shutil
import sys
root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--output', type=Path, default=root/'dist/MotorDesk/LICENSES')
args = parser.parse_args()
output = args.output
output.mkdir(parents=True, exist_ok=True)
manifest = []
for dist in importlib.metadata.distributions():
    name = dist.metadata['Name'] or 'unknown'
    manifest.append({'name': name, 'version': dist.version, 'license': dist.metadata.get('License-Expression') or dist.metadata.get('License', '')})
    for file in dist.files or []:
        if any(word in file.name.lower() for word in ('license', 'copying', 'notice')) and '.dist-info' in str(file):
            source = Path(dist.locate_file(file))
            if source.is_file():
                destination = output / name / file.name
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, destination)
python_license = Path(sys.base_prefix) / 'LICENSE.txt'
if python_license.exists():
    shutil.copyfile(python_license, output / 'Python-LICENSE.txt')
(output / 'dependencies.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
