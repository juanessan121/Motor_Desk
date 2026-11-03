import base64
import re

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .models import AppConfiguration, User
from .regional import REGIONAL_DEFAULTS, regional_config

FEATURES = {
    "vehicles": "Mis vehículos", "maintenance": "Seguimiento del mantenimiento",
    "quotes": "Aprobación de repuestos", "photos": "Fotografías de recepción",
    "history": "Historial técnico",
}

# Los cuatro temas del sistema visual Automotive Atelier. Paletas completas,
# con sus colores semánticos de estado, para que el taller pueda publicar el
# que corresponda sin que el código tenga que inventar tonos intermedios.
#
# El taller sigue publicando sus cuatro colores de marca: un tema sin
# `colors` guardados usa la paleta; con `colors` guardados manda lo publicado.
THEMES = {
    "pitlane": {
        "label": "Pitlane",
        "description": "Administración. Claro, sobrio, máxima legibilidad.",
        "navigation": "#101B2E", "background": "#F4F2EE", "surface": "#FFFFFF",
        "text": "#202B36", "secondary_text": "#6F7C89", "primary": "#2563EB",
        "accent": "#D56845", "complementary": "#168B78", "diagnostic": "#101B28",
        "success": "#168B78", "warning": "#D99B32", "danger": "#C54747",
        "unknown": "#6F7C89",
    },
    "carbon-racing": {
        "label": "Carbon Racing",
        "description": "Operación en taller. Oscuro, con acento cálido.",
        "navigation": "#0D151C", "background": "#0D151C", "surface": "#202B34",
        "text": "#F5F8F9", "secondary_text": "#A7B3BC", "primary": "#FF774D",
        "accent": "#FF774D", "complementary": "#57CBB4", "diagnostic": "#0B1116",
        "success": "#57CBB4", "warning": "#E0A458", "danger": "#FF6B6B",
        "unknown": "#A7B3BC",
    },
    "electric-blue": {
        "label": "Electric Blue",
        "description": "Tecnología y diagnóstico. Oscuro, alto contraste.",
        "navigation": "#081D2C", "background": "#081D2C", "surface": "#123547",
        "text": "#F4FAFC", "secondary_text": "#A8C4D4", "primary": "#34D9DA",
        "accent": "#34D9DA", "complementary": "#B7E860", "diagnostic": "#061520",
        "success": "#B7E860", "warning": "#F2C14E", "danger": "#FF6B81",
        "unknown": "#A8C4D4",
    },
    "heritage-garage": {
        "label": "Heritage Garage",
        "description": "Taller clásico. Cálido, con acento dorado.",
        "navigation": "#183A34", "background": "#183A34", "surface": "#275047",
        "text": "#FAF5E9", "secondary_text": "#C3CFC6", "primary": "#E4B86A",
        "accent": "#E4B86A", "complementary": "#D9C7A3", "diagnostic": "#122B26",
        "success": "#9CC08A", "warning": "#E4B86A", "danger": "#D98A7A",
        "unknown": "#C3CFC6",
    },
}

DEFAULT_THEME = "pitlane"

DEFAULT_CONFIG = {
    "schema_version": 1,
    "branding": {
        "name": "MotorDesk", "tagline": "Tu taller, conectado.",
        "welcome": "Cuidamos lo que te mueve", "logo": "",
        "colors": {"primary": "#2563EB", "secondary": "#0D9488", "background": "#F4F6FA", "surface": "#FFFFFF"},
    },
    "features": {key: True for key in FEATURES},
    # Sección aditiva. Las configuraciones ya publicadas no la tienen, así que
    # se rellena al leer (ver `effective_config`); el contrato v1 no se rompe.
    "regional": dict(REGIONAL_DEFAULTS),
}


def themes():
    """Catálogo de temas para la pantalla de Personalización."""
    return [{"key": key, **value} for key, value in THEMES.items()]


def theme_palette(key: str | None) -> dict:
    """Paleta efectiva de un tema, o la de por defecto si no existe."""
    return dict(THEMES.get(key or DEFAULT_THEME, THEMES[DEFAULT_THEME]))


def validate_logo(logo: str):
    if not logo:
        return logo
    if logo.startswith("data:image/"):
        match = re.fullmatch(r"data:image/(png|jpeg|webp);base64,([A-Za-z0-9+/=]+)", logo)
        if not match:
            raise ValueError("Logo: solo PNG, JPEG o WebP en Base64")
        raw = base64.b64decode(match[2], validate=True)
        if len(raw) > 256 * 1024:
            raise ValueError("El logo no puede superar 256 KB")
        from io import BytesIO
        from PIL import Image
        with Image.open(BytesIO(raw)) as image:
            if image.format not in {"PNG", "JPEG", "WEBP"}:
                raise ValueError("Formato de logo inválido")
            if image.width > 2048 or image.height > 2048:
                raise ValueError("El logo no debe superar 2048 píxeles por lado")
            image.verify()
        return logo
    if not re.fullmatch(r"https://[^\s]{1,2040}", logo):
        raise ValueError("El logo remoto requiere una URL HTTPS")
    return logo


def config_scope(scope, workshop_id):
    return scope if workshop_id == 1 else f"workshop:{workshop_id}:{scope}"


def effective_config(db: Session, user_id: int | None = None, device_id: int | None = None, *, workshop_id=None):
    owner = db.get(User, user_id) if user_id else None
    workshop_id = workshop_id or (owner.workshop_id if owner else db.info.get("workshop_id", 1))
    row = db.get(AppConfiguration, config_scope("global", workshop_id))
    config = dict(row.payload if row else DEFAULT_CONFIG)
    # Las configuraciones publicadas antes de que existiera la sección
    # regional no la traen: se completa con los valores por defecto en lugar de
    # propagar un KeyError a la interfaz.
    config["regional"] = regional_config(config)
    flags = dict(config["features"])
    revisions = {"global": row.revision if row else 1}
    for scope in ([f"user:{user_id}"] if user_id else []) + ([f"device:{device_id}"] if device_id else []):
        override = db.get(AppConfiguration, config_scope(scope, workshop_id))
        if override:
            revisions[scope] = override.revision
            flags = {key: enabled and override.payload.get("features", {}).get(key, True) for key, enabled in flags.items()}
    # El tema viaja con la configuración efectiva para que la interfaz no tenga
    # que conocer la paleta: recibe el tema elegido y sus colores ya resueltos.
    theme_key = config["branding"].get("theme") or DEFAULT_THEME
    return {**config, "features": flags, "theme_key": theme_key,
            "theme": theme_palette(theme_key), "revision": revisions["global"],
            "revisions": revisions}


def require_feature(db: Session, user, feature: str, device_id: int | None = None):
    if user.role == "customer" and not effective_config(db, user.id, device_id)["features"].get(feature, False):
        raise HTTPException(403, "Este módulo está deshabilitado para su cuenta o dispositivo")
