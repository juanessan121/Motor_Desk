"""Descarga referencias públicas, guarda licencias y hashes; no accede al taller."""
import hashlib
import json
from pathlib import Path
import urllib.request

target = Path(__file__).resolve().parents[1] / 'backend/app/resources/catalog'
target.mkdir(parents=True, exist_ok=True)
sources = {
    'vehicles.sqlite': 'https://raw.githubusercontent.com/gor3a/vehicle-makes-models/main/data/vehicles.sqlite',
    'part_terms.json': 'https://raw.githubusercontent.com/lifeofcapo/car-api/main/car-parts.json',
    'LICENSE-vehicles.txt': 'https://raw.githubusercontent.com/gor3a/vehicle-makes-models/main/LICENSE-DATA',
    'LICENSE-parts.txt': 'https://raw.githubusercontent.com/lifeofcapo/car-api/main/LICENSE',
}
manifest = {}
for name, url in sources.items():
    path = target / name
    if not path.exists():
        request = urllib.request.Request(url, headers={'User-Agent': 'MotorDesk-Catalog/1.0'})
        with urllib.request.urlopen(request, timeout=60) as response:
            with path.with_suffix(path.suffix + '.part').open('wb') as output:
                while chunk := response.read(1024 * 1024):
                    output.write(chunk)
        path.with_suffix(path.suffix + '.part').replace(path)
    manifest[name] = {'url': url, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'bytes': path.stat().st_size}
    print(name, path.stat().st_size, flush=True)
(target / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
