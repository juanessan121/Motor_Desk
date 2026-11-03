"""Valida esquema, formatos y relaciones sin importar ni modificar registros."""
import argparse
import json
from pathlib import Path
import sys
from jsonschema import Draft7Validator, FormatChecker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.academic_validation import relational_errors

parser = argparse.ArgumentParser()
parser.add_argument('file', type=Path)
parser.add_argument('--schema', type=Path, default=Path(__file__).resolve().parents[2] / 'docs/motordesk_workshop_schema.json')
args = parser.parse_args()
payload = json.loads(args.file.read_text(encoding='utf-8-sig'))
schema = json.loads(args.schema.read_text(encoding='utf-8-sig'))
errors = [f'{list(e.path)}: {e.message}' for e in Draft7Validator(schema, format_checker=FormatChecker()).iter_errors(payload)]
if not errors:
    errors = relational_errors(payload)
print(json.dumps({'valid': not errors, 'errors': errors}, ensure_ascii=False, indent=2))
raise SystemExit(bool(errors))
