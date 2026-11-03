from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from . import schemas
from .branding import (
    DEFAULT_CONFIG, DEFAULT_THEME, REGIONAL_DEFAULTS, THEMES, config_scope,
    effective_config, themes,
)
from .dependencies import Database, admin, authenticated, device_id, invalidate, staff
from .models import AppConfiguration, Device, User, utcnow
from .registry_routes import get_record

router = APIRouter(tags=["Server-driven UI"])


@router.get("/public/config")
def public_config(db: Database):
    return effective_config(db)


@router.get("/config")
def config(db: Database, user: User = Depends(authenticated), device: int | None = Depends(device_id)):
    return effective_config(db, user.id if user.role == "customer" else None, device if user.role == "customer" else None, workshop_id=user.workshop_id)


@router.get("/config/themes")
def config_themes(_: User = Depends(authenticated)):
    """Catálogo de temas del sistema visual, para la pantalla de Personalización.

    Es solo lectura: elegir un tema es guardarlo en `branding`, y eso exige la
    publicación explícita que ya exige cualquier otro cambio de diseño.
    """
    return {"themes": themes(), "default": DEFAULT_THEME}


@router.put("/config/global")
def save_config(data: schemas.ConfigInput, db: Database, user: User = Depends(admin)):
    scope = config_scope("global", user.workshop_id)
    row = db.scalar(select(AppConfiguration).where(AppConfiguration.scope == scope).with_for_update())
    if row is None:
        row = AppConfiguration(scope=scope, payload=DEFAULT_CONFIG.copy(), revision=1)
        db.add(row)
    if row.revision != data.expected_revision:
        raise HTTPException(409, "Otro administrador modificó el diseño. Recargue antes de guardar")
    payload = data.model_dump(exclude={"expected_revision"})
    if not payload.get("regional"):
        # Un cliente antiguo que no conoce la clave no debe borrarla al guardar
        # la marca: el payload se reemplaza entero.
        payload["regional"] = dict(row.payload.get("regional") or REGIONAL_DEFAULTS)
    theme = payload.get("branding", {}).get("theme")
    if theme and theme not in THEMES:
        raise HTTPException(422, f"Tema desconocido: {theme}")
    row.payload = payload
    row.revision += 1
    row.updated_at, row.updated_by = utcnow(), user.id
    invalidate(db, "config")
    return effective_config(db)


@router.get("/config/users/{user_id}")
def user_flags(user_id: int, db: Database, _: User = Depends(admin)):
    get_record(db, User, user_id)
    row = db.get(AppConfiguration, config_scope(f"user:{user_id}", db.info.get("workshop_id", 1)))
    return {"features": row.payload.get("features", {}) if row else {}}


@router.put("/config/users/{user_id}")
def save_user_flags(user_id: int, data: schemas.Flags, db: Database, user: User = Depends(admin)):
    get_record(db, User, user_id)
    save_flags(db, f"user:{user_id}", data.features, user.id)
    invalidate(db, "config", {user_id, user.id})
    return {"features": data.features}


def save_flags(db, scope, flags, actor):
    scope = config_scope(scope, db.info.get("workshop_id", 1))
    row = db.get(AppConfiguration, scope)
    if row:
        row.payload = {"features": flags}
        row.revision += 1
        row.updated_by, row.updated_at = actor, utcnow()
    else:
        db.add(AppConfiguration(scope=scope, payload={"features": flags}, updated_by=actor))


@router.get("/devices")
def devices(db: Database, user: User = Depends(admin)):
    return [{
        "id": row.id, "user_id": row.user_id, "device_key": row.device_key,
        "last_seen_at": row.last_seen_at.isoformat(),
        "features": (db.get(AppConfiguration, config_scope(f"device:{row.id}", user.workshop_id)).payload["features"] if db.get(AppConfiguration, config_scope(f"device:{row.id}", user.workshop_id)) else {}),
    } for row in db.scalars(select(Device).join(User).where(User.role == "customer", User.workshop_id == user.workshop_id).order_by(Device.last_seen_at.desc()))]


@router.put("/config/devices/{registered_device_id}")
def save_device_flags(registered_device_id: int, data: schemas.Flags, db: Database, user: User = Depends(admin)):
    device = get_record(db, Device, registered_device_id)
    get_record(db, User, device.user_id)
    save_flags(db, f"device:{device.id}", data.features, user.id)
    invalidate(db, "config", {device.user_id, user.id})
    return {"features": data.features}
