from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from .branding import FEATURES, validate_logo

Money = Annotated[Decimal, Field(ge=0, le=99999999, max_digits=12, decimal_places=2)]
Text100 = Annotated[str, Field(min_length=1, max_length=100)]


class Input(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


class Login(Input):
    username: str = Field(min_length=1, max_length=254)
    password: str = Field(min_length=1, max_length=200)


class PasswordChange(Input):
    current_password: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=12, max_length=200)


class CustomerInput(Input):
    national_id: str = Field(min_length=3, max_length=40)
    first_name: Text100
    last_name: Text100
    address: str = Field(default="", max_length=300)
    phone: str = Field(default="", max_length=40)
    whatsapp: str = Field(default="", max_length=40)
    email: EmailStr
    telegram_chat_id: str | None = Field(default=None, pattern=r"^-?\d{1,30}$")
    notification_channel: Literal["email", "telegram", "whatsapp"] = "email"
    has_portal_access: bool = True
    email_notifications_enabled: bool = True
    telegram_notifications_enabled: bool = True
    whatsapp_notifications_enabled: bool = True

    @model_validator(mode="after")
    def channel_address(self):
        if self.notification_channel == "telegram" and not self.telegram_chat_id:
            raise ValueError("Telegram requiere chat_id; el cliente debe iniciar el bot")
        return self


class NotificationContactInput(Input):
    email: EmailStr
    notification_channel: Literal['email', 'telegram', 'whatsapp']
    telegram_chat_id: str | None = Field(None, pattern=r'^-?\d{1,30}$')
    whatsapp: str | None = Field(default=None, max_length=40)
    notifications_enabled: bool | None = None
    email_notifications_enabled: bool | None = None
    telegram_notifications_enabled: bool | None = None
    whatsapp_notifications_enabled: bool | None = None

    @model_validator(mode='after')
    def telegram_destination(self):
        if self.notifications_enabled is not False and self.notification_channel == 'telegram' and not self.telegram_chat_id:
            raise ValueError('Indica el chat_id numérico; el cliente debe iniciar el bot')
        return self


class VehicleInput(Input):
    owner_id: int = Field(gt=0)
    plate: str = Field(min_length=2, max_length=20)
    vin: str | None = Field(default=None, min_length=3, max_length=40)
    brand: str = Field(min_length=1, max_length=80)
    model: Text100
    year: int = Field(ge=1900, le=2200)
    color: str = Field(default="", max_length=40)
    fuel_type: str = Field(default="gasolina", max_length=40)
    mileage: int = Field(default=0, ge=0, le=10000000)
    # Omitidos: se conserva el enlace al editar sin cambiar la identidad.
    # Enviados como null: se elimina explícitamente la referencia.
    catalog_make_id: int | None = Field(default=None, gt=0)
    catalog_model_id: int | None = Field(default=None, gt=0)
    catalog_generation_id: int | None = Field(default=None, gt=0)
    catalog_engine_id: int | None = Field(default=None, gt=0)

    @field_validator("plate", "vin")
    @classmethod
    def uppercase(cls, value):
        return value.upper() if value else None

    @field_validator("plate")
    @classmethod
    def plausible_plate(cls, value: str) -> str:
        """Avisa en la capa de aplicación, nunca con un CHECK en la base.

        Una placa diplomática, en trámite o simplemente mal escrita no puede
        impedir anotar el vehículo que está en el taller: solo se descarta lo
        que es imposible (vacía o desmedidamente larga).
        """
        from .regional import validate_plate
        aceptada, motivo = validate_plate(value)
        if not aceptada:
            raise ValueError(motivo)
        return value


class TransferInput(Input):
    owner_id: int = Field(gt=0)


class NotesPublicationInput(Input):
    published: bool
    expected_published: bool


