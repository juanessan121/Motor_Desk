"""Configuración regional de Ecuador y validación de documentos.

Todo se valida en la capa de aplicación, nunca con `CHECK` en la base: una
restricción dura rechazaría placas y cédulas legítimas que el usuario sí debe
poder registrar, y no se puede reescribir un `CHECK` sin tocar los datos.

Ecuador tiene formatos reales y también excepciones legítimas: diplomas,
consulares, placas de servicio,=y vehículos con registro incompleto mientras se
regulariza el trámite. La validación avisa y deja decidir a la persona; no
bloquea el trabajo del taller por un dígito.
"""
from __future__ import annotations

import re
import unicodedata

# --- Configuración regional por defecto -------------------------------------

REGIONAL_DEFAULTS = {
    "country": "EC",
    "country_name": "Ecuador",
    "locale": "es-EC",
    "timezone": "America/Guayaquil",
    "currency": "USD",
    "currency_symbol": "$",
    "date_format": "dd/MM/yyyy",
    "distance_unit": "km",
    "temperature_unit": "C",
    "power_unit": "hp",
    "displacement_unit": "cc",
    # Valor inicial heredado, editable por el administrador. No certifica
    # la tasa legal aplicable a una operación concreta.
    "tax_rate": "0.15",
}

# Marcas y modelos habituales en el mercado ecuatoriano. Sirven para priorizar
# el orden de las sugerencias, NO como lista cerrada: el catálogo es global y
# estas entradas no limitan lo que se puede buscar ni registrar.
ECUADOR_COMMON_MAKES = (
    "Chevrolet", "Kia", "Hyundai", "Toyota", "Nissan", "Mazda", "Suzuki",
    "Volkswagen", "Renault", "Ford", "Chery", "JAC", "Great Wall", "Changan",
    "BYD",
)


def regional_config(payload: dict | None) -> dict:
    """Configuración efectiva: lo guardado sobre los valores por defecto."""
    saved = (payload or {}).get("regional") or {}
    return {**REGIONAL_DEFAULTS, **{key: value for key, value in saved.items()
                                    if value not in (None, "")}}


def normalize_text(value: str) -> str:
    """Sin acentos ni mayúsculas, para comparar nombres entre sí."""
    decomposed = unicodedata.normalize("NFKD", value or "")
    return re.sub(r"[^a-z0-9]+", "", decomposed.lower())


# --- Placas ----------------------------------------------------------------

# Tres o dos letras y hasta cuatro dígitos: `PBE1234`, `ABC-1234`.
PLATE_NORMAL = re.compile(r"^[A-Z]{2,3}[0-9]{3,4}$")
# Placas de motos con menos letras, y diplomáticas o de servicio: se aceptan
# con aviso, no se rechazan.
PLATE_SPECIAL = re.compile(r"^[A-Z]{1,4}[0-9]{1,5}$")


def normalize_plate(raw: str) -> str:
    """`pbe-1234` -> `PBE1234`. Solo para comparar y mostrar, no para inventar."""
    text = unicodedata.normalize("NFKD", raw or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Z0-9]", "", text.upper())


def validate_plate(raw: str) -> tuple[bool, str]:
    """Comprueba una placa ecuatoriana.

    Devuelve `(aceptada, motivo)`. Un formato inusual no se rechaza: se admite
    con el aviso correspondiente, porque el registro del vehículo es más
    urgente que la forma exacta de su placa.
    """
    plate = normalize_plate(raw)
    if not plate:
        return False, "La placa no puede estar vacía"
    if len(plate) > 10:
        return False, "La placa no puede superar 10 caracteres"
    if PLATE_NORMAL.match(plate):
        return True, ""
    if PLATE_SPECIAL.match(plate):
        return True, ("Formato inusual: se admite por tratarse de una placa "
                      "especial o de un registro provisional")
    return True, ("Formato fuera del patrón ecuatoriano (AAA-1234). Se admite y "
                  "queda marcado para revisión del administrador")


# --- Cédula y RUC ----------------------------------------------------------

def _check_digit(digits: str) -> int:
    """Dígito verificador módulo 10: pesos 2,1,2,1... sobre los dígitos dados."""
    total = sum(int(digit) * (2 - index % 2) for index, digit in enumerate(digits))
    resto = total % 10
    return 0 if resto == 0 else 10 - resto


def validate_national_id(raw: str) -> tuple[bool, str]:
    """Cédula de 10 dígitos o RUC de 13, con su dígito verificador módulo 10.

    Ambos usan el mismo algoritmo con pesos alternos 2,1,2,1... El RUC añade
    dos dígitos de tipo al principio: 00 (sociedades públicas), 15 (privadas) o
    17 (sin ánimo de lucro). El verificador es el último dígito en ambos casos.
    """
    value = re.sub(r"\D", "", raw or "")
    if not value:
        return True, ""
    if len(value) == 13:
        if not value.startswith(("00", "15", "17")):
            return False, "Un RUC ecuatoriano empieza por 00, 15 o 17"
        cuerpo, verificador = value[:12], value[12]
    elif len(value) == 10:
        cuerpo, verificador = value[:9], value[9]
    else:
        return False, "La cédula tiene 10 dígitos y el RUC 13"
    if len(set(value)) == 1:
        return False, "El número no puede tener todos sus dígitos iguales"
    if _check_digit(cuerpo) != int(verificador):
        return False, "El dígito verificador no coincide"
    return True, ""


def format_plate(raw: str) -> str:
    """`PBE1234` -> `PBE-1234` para mostrar. No altera lo almacenado."""
    plate = normalize_plate(raw)
    if len(plate) > 4 and plate[:-4].isalpha() and plate[-4:].isdigit():
        return f"{plate[:-4]}-{plate[-4:]}"
    return plate
