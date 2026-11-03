import json
from functools import lru_cache
from pathlib import Path

from fastapi import HTTPException


@lru_cache
def templates():
    return json.loads((Path(__file__).parent / "resources" / "vehicle_templates.json").read_text(encoding="utf-8"))["templates"]


def vehicle_template(template_id="sedan-neutral-v1"):
    result = next((item for item in templates() if item["id"] == template_id), None)
    if result is None:
        raise HTTPException(422, "Plantilla desconocida")
    return result


def validate_mapping(template_id, component_id, view_id):
    template = vehicle_template(template_id)
    if component_id not in {item["id"] for item in template["components"]}:
        raise HTTPException(422, "Componente desconocido para esta plantilla")
    if view_id not in {item["id"] for item in template["views"]}:
        raise HTTPException(422, "Vista desconocida para esta plantilla")