class CatalogTaskInput(Input):
    activity_id: int | None = Field(None, gt=0)
    label: str = Field(min_length=1, max_length=250)
    description: str = Field(default='', max_length=2000)
    required: bool = True
    estimated_minutes: int | None = Field(None, ge=1, le=10000)
    suggested_part_ids: list[Annotated[int, Field(gt=0)]] = Field(default_factory=list, max_length=20)


class ActivityInput(CatalogTaskInput):
    active: bool = True
    expected_revision: int | None = Field(None, ge=1)


class AccessGrantInput(Input):
    confirm_recovery: bool = False


class ApplicabilityInput(Input):
    make_id: int | None = Field(None, gt=0)
    model_id: int | None = Field(None, gt=0)
    generation_id: int | None = Field(None, gt=0)
    engine_id: int | None = Field(None, gt=0)
    year_from: int | None = Field(None, ge=1900, le=2200)
    year_to: int | None = Field(None, ge=1900, le=2200)

    @model_validator(mode='after')
    def valid_range(self):
        if self.year_from and self.year_to and self.year_from > self.year_to:
            raise ValueError('El año inicial supera al final')
        return self


class CatalogInput(Input):
    name: str = Field(min_length=2, max_length=150)
    description: str = Field(default="", max_length=3000)
    base_price: Money
    tasks: list[Annotated[str, Field(min_length=1, max_length=250)] | CatalogTaskInput] = Field(min_length=1, max_length=100)
    interval_km: int | None = Field(None, ge=1, le=1000000)
    schedule_source: str = Field(default='', max_length=500)
    applicability: ApplicabilityInput = Field(default_factory=ApplicabilityInput)
    active: bool = True
    price_configured: bool = True
    expected_revision: int | None = Field(None, ge=1)


class DuplicateCatalogInput(Input):
    name: str = Field(min_length=2, max_length=150)


class ExtraTaskInput(Input):
    label: str = Field(min_length=1, max_length=350)
    reason: str = Field(min_length=3, max_length=1000)
    # No se añaden cargos desde esta ruta: deben pasar por una cotización.


class OrderReviewInput(Input):
    expected_revision: int = Field(ge=1)
    note: str = Field(min_length=3, max_length=1000)


class RecordedApprovalInput(Input):
    expected_revision: int = Field(ge=1)
    approved: bool
    note: str = Field(min_length=10, max_length=1000)


class MaintenanceActivityInput(Input):
    label: str = Field(min_length=1, max_length=250)
    description: str = Field(default='', max_length=2000)
    system: str = Field(default='general', max_length=80)
    technical_notes: str = Field(default='', max_length=2000)
    required: bool = True
    estimated_minutes: int | None = Field(None, ge=1, le=10000)
    suggested_part_ids: list[Annotated[int, Field(gt=0)]] = Field(default_factory=list, max_length=20)
    active: bool = True


class ActivateCustomerInput(Input):
    token: str = Field(min_length=10, max_length=120)
    password: str = Field(min_length=12, max_length=200)


class OrderInput(Input):
    vehicle_id: int = Field(gt=0)
    catalog_id: int | None = Field(None, gt=0)
    catalog_ids: list[Annotated[int, Field(gt=0)]] = Field(default_factory=list, max_length=10)
    customer_id: int | None = Field(default=None, gt=0)
    order_code: str | None = Field(default=None, max_length=40)
    maintenance_type: Literal['preventivo', 'correctivo', 'kilometraje', 'diagnostico', 'personalizado'] = 'preventivo'
    problem_description: str = Field(default="", max_length=3000)
    technical_diagnosis: str = Field(default="", max_length=3000)
    notes: str = Field(default="", max_length=3000)
    symptoms: str = Field(default='', max_length=3000)
    delay_reason: str | None = Field(default=None, max_length=1000)
    estimated_delivery_date: datetime | None = None
    labor_cost: Money | None = None
    parts_cost: Money | None = None
    mileage: int | None = Field(None, ge=0, le=10000000)
    mechanic_id: int | None = Field(None, gt=0)
    priority: Literal['normal', 'urgent'] = 'normal'
    request_key: UUID | None = None
    included_tasks: list[str] | None = None
    extra_tasks: list[ExtraTaskInput] = Field(default_factory=list, max_length=30)

    @model_validator(mode='after')
    def services(self):
        ids = self.catalog_ids or ([self.catalog_id] if self.catalog_id else [])
        if not ids or len(set(ids)) != len(ids) or (self.catalog_ids and self.catalog_id):
            raise ValueError('Selecciona servicios distintos usando catalog_id o catalog_ids')
        return self


