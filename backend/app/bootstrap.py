import copy

from sqlalchemy import select

from .branding import DEFAULT_CONFIG
from .database import SessionLocal
from .models import AppConfiguration, User, Workshop
from .security import password_hasher
from .settings import settings


def bootstrap():
    config = settings()
    with SessionLocal.begin() as db:
        if not db.get(Workshop, 1):
            db.add(Workshop(id=1, name=DEFAULT_CONFIG["branding"]["name"]))
            db.flush()
        if not db.scalar(select(User).where(User.role == "admin")):
            db.add(User(
                username="admin", email=config.admin_email.lower(),
                password_hash=password_hasher.hash(config.admin_password),
                role="admin", active=True, must_change_password=True,
            ))
        if not db.get(AppConfiguration, "global"):
            db.add(AppConfiguration(scope="global", payload=copy.deepcopy(DEFAULT_CONFIG)))


if __name__ == "__main__":
    bootstrap()
    from .bundled_catalog import seed_bundled_catalog
    seed_bundled_catalog(SessionLocal)
    print("Administrador y configuración inicial disponibles. Las ejecuciones posteriores no reemplazan datos.")
