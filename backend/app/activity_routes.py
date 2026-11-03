"""Catálogo central de actividades de mantenimiento reutilizables."""
import re
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select

from . import schemas
from .access_policy import audit
from .dependencies import Database, admin, authenticated, invalidate
from .models import MaintenanceActivity, User
from .serializers import activity_json

router = APIRouter(prefix="/activities", tags=["Catálogo de actividades"])

DEFAULT_ACTIVITIES = [
    {
        "label": "Cambio de aceite de motor",
        "system": "motor",
        "description": "Drenado de aceite usado y reemplazo por aceite según especificación del fabricante.",
        "estimated_minutes": 30,
        "technical_notes": "Verificar viscosidad y capacidad exacta según manual de taller.",
        "required": True,
    },
    {
        "label": "Revisión y cambio de filtro de aceite",
        "system": "motor",
        "description": "Sustitución del elemento filtrante o cartucho de aceite y lubricación de empaque.",
        "estimated_minutes": 20,
        "technical_notes": "Apretar a torque especificado o 3/4 de vuelta tras contacto.",
        "required": True,
    },
    {
        "label": "Revisión y cambio de filtro de aire",
        "system": "motor",
        "description": "Inspección de saturación del elemento filtrante y limpieza de caja portafiltro.",
        "estimated_minutes": 15,
        "technical_notes": "Reemplazar si presenta acumulación excesiva de polvo o aceite.",
        "required": True,
    },
    {
        "label": "Revisión del sistema de frenos",
        "system": "frenos",
        "description": "Inspección de espesor de pastillas, estado de discos/tambores y latiguillos.",
        "estimated_minutes": 45,
        "technical_notes": "Medir espesor residual de material de fricción en mm.",
        "required": True,
    },
    {
        "label": "Inspección y calibración de neumáticos",
        "system": "seguridad",
        "description": "Medición de profundidad de labrado, desgaste irregular y presión en frío.",
        "estimated_minutes": 20,
        "technical_notes": "Verificar presión recomendada en etiqueta del marco de la puerta.",
        "required": False,
    },
    {
        "label": "Revisión de niveles de fluidos",
        "system": "fluidos",
        "description": "Inspección de líquido de frenos, refrigerante, dirección asistida y limpiaparabrisas.",
        "estimated_minutes": 20,
        "technical_notes": "Comprobar punto de ebullición del líquido de frenos y concentración de refrigerante.",
        "required": True,
    },
    {
        "label": "Diagnóstico electrónico por scanner",
        "system": "electrico",
        "description": "Lectura de códigos de falla (DTC), monitoreo de sensores en vivo y borrado de códigos si aplica.",
        "estimated_minutes": 40,
        "technical_notes": "Documentar códigos históricos y códigos activos antes de borrarlos.",
        "required": False,
    },
    {
        "label": "Revisión de suspensión y amortiguadores",
        "system": "suspension",
        "description": "Inspección de bujes, terminales de dirección, rótulas y fugas en amortiguadores.",
        "estimated_minutes": 40,
        "technical_notes": "Comprobar holguras axiales y radiales en tren delantero y trasero.",
        "required": False,
    },
    {
        "label": "Inspección del sistema de refrigeración",
        "system": "refrigeracion",
        "description": "Prueba de presión de fugas, estado de mangueras, abrazaderas y funcionamiento de electroventilador.",
        "estimated_minutes": 35,
        "technical_notes": "Comprobar tapa del radiador y termostato a temperatura de operación.",
        "required": False,
    },
    {
        "label": "Revisión de batería y sistema de carga",
        "system": "electrico",
        "description": "Prueba de voltaje de reposo, arranque y voltaje del alternador bajo carga.",
        "estimated_minutes": 15,
        "technical_notes": "Voltaje con motor encendido debe situarse entre 13.8V y 14.5V.",
        "required": False,
    },
]


def normalize_label(label: str) -> str:
    cleaned = re.sub(r"\s+", " ", label.strip().lower())
    return cleaned


@router.get("")
def list_activities(
    db: Database,
    user: User = Depends(authenticated),
    system: str | None = None,
    q: str = "",
    include_inactive: bool = False,
):
    query = select(MaintenanceActivity).where(
        MaintenanceActivity.workshop_id == user.workshop_id
    )
    if not include_inactive:
        query = query.where(MaintenanceActivity.active.is_(True))
    if system and system != "all":
        query = query.where(MaintenanceActivity.system == system)
    activities = list(db.scalars(query.order_by(MaintenanceActivity.label)))
    if q:
        query_text = q.lower().strip()
        activities = [
            act
            for act in activities
            if query_text in act.label.lower()
            or query_text in act.description.lower()
            or query_text in act.system.lower()
        ]
    return [activity_json(act) for act in activities]