class ChecklistInput(Input):
    completed: bool | None = None
    status: Literal['pending', 'in_progress', 'completed', 'not_applicable', 'attention'] | None = None
    notes: str | None = Field(None, max_length=3000)
    expected_revision: int | None = Field(None, ge=1)

    @model_validator(mode='after')
    def consistent(self):
        if self.completed is None and self.status is None and self.notes is None:
            raise ValueError('Indica estado u observación')
        if self.completed is not None and self.status is not None:
            raise ValueError('Usa status o completed, no ambos')
        return self


Quantity = Annotated[Decimal, Field(gt=0, le=99999999, decimal_places=3)]


class PartRequestInput(Input):
    task_id: int = Field(gt=0)
    part_id: int | None = Field(None, gt=0)
    description: str = Field(min_length=2, max_length=250)
    quantity: Quantity
    unit: str = Field(default='unidad', min_length=1, max_length=20)
    reason: str = Field(min_length=3, max_length=1000)
    request_key: UUID


class PartResolutionInput(Input):
    expected_revision: int = Field(ge=1)
    decision: Literal['approve', 'reject']
    authorization_basis: Literal['included_base', 'approved_quote'] | None = None
    quote_id: int | None = Field(None, gt=0)
    part_id: int | None = Field(None, gt=0)
    note: str = Field(min_length=3, max_length=1000)


class StockReceiptInput(Input):
    part_id: int = Field(gt=0)
    quantity: Quantity
    unit: str = Field(default='unidad', min_length=1, max_length=20)
    reason: str = Field(min_length=3, max_length=1000)
    request_key: UUID


class QuoteOptionInput(Input):
    label: str = Field(min_length=1, max_length=150)
    price: Money


class QuoteInput(Input):
    title: str = Field(min_length=2, max_length=200)
    options: list[QuoteOptionInput] = Field(min_length=1, max_length=10)
    task_id: int | None = Field(default=None, gt=0)


class DecisionInput(Input):
    decision: Literal["approved", "rejected"]
    option_id: int | None = None

    @model_validator(mode="after")
    def valid_choice(self):
        if self.decision == "approved" and not self.option_id:
            raise ValueError("Debe seleccionar una variante")
        if self.decision == "rejected" and self.option_id is not None:
            raise ValueError("Un rechazo no puede tener variante")
        return self


class Colors(Input):
    primary: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")
    secondary: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")
    background: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")
    surface: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")


class Theme(Input):
    """Paleta de un tema del sistema visual.

    Los cuatro temas del prompt se materializan como paletas completas. Se
    guardan dentro de `branding`, no en un sistema paralelo, para que la
    publicación y las revisiones sigan siendo las mismas.
    """

    key: str = Field(pattern=r"^[a-z][a-z0-9-]{1,30}$")
    navigation: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")
    background: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")
    surface: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")
    text: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")
    secondary_text: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")
    primary: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")
    accent: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")
    complementary: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")
    diagnostic: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")


class Branding(Input):
    name: str = Field(min_length=1, max_length=80)
    tagline: str = Field(max_length=150)
    welcome: str = Field(max_length=150)
    logo: str = Field(default="", max_length=360000)
    colors: Colors
    # Tema del sistema visual. Ausente significa "usar los colores publicados".
    theme: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9-]{1,30}$")

    @field_validator("logo")
    @classmethod
    def check_logo(cls, value):
        try:
            return validate_logo(value)
        except Exception as exc:
            raise ValueError("Logo invÃƒÂ¡lido: use HTTPS o imagen Base64 de hasta 256 KB") from exc


