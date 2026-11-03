"""Empaqueta el árbol Windows generado y guarda las sumas de los dos ZIP."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import hashlib
root = Path(__file__).resolve().parents[1]
folder = root / 'dist/MotorDesk'
with ZipFile(root / 'dist/MotorDesk-Windows-x64.zip', 'w', ZIP_DEFLATED, compresslevel=6) as archive:
    for path in folder.rglob('*'):
        if path.is_file():
            archive.write(path, path.relative_to(root/'dist').as_posix())
checksums = []
for name in ['MotorDesk-Windows-x64.zip', 'MotorDesk-Tecnico.zip']:
    path = root / 'dist' / name
    if path.exists():
        with path.open('rb') as stream:
            checksums.append(hashlib.file_digest(stream, 'sha256').hexdigest() + '  ' + name)
(root / 'dist/SHA256SUMS.txt').write_text('\n'.join(checksums)+'\n', encoding='utf-8')
print('\n'.join(checksums))
