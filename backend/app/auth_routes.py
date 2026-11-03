from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import or_, select

from . import schemas
from .dependencies import Database, authenticated, bearer, current_user, invalidate
from .models import Device, User, utcnow
from .security import decode_token, issue_token, password_hasher, throttle_login, verify_password
from .serializers import user_json

router = APIRouter(prefix="/auth", tags=["Autenticación"])


@router.post("/login")
def login(data: schemas.Login, request: Request, db: Database, x_device_id: str | None = Header(default=None)):
    host = request.client.host if request.client else "unknown"
    throttle_login(f"{host}:{data.username.lower()}")
    user = db.scalar(select(User).where(or_(User.username == data.username.lower(), User.email == data.username.lower())))
    if not verify_password(data.password, user.password_hash if user else None) or not user.active:
        raise HTTPException(401, "Usuario o contraseña incorrectos")
    if user.role == "customer" and not x_device_id:
        raise HTTPException(422, "La cuenta de cliente requiere un identificador de instalación")
    device = None
    if x_device_id:
        try:
            x_device_id = str(UUID(x_device_id))
        except ValueError as exc:
            raise HTTPException(422, "Identificador de dispositivo inválido") from exc
        device = db.scalar(select(Device).where(Device.user_id == user.id, Device.device_key == x_device_id))
        if device:
            device.last_seen_at = utcnow()
        else:
            device = Device(user_id=user.id, device_key=x_device_id)
            db.add(device)
        db.flush()
    return {"access_token": issue_token(user, device.id if device else None), "token_type": "bearer", "user": user_json(user)}


@router.get("/me")
def me(user: User = Depends(current_user)):
    return user_json(user)


@router.post("/password")
def change_password(data: schemas.PasswordChange, db: Database, user: User = Depends(current_user), credentials=Depends(bearer)):
    db.refresh(user, with_for_update=True)
    if not verify_password(data.current_password, user.password_hash):
        raise HTTPException(400, "Contraseña actual incorrecta")
    if data.current_password == data.new_password:
        raise HTTPException(422, "La nueva contraseña debe ser diferente")
    user.password_hash = password_hasher.hash(data.new_password)
    user.must_change_password = False
    user.token_version += 1
    db.flush()
    invalidate(db, "session", {user.id})
    device = decode_token(credentials.credentials).get("did")
    return {"access_token": issue_token(user, device), "token_type": "bearer", "user": user_json(user)}


@router.post("/logout")
def logout(db: Database, user: User = Depends(authenticated)):
    db.refresh(user, with_for_update=True)
    user.token_version += 1
    invalidate(db, "session", {user.id})
    return {"message": "Sesiones cerradas"}


@router.post("/activate")
def activate_account(data: schemas.ActivateCustomerInput, db: Database):
    import hashlib
    token_hash = hashlib.sha256(data.token.strip().encode()).hexdigest()
    from .models import CustomerAccessGrant
    grant = db.scalar(select(CustomerAccessGrant).where(CustomerAccessGrant.token_hash == token_hash).with_for_update())
    if not grant or grant.consumed_at is not None:
        raise HTTPException(400, "El enlace de activación no es válido o ya fue utilizado")
    now = utcnow()
    exp = grant.expires_at
    if exp.tzinfo is None:
        now = now.replace(tzinfo=None)
    if exp < now:
        raise HTTPException(400, "El enlace de activación ha expirado; solicite uno nuevo a la administración")
    user = db.get(User, grant.user_id)
    if not user or not user.active:
        raise HTTPException(400, "Cuenta no válida o desactivada")
    if grant.token_version != user.token_version:
        raise HTTPException(400, "El enlace corresponde a una versión anterior de credenciales")
    user.password_hash = password_hasher.hash(data.password)
    user.must_change_password = False
    user.token_version += 1
    grant.consumed_at = utcnow()
    db.flush()
    invalidate(db, "session", {user.id})
    return {"message": "Cuenta activada con éxito. Ya puede iniciar sesión con sus credenciales.", "username": user.username, "email": user.email}