class Flags(Input):
    features: dict[str, bool]

    @field_validator("features")
    @classmethod
    def known_flags(cls, value):
        if set(value) - set(FEATURES):
            raise ValueError("Feature flag desconocido")
        return value


class ConfigInput(Flags):
    schema_version: Literal[1] = 1
    branding: Branding
    # Sin esta clave, guardar la marca borraría la configuración regional: el
    # payload se reemplaza entero. Es opcional para no romper clientes viejos.
    regional: dict = Field(default_factory=dict)
    expected_revision: int = Field(ge=1)

    @field_validator("regional")
    @classmethod
    def valid_tax_rate(cls, value):
        if "tax_rate" in value:
            try:
                rate = Decimal(str(value["tax_rate"]))
                if not rate.is_finite() or not Decimal("0") <= rate <= Decimal("1") or rate.as_tuple().exponent < -4:
                    raise ValueError()
            except Exception:
                raise ValueError("La tasa debe estar entre 0 y 1, con hasta cuatro decimales")
            value = {**value, "tax_rate": str(rate)}
        return value

    @field_validator("features")
    @classmethod
    def complete_flags(cls, value):
        if set(value) != set(FEATURES):
            raise ValueError("La configuraciÃƒÂ³n global debe incluir todos los mÃƒÂ³dulos")
        return value


class AssignmentInput(Input):
    mechanic_id: int = Field(gt=0)
    task_ids: list[int] = Field(min_length=1, max_length=200)
    can_quote: bool = False
    expected_revision: int | None = None


class InspectionInput(Input):
    order_id: int = Field(gt=0)
    task_id: int | None = Field(default=None, gt=0)
    title: str = Field(min_length=2, max_length=150)


class RevisionInput(Input):
    expected_revision: int = Field(ge=1)


class FindingInput(RevisionInput):
    component_id: str = Field(min_length=1, max_length=80)
    view_id: str = Field(min_length=1, max_length=80)
    x: float | None = Field(None, ge=0, le=1)
    y: float | None = Field(None, ge=0, le=1)
    polygon: list[list[float]] | None = Field(default=None, max_length=100)
    category: str = Field(min_length=1, max_length=80)
    severity: Literal["not_assessed", "minor", "moderate", "major"]
    condition: Literal["no_data", "normal", "follow_up", "issue"]
    note: str = Field(min_length=1, max_length=3000)

    @model_validator(mode='after')
    def coordinate_pair(self):
        if (self.x is None) != (self.y is None) or (self.polygon and self.x is None):
            raise ValueError('Indique ambas coordenadas o registre la observación solo por componente')
        return self

    @field_validator("polygon")
    @classmethod
    def normalized_polygon(cls, value):
        if value is not None and (len(value) < 3 or any(len(point) != 2 or any(not 0 <= n <= 1 for n in point) for point in value)):
            raise ValueError("El polÃƒÂ­gono necesita al menos tres pares normalizados")
        return value


class PublishInspection(RevisionInput):
    photo_ids: list[int] = Field(default_factory=list, max_length=12)


class PublicationInput(Input):
    published: bool


class BaseApprovalInput(Input):
    approved: bool


class GeometryInput(Input):
    name: str = Field(min_length=1, max_length=100)
    kind: str = Field(min_length=1, max_length=80)
    capacity: int = Field(ge=1, le=100)
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    width: float = Field(gt=0, le=1)
    height: float = Field(gt=0, le=1)
    expected_revision: int | None = None

    @model_validator(mode="after")
    def inside_plan(self):
        if self.x + self.width > 1.00000001 or self.y + self.height > 1.00000001:
            raise ValueError("La geometrÃƒÂ­a debe estar dentro del plano normalizado")
        return self


class BayInput(GeometryInput):
    zone_id: int = Field(gt=0)
    active: bool = True


class WorkshopTemplateInput(Input):
    expected_revision: int = Field(ge=1)
    template: Literal['six-bays'] = 'six-bays'


