from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .database import SessionLocal
from .events import hub
from .models import Device, User
from .security import decode_token

bearer = HTTPBearer(auto_error=False)


async def get_db():
    db = SessionLocal()
    try:
        yield db
        db.commit()
        for kind, audience in db.info.get("events", []):
            hub.publish(kind, audience)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Registro duplicado o relación inválida; revise cédula, correo, placa y VIN") from exc
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def invalidate(db: Session, kind: str = "data", audience: set[int] | None = None, *, order_id=None):
    if kind in {"data", "notifications"}:
        from .access_policy import admins
        from .models import WorkAssignment
        team = admins(db, db.info.get("workshop_id", 1))
        if order_id is not None:
            team |= set(db.scalars(select(WorkAssignment.mechanic_id).where(
                WorkAssignment.order_id == order_id, WorkAssignment.revoked_at.is_(None))))
        audience = team | (audience or set())
    elif kind == "config" and audience is None:
        audience = set(db.scalars(select(User.id).where(User.workshop_id == db.info.get("workshop_id", 1))))
    db.info.setdefault("events", []).append((kind, audience))


Database = Annotated[Session, Depends(get_db, scope="function")]


def current_user(db: Database, credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
    if credentials is None:
        raise HTTPException(401, "Autenticación requerida")
    payload = decode_token(credentials.credentials)
    user = db.get(User, int(payload["sub"]))
    if not user or not user.active or user.token_version != payload.get("ver"):
        raise HTTPException(401, "Sesión revocada")
    db.info["workshop_id"] = user.workshop_id
    db.info["actor_id"] = user.id
    return user


def authenticated(user: User = Depends(current_user)):
    if user.must_change_password:
        raise HTTPException(403, "Debe cambiar su contraseña temporal")
    return user


def staff(user: User = Depends(authenticated)):
    if user.role not in {"admin", "mechanic"}:
        raise HTTPException(403, "Se requiere rol de taller")
    return user


def admin(user: User = Depends(authenticated)):
    if user.role != "admin":
        raise HTTPException(403, "Se requiere rol administrador")
    return user


def device_id(
    db: Database,
    x_device_id: str | None = Header(default=None),
    user: User = Depends(authenticated),
    credentials=Depends(bearer),
):
    if user.role != "customer":
        return None
    bound_id = decode_token(credentials.credentials).get("did")
    try:
        key = str(UUID(x_device_id or ""))
    except ValueError as exc:
        raise HTTPException(403, "Falta el identificador de instalación autenticado") from exc
    device = db.get(Device, bound_id) if bound_id else None
    if device is None or device.user_id != user.id or device.device_key != key:
        raise HTTPException(403, "Dispositivo no registrado; vuelva a iniciar sesión")
    return device.id