@router.post("", status_code=201)
def create_activity(
    data: schemas.MaintenanceActivityInput,
    db: Database,
    user: User = Depends(admin),
):
    norm = normalize_label(data.label)
    existing = db.scalar(
        select(MaintenanceActivity).where(
            MaintenanceActivity.workshop_id == user.workshop_id,
            MaintenanceActivity.normalized_label == norm,
        )
    )
    if existing:
        if not existing.active:
            # Reactivate if previously deactivated
            existing.active = True
            for key, val in data.model_dump().items():
                if key != "label":
                    setattr(existing, key, val)
            existing.revision += 1
            db.flush()
            invalidate(db)
            return activity_json(existing)
        raise HTTPException(
            409, f"Ya existe una actividad registrada como '{existing.label}'"
        )
    activity = MaintenanceActivity(
        workshop_id=user.workshop_id,
        label=data.label.strip(),
        normalized_label=norm,
        description=data.description,
        system=data.system,
        technical_notes=data.technical_notes,
        required=data.required,
        estimated_minutes=data.estimated_minutes,
        suggested_part_ids=data.suggested_part_ids,
        active=data.active,
    )
    db.add(activity)
    db.flush()
    audit(db, user, "activity.created", "activity", activity.id)
    invalidate(db)
    return activity_json(activity)


@router.post("/seed", status_code=201)
def seed_activities(db: Database, user: User = Depends(admin)):
    seeded = 0
    for defn in DEFAULT_ACTIVITIES:
        norm = normalize_label(defn["label"])
        existing = db.scalar(
            select(MaintenanceActivity).where(
                MaintenanceActivity.workshop_id == user.workshop_id,
                MaintenanceActivity.normalized_label == norm,
            )
        )
        if not existing:
            activity = MaintenanceActivity(
                workshop_id=user.workshop_id,
                label=defn["label"],
                normalized_label=norm,
                description=defn["description"],
                system=defn["system"],
                technical_notes=defn["technical_notes"],
                required=defn["required"],
                estimated_minutes=defn["estimated_minutes"],
                suggested_part_ids=[],
                active=True,
            )
            db.add(activity)
            seeded += 1
    db.flush()
    if seeded > 0:
        audit(db, user, "activity.seeded", "workshop", user.workshop_id, {"count": seeded})
        invalidate(db)
    return {"message": f"{seeded} actividades inicializadas en el catálogo central", "seeded": seeded}


@router.put("/{activity_id}")
def update_activity(
    activity_id: int,
    data: schemas.MaintenanceActivityInput,
    db: Database,
    user: User = Depends(admin),
):
    activity = db.get(MaintenanceActivity, activity_id)
    if not activity or activity.workshop_id != user.workshop_id:
        raise HTTPException(404, "Actividad no encontrada")
    norm = normalize_label(data.label)
    duplicate = db.scalar(
        select(MaintenanceActivity).where(
            MaintenanceActivity.workshop_id == user.workshop_id,
            MaintenanceActivity.normalized_label == norm,
            MaintenanceActivity.id != activity_id,
        )
    )
    if duplicate:
        raise HTTPException(409, f"Otra actividad ya usa el nombre '{duplicate.label}'")
    for key, val in data.model_dump().items():
        setattr(activity, key, val)
    activity.normalized_label = norm
    activity.revision += 1
    db.flush()
    audit(db, user, "activity.updated", "activity", activity.id)
    invalidate(db)
    return activity_json(activity)


@router.delete("/{activity_id}")
def delete_activity(
    activity_id: int,
    db: Database,
    user: User = Depends(admin),
):
    activity = db.get(MaintenanceActivity, activity_id)
    if not activity or activity.workshop_id != user.workshop_id:
        raise HTTPException(404, "Actividad no encontrada")
    activity.active = False
    activity.revision += 1
    db.flush()
    audit(db, user, "activity.archived", "activity", activity.id)
    invalidate(db)
    return {"message": "Actividad archivada; las plantillas históricas conservan sus referencias", "id": activity.id, "active": False}