class MoveInput(Input):
    bay_id: int | None = Field(default=None, gt=0)
    expected_occupancy_id: int | None = Field(default=None, gt=0)
    reason: str = Field(min_length=3, max_length=250)

# --- CatÃ¡logo de referencia: registro manual -------------------------------
# El prompt exige que un vehÃ­culo, marca, modelo o repuesto que no exista en
# las fuentes se pueda registrar de verdad, en la base, con autor y procedencia.


class ManualMakeInput(Input):
    name: str = Field(min_length=2, max_length=120)
    country: str | None = Field(default=None, max_length=80)
    aliases: list[str] = Field(default_factory=list, max_length=8)
    note: str = Field(default="", max_length=250)

    @field_validator("aliases")
    @classmethod
    def unique_aliases(cls, value):
        cleaned = [item.strip() for item in value if item and item.strip()]
        return list(dict.fromkeys(cleaned))[:8]


class ManualModelInput(Input):
    make_id: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=160)
    year_start: int | None = Field(default=None, ge=1900, le=2200)
    year_end: int | None = Field(default=None, ge=1900, le=2200)
    note: str = Field(default="", max_length=250)


class ManualGenerationInput(Input):
    model_id: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=200)
    year_start: int | None = Field(default=None, ge=1900, le=2200)
    year_end: int | None = Field(default=None, ge=1900, le=2200)
    body_type: str | None = Field(default=None, max_length=80)
    note: str = Field(default="", max_length=250)


class ManualEngineInput(Input):
    generation_id: int = Field(gt=0)
    label: str = Field(min_length=1, max_length=240)
    fuel_type: str | None = Field(default=None, max_length=80)
    cylinders: int | None = Field(default=None, ge=1, le=32)
    displacement_cc: float | None = Field(default=None, ge=0, le=100000)
    power_hp: float | None = Field(default=None, ge=0, le=5000)
    torque_nm: float | None = Field(default=None, ge=0, le=5000)
    transmission: str | None = Field(default=None, max_length=255)
    drivetrain: str | None = Field(default=None, max_length=80)
    note: str = Field(default="", max_length=250)

    @model_validator(mode="after")
    def sane_range(self):
        if (self.displacement_cc and self.displacement_cc < 20) or \
           (self.power_hp and self.power_hp < 5):
            raise ValueError("Revise las especificaciones: parecen estar mal escritas")
        return self


class ManualPartInput(Input):
    title: str = Field(min_length=2, max_length=200)
    name_es: str | None = Field(default=None, max_length=200)
    system: str | None = Field(default=None, max_length=40)
    sku: str | None = Field(default=None, max_length=80)
    brand: str | None = Field(default=None, max_length=120)
    synonyms: list[str] = Field(default_factory=list, max_length=12)
    keywords: list[str] = Field(default_factory=list, max_length=24)
    note: str = Field(default="", max_length=250)
# --- Vehículos: anclaje opcional al catálogo -------------------------------


class VehicleCatalogLink(Input):
    """Vincula el vehículo con una entrada real del catálogo.

    Es opcional a propósito: la lista del catálogo es global y el taller puede
    tener un vehículo que las fuentes no cubren. Vincular da contexto técnico
    (datos de catálogo, no verificación de este vehículo concreto).
    """

    model_id: int | None = Field(default=None, gt=0)
    generation_id: int | None = Field(default=None, gt=0)
    engine_id: int | None = Field(default=None, gt=0)
    source: Literal["catalog", "manual"] = "catalog"
    note: str = Field(default="", max_length=250)


class CatalogReviewInput(Input):
    expected_revision: int = Field(ge=1)
    decision: Literal["verify", "keep_pending"]
    note: str = Field(default="", max_length=1000)

    @model_validator(mode="after")
    def explain_pending(self):
        if self.decision == "keep_pending" and not self.note:
            raise ValueError("Indique qué falta comprobar antes de verificar el registro")
        return self
