from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    JSON, Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer,
    LargeBinary, Numeric, String, Text, UniqueConstraint, text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .catalog_models import VehicleEngine, VehicleGeneration, VehicleMake, VehicleModel
from .database import Base


def utcnow():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("role IN ('admin','mechanic','customer')", name="user_role"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    workshop_id: Mapped[int] = mapped_column(ForeignKey("workshops.id"), default=1, server_default="1", index=True)
    username: Mapped[str] = mapped_column(String(100), unique=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(20))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=True)
    token_version: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Customer(Base):
    __tablename__ = "customers"
    __table_args__ = (CheckConstraint("notification_channel IN ('email','telegram','whatsapp')", name="customer_channel"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    workshop_id: Mapped[int] = mapped_column(ForeignKey("workshops.id"), default=1, server_default="1", index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), unique=True, nullable=True)
    national_id: Mapped[str] = mapped_column(String(40), unique=True)
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    address: Mapped[str] = mapped_column(String(300), default="")
    phone: Mapped[str] = mapped_column(String(40), default="")
    whatsapp: Mapped[str] = mapped_column(String(40), default="", server_default="")
    email: Mapped[str] = mapped_column(String(254), unique=True)
    telegram_chat_id: Mapped[str | None] = mapped_column(String(40))
    notification_channel: Mapped[str] = mapped_column(String(20), default="email")
    notifications_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text('true'))
    email_notifications_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text('true'))
    telegram_notifications_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text('true'))
    whatsapp_notifications_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text('true'))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    user: Mapped[User | None] = relationship()

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def preferred_channel(self) -> str:
        return self.notification_channel


class Vehicle(Base):
    __tablename__ = "vehicles"
    id: Mapped[int] = mapped_column(primary_key=True)
    workshop_id: Mapped[int] = mapped_column(ForeignKey("workshops.id"), default=1, server_default="1", index=True)
    template_id: Mapped[str] = mapped_column(String(80), default="sedan-neutral-v1", server_default="sedan-neutral-v1")
    owner_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    plate: Mapped[str] = mapped_column(String(20), unique=True)
    vin: Mapped[str | None] = mapped_column(String(40), unique=True)
    brand: Mapped[str] = mapped_column(String(80))
    model: Mapped[str] = mapped_column(String(100))
    year: Mapped[int] = mapped_column(Integer)
    color: Mapped[str] = mapped_column(String(40), default="", server_default="")
    fuel_type: Mapped[str] = mapped_column(String(40), default="gasolina", server_default="gasolina")
    mileage: Mapped[int] = mapped_column(default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Referencia opcional al catálogo. El texto de arriba sigue siendo la
    # fuente de verdad: dice qué escribió el taller sobre este coche. Estas
    # columnas solo enlazan con la ficha de referencia cuando se resolvió con
    # certeza. Ver migración 0008.
    catalog_make_id: Mapped[int | None] = mapped_column(
        ForeignKey("catalog_makes.id", ondelete="SET NULL"), index=True)
    catalog_model_id: Mapped[int | None] = mapped_column(
        ForeignKey("catalog_models.id", ondelete="SET NULL"), index=True)
    catalog_generation_id: Mapped[int | None] = mapped_column(
        ForeignKey("catalog_generations.id", ondelete="SET NULL"))
    catalog_engine_id: Mapped[int | None] = mapped_column(
        ForeignKey("catalog_engines.id", ondelete="SET NULL"))
    catalog_make: Mapped[VehicleMake | None] = relationship(
        foreign_keys=[catalog_make_id], lazy="joined")
    catalog_model: Mapped[VehicleModel | None] = relationship(
        foreign_keys=[catalog_model_id], lazy="joined")
    catalog_generation: Mapped[VehicleGeneration | None] = relationship(
        foreign_keys=[catalog_generation_id], lazy="joined")
    catalog_engine: Mapped[VehicleEngine | None] = relationship(
        foreign_keys=[catalog_engine_id], lazy="joined")
    owner: Mapped[Customer] = relationship()
    __table_args__ = (
        CheckConstraint("mileage >= 0", name="vehicle_mileage"),
        CheckConstraint("year >= 1900 AND year <= 2200", name="vehicle_year"),
    )

    def catalog_ref(self) -> dict | None:
        """Ficha del catálogo enlazada, o `None` si no se resolvió.

        Devuelve `None` y no un objeto vacío porque hay una diferencia real
        entre «no está enlazado» y «enlazado y sin detalles»: son dos
        afirmaciones distintas sobre lo que sabe el sistema de ese coche.
        """
        if self.catalog_make is None:
            return None
        # Si una ficha desapareció (SET NULL), no se muestran descendientes
        # que ya no pueden comprobarse dentro de la cadena conservada.
        model = self.catalog_model
        if model is not None and model.make_id != self.catalog_make.id:
            model = None
        generation = self.catalog_generation if model is not None else None
        if generation is not None and generation.model_id != model.id:
            generation = None
        engine = self.catalog_engine if generation is not None else None
        if engine is not None and engine.generation_id != generation.id:
            engine = None
        return {
            "make_id": self.catalog_make.id,
            "make_name": self.catalog_make.name,
            "make_slug": self.catalog_make.slug,
            "logo_url": self.catalog_make.logo_url,
            "model_id": model.id if model else None,
            "model_name": model.name if model else None,
            "generation_id": generation.id if generation else None,
            "generation_name": generation.name if generation else None,
            "engine_id": engine.id if engine else None,
            "engine": ({key: getattr(engine, key) for key in (
                "id", "label", "fuel_type", "cylinders", "displacement_cc", "power_hp",
                "torque_nm", "transmission", "drivetrain")} if engine else None),
            "year_start": model.year_start if model else None,
            "year_end": model.year_end if model else None,
        }


class OwnershipHistory(Base):
    __tablename__ = "ownership_history"
    id: Mapped[int] = mapped_column(primary_key=True)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id"), index=True)
    previous_owner_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id"))
    new_owner_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    changed_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class MaintenanceCatalog(Base):
    __tablename__ = "maintenance_catalogs"
    __table_args__ = (CheckConstraint("base_price >= 0", name="catalog_price"),
                     UniqueConstraint('workshop_id', 'system_key', name='uq_catalog_system_key'))
    id: Mapped[int] = mapped_column(primary_key=True)
    workshop_id: Mapped[int] = mapped_column(ForeignKey("workshops.id"), default=1, server_default="1", index=True)
    name: Mapped[str] = mapped_column(String(150))
    description: Mapped[str] = mapped_column(Text, default="")
    base_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    revision: Mapped[int] = mapped_column(default=1, server_default='1')
    system_key: Mapped[str | None] = mapped_column(String(60))
    price_configured: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text('true'))
    interval_km: Mapped[int | None] = mapped_column(Integer)
    schedule_source: Mapped[str] = mapped_column(String(500), default='', server_default='')
    applicability: Mapped[dict] = mapped_column(JSON, default=dict, server_default='{}')
    tasks: Mapped[list["CatalogTask"]] = relationship(cascade="all, delete-orphan", order_by="CatalogTask.position")


class CatalogTask(Base):
    __tablename__ = "catalog_tasks"
    id: Mapped[int] = mapped_column(primary_key=True)
    catalog_id: Mapped[int] = mapped_column(ForeignKey("maintenance_catalogs.id", ondelete="CASCADE"), index=True)
    label: Mapped[str] = mapped_column(String(250))
    position: Mapped[int] = mapped_column(Integer)
    description: Mapped[str] = mapped_column(Text, default='', server_default='')
    system: Mapped[str] = mapped_column(String(80), default='general', server_default='general')
    technical_notes: Mapped[str] = mapped_column(Text, default='', server_default='')
    required: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text('true'))
    estimated_minutes: Mapped[int | None] = mapped_column(Integer)
    suggested_part_ids: Mapped[list] = mapped_column(JSON, default=list, server_default='[]')
    activity_id: Mapped[int | None] = mapped_column(ForeignKey('maintenance_activities.id'))


class MaintenanceActivity(Base):
    __tablename__ = 'maintenance_activities'
    __table_args__ = (UniqueConstraint('workshop_id', 'normalized_label', name='uq_maintenance_activity'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    workshop_id: Mapped[int] = mapped_column(ForeignKey('workshops.id'), index=True)
    label: Mapped[str] = mapped_column(String(250))
    normalized_label: Mapped[str] = mapped_column(String(250))
    description: Mapped[str] = mapped_column(Text, default='', server_default='')
    system: Mapped[str] = mapped_column(String(80), default='general', server_default='general')
    technical_notes: Mapped[str] = mapped_column(Text, default='', server_default='')
    required: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text('true'))
    estimated_minutes: Mapped[int | None] = mapped_column(Integer)
    suggested_part_ids: Mapped[list] = mapped_column(JSON, default=list, server_default='[]')
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text('true'))
    revision: Mapped[int] = mapped_column(default=1, server_default='1')


class CustomerAccessGrant(Base):
    __tablename__ = 'customer_access_grants'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    token_version: Mapped[int] = mapped_column(Integer)
    created_by: Mapped[int] = mapped_column(ForeignKey('users.id'))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MaintenanceVersion(Base):
    __tablename__ = 'maintenance_versions'
    __table_args__ = (UniqueConstraint('catalog_id', 'revision', name='uq_maintenance_version'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    catalog_id: Mapped[int] = mapped_column(ForeignKey('maintenance_catalogs.id'), index=True)
    revision: Mapped[int] = mapped_column(Integer)
    snapshot: Mapped[dict] = mapped_column(JSON)
    created_by: Mapped[int | None] = mapped_column(ForeignKey('users.id'))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class WorkOrder(Base):
    __tablename__ = "work_orders"
    __table_args__ = (
        CheckConstraint("base_total >= 0", name="order_total"),
        CheckConstraint("status IN ('in_progress','ready','delivered','cancelled')", name="order_status"),
        UniqueConstraint('workshop_id', 'request_key', name='uq_order_request'),
        Index("one_open_order_per_vehicle", "vehicle_id", unique=True,
              postgresql_where=text("status IN ('in_progress','ready')"),
              sqlite_where=text("status IN ('in_progress','ready')")),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    workshop_id: Mapped[int] = mapped_column(ForeignKey("workshops.id"), default=1, server_default="1", index=True)
    order_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    maintenance_type: Mapped[str] = mapped_column(String(40), default="preventivo", server_default="preventivo")
    base_approval: Mapped[str] = mapped_column(String(20), default="pending", server_default="pending")
    base_approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    base_approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id"), index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    catalog_id: Mapped[int] = mapped_column(ForeignKey("maintenance_catalogs.id"))
    title: Mapped[str] = mapped_column(String(150))
    payer_snapshot: Mapped[dict] = mapped_column(JSON)
    problem_description: Mapped[str] = mapped_column(Text, default="", server_default="")
    technical_diagnosis: Mapped[str] = mapped_column(Text, default="", server_default="")
    base_total: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    labor_cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    parts_cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=Decimal("0.15"), server_default="0.15")
    tax_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    total_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="in_progress")
    notes: Mapped[str] = mapped_column(Text, default="")
    symptoms: Mapped[str] = mapped_column(Text, default='', server_default='')
    delay_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes_published: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text('false'))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    ready_notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    estimated_delivery_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    intake_mileage: Mapped[int | None] = mapped_column(Integer)
    template_snapshot: Mapped[list | None] = mapped_column(JSON, nullable=True)
    request_key: Mapped[str | None] = mapped_column(String(36))
    request_hash: Mapped[str | None] = mapped_column(String(64))
    priority: Mapped[str] = mapped_column(String(20), default='normal', server_default='normal')
    revision: Mapped[int] = mapped_column(default=1, server_default='1')
    # Las órdenes previas conservan su política; las nuevas se revisan antes de entregar.
    review_required: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text('false'))
    execution_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    execution_reviewed_by: Mapped[int | None] = mapped_column(ForeignKey('users.id'))
    vehicle: Mapped[Vehicle] = relationship()
    customer: Mapped[Customer] = relationship()
    items: Mapped[list["ChecklistItem"]] = relationship(cascade="all, delete-orphan", order_by="ChecklistItem.id")
    quotes: Mapped[list["ExtraQuote"]] = relationship(cascade="all, delete-orphan", order_by="ExtraQuote.id")
    photos: Mapped[list["IntakePhoto"]] = relationship(cascade="all, delete-orphan", order_by="IntakePhoto.id")
    assignments: Mapped[list['WorkAssignment']] = relationship()
    part_requests: Mapped[list['PartRequest']] = relationship(order_by='PartRequest.id')


class ExtraQuote(Base):
    __tablename__ = "extra_quotes"
    __table_args__ = (CheckConstraint("decision IN ('pending','approved','rejected')", name="quote_decision"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("work_orders.id"), index=True)
    task_id: Mapped[int | None] = mapped_column(ForeignKey("checklist_items.id", use_alter=True, name="fk_quote_task"))
    title: Mapped[str] = mapped_column(String(200))
    decision: Mapped[str] = mapped_column(String(20), default="pending")
    selected_option_id: Mapped[int | None] = mapped_column(ForeignKey("quote_options.id", use_alter=True, name="fk_selected_option"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    options: Mapped[list["QuoteOption"]] = relationship(
        foreign_keys="QuoteOption.quote_id", cascade="all, delete-orphan", order_by="QuoteOption.id",
    )


class QuoteOption(Base):
    __tablename__ = "quote_options"
    __table_args__ = (CheckConstraint("price >= 0", name="option_price"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    quote_id: Mapped[int] = mapped_column(ForeignKey("extra_quotes.id"), index=True)
    label: Mapped[str] = mapped_column(String(150))
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2))


class ChecklistItem(Base):
    __tablename__ = "checklist_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("work_orders.id"), index=True)
    quote_id: Mapped[int | None] = mapped_column(ForeignKey("extra_quotes.id"), unique=True)
    label: Mapped[str] = mapped_column(String(350))
    description: Mapped[str] = mapped_column(Text, default='', server_default='')
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(24), default='pending', server_default='pending')
    notes: Mapped[str] = mapped_column(Text, default='', server_default='')
    required: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text('true'))
    estimated_minutes: Mapped[int | None] = mapped_column(Integer)
    suggested_part_ids: Mapped[list] = mapped_column(JSON, default=list, server_default='[]')
    template_catalog_id: Mapped[int | None] = mapped_column(ForeignKey('maintenance_catalogs.id'))
    revision: Mapped[int] = mapped_column(default=1, server_default='1')
    updated_by: Mapped[int | None] = mapped_column(ForeignKey('users.id'))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (CheckConstraint("status IN ('pending','in_progress','completed','not_applicable','attention')", name='checklist_status'),)


class StockItem(Base):
    """Existencia física declarada por el taller; no la cantidad del catálogo."""
    __tablename__ = 'stock_items'
    __table_args__ = (UniqueConstraint('workshop_id', 'part_id', name='uq_stock_part'),
                     CheckConstraint('quantity >= 0', name='stock_nonnegative'))
    id: Mapped[int] = mapped_column(primary_key=True)
    workshop_id: Mapped[int] = mapped_column(ForeignKey('workshops.id'), index=True)
    part_id: Mapped[int] = mapped_column(ForeignKey('catalog_parts.id'))
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=0, server_default='0')
    unit: Mapped[str] = mapped_column(String(20), default='unidad', server_default='unidad')


class PartRequest(Base):
    __tablename__ = 'part_requests'
    __table_args__ = (UniqueConstraint('order_id', 'request_key', name='uq_part_request_key'),
        CheckConstraint('quantity > 0', name='request_positive'),
        CheckConstraint("status IN ('requested','approved','issued','rejected')", name='part_request_status'))
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey('work_orders.id'), index=True)
    task_id: Mapped[int] = mapped_column(ForeignKey('checklist_items.id'))
    part_id: Mapped[int | None] = mapped_column(ForeignKey('catalog_parts.id'))
    description: Mapped[str] = mapped_column(String(250))
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3))
    unit: Mapped[str] = mapped_column(String(20), default='unidad', server_default='unidad')
    reason: Mapped[str] = mapped_column(String(1000))
    request_key: Mapped[str] = mapped_column(String(36))
    status: Mapped[str] = mapped_column(String(20), default='requested', server_default='requested')
    quote_id: Mapped[int | None] = mapped_column(ForeignKey('extra_quotes.id'))
    authorization_basis: Mapped[str] = mapped_column(String(24), default='', server_default='')
    resolution_note: Mapped[str] = mapped_column(String(1000), default='', server_default='')
    created_by: Mapped[int] = mapped_column(ForeignKey('users.id'))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    resolved_by: Mapped[int | None] = mapped_column(ForeignKey('users.id'))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revision: Mapped[int] = mapped_column(default=1, server_default='1')


class StockMovement(Base):
    __tablename__ = 'stock_movements'
    __table_args__ = (UniqueConstraint('workshop_id', 'request_key', name='uq_stock_movement_key'),
                     UniqueConstraint('part_request_id', name='uq_stock_issue_once'),
                     CheckConstraint('delta != 0', name='stock_nonzero'))
    id: Mapped[int] = mapped_column(primary_key=True)
    workshop_id: Mapped[int] = mapped_column(ForeignKey('workshops.id'), index=True)
    stock_item_id: Mapped[int] = mapped_column(ForeignKey('stock_items.id'), index=True)
    part_request_id: Mapped[int | None] = mapped_column(ForeignKey('part_requests.id'))
    delta: Mapped[Decimal] = mapped_column(Numeric(12, 3))
    request_key: Mapped[str] = mapped_column(String(36))
    reason: Mapped[str] = mapped_column(String(1000))
    actor_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class IntakePhoto(Base):
    __tablename__ = "intake_photos"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("work_orders.id"), index=True)
    uploaded_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    task_id: Mapped[int | None] = mapped_column(ForeignKey("checklist_items.id"), index=True)
    inspection_id: Mapped[int | None] = mapped_column(ForeignKey("inspections.id"), index=True)
    finding_id: Mapped[int | None] = mapped_column(ForeignKey("findings.id"))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    caption: Mapped[str] = mapped_column(String(250), default="")
    content: Mapped[bytes] = mapped_column(LargeBinary, deferred=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AppConfiguration(Base):
    __tablename__ = "app_configurations"
    scope: Mapped[str] = mapped_column(String(100), primary_key=True)
    payload: Mapped[dict] = mapped_column(JSON)
    revision: Mapped[int] = mapped_column(default=1)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Device(Base):
    __tablename__ = "devices"
    __table_args__ = (UniqueConstraint("user_id", "device_key", name="user_device"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    device_key: Mapped[str] = mapped_column(String(36))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        CheckConstraint("status IN ('pending','sent','failed')", name="notification_status"),
        Index("notification_due", "status", "next_attempt_at"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True, nullable=True)
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id"), index=True, nullable=True)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("work_orders.id"), nullable=True)
    kind: Mapped[str] = mapped_column(String(50))
    channel: Mapped[str] = mapped_column(String(20))
    encrypted_payload: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    attempts: Mapped[int] = mapped_column(default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_error: Mapped[str | None] = mapped_column(String(250))
    # En pausa conserva el estado original y el contenido cifrado. El worker
    # no la selecciona hasta una corrección/reanudación explícita o al arrancar.
    blocked_reason: Mapped[str | None] = mapped_column(String(250))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archived_by: Mapped[int | None] = mapped_column(ForeignKey('users.id'))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    provider_message_id: Mapped[str | None] = mapped_column(String(200))

    @property
    def payload_data(self) -> dict:
        if not self.encrypted_payload:
            return getattr(self, "_transient_payload", {}) or {}
        try:
            from .security import decrypt_payload
            return decrypt_payload(self.encrypted_payload) or {}
        except Exception:
            return {}

    @property
    def recipient(self) -> str | None:
        p = self.payload_data
        return p.get("to") or p.get("whatsapp") or p.get("chat_id") or getattr(self, "_recipient", None)

    @recipient.setter
    def recipient(self, value: str):
        self._recipient = value

    @property
    def subject(self) -> str | None:
        p = self.payload_data
        return p.get("title") or getattr(self, "_subject", None)

    @subject.setter
    def subject(self, value: str):
        self._subject = value

    @property
    def body(self) -> str | None:
        p = self.payload_data
        return p.get("body") or getattr(self, "_body", None)

    @body.setter
    def body(self, value: str):
        self._body = value



class InboxEvent(Base):
    __tablename__ = "inbox_events"
    __table_args__ = (Index('ix_inbox_events_user_id_id', 'user_id', 'id'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("work_orders.id"))
    kind: Mapped[str] = mapped_column(String(50), default='legacy', server_default='legacy')
    inspection_id: Mapped[int | None] = mapped_column(ForeignKey('inspections.id', ondelete='SET NULL'))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Workshop(Base):
    __tablename__ = "workshops"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    layout_revision: Mapped[int] = mapped_column(default=1, server_default="1")


class WorkAssignment(Base):
    __tablename__ = "work_assignments"
    __table_args__ = (Index("one_active_assignment", "order_id", "mechanic_id", unique=True,
        postgresql_where=text("revoked_at IS NULL"), sqlite_where=text("revoked_at IS NULL")),)
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("work_orders.id"), index=True)
    mechanic_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    mechanic: Mapped["User"] = relationship(foreign_keys=[mechanic_id])
    task_ids: Mapped[list] = mapped_column(JSON)
    can_quote: Mapped[bool] = mapped_column(Boolean, default=False)
    assigned_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    revision: Mapped[int] = mapped_column(default=1)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))


class Inspection(Base):
    __tablename__ = "inspections"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("work_orders.id"), index=True)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id"), index=True)
    task_id: Mapped[int | None] = mapped_column(ForeignKey("checklist_items.id"))
    title: Mapped[str] = mapped_column(String(150))
    template_id: Mapped[str] = mapped_column(String(80), default="sedan-neutral-v1")
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    revision: Mapped[int] = mapped_column(default=1)
    review_status: Mapped[str] = mapped_column(String(20), default="draft")
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    published_revision: Mapped[int | None] = mapped_column(Integer)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    findings: Mapped[list["Finding"]] = relationship(order_by="Finding.id")


class Finding(Base):
    __tablename__ = "findings"
    __table_args__ = (
        CheckConstraint("x >= 0 AND x <= 1 AND y >= 0 AND y <= 1", name="finding_coordinates"),
        CheckConstraint("condition IN ('no_data','normal','follow_up','issue')", name="finding_condition"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    inspection_id: Mapped[int] = mapped_column(ForeignKey("inspections.id"), index=True)
    component_id: Mapped[str] = mapped_column(String(80))
    view_id: Mapped[str] = mapped_column(String(80))
    x: Mapped[Decimal | None] = mapped_column(Numeric(10, 8))
    y: Mapped[Decimal | None] = mapped_column(Numeric(10, 8))
    polygon: Mapped[list | None] = mapped_column(JSON, nullable=True)
    category: Mapped[str] = mapped_column(String(80))
    severity: Mapped[str] = mapped_column(String(30))
    condition: Mapped[str] = mapped_column(String(20))
    note: Mapped[str] = mapped_column(Text)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class InspectionRevision(Base):
    __tablename__ = "inspection_revisions"
    __table_args__ = (UniqueConstraint("inspection_id", "version", name="inspection_version"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    inspection_id: Mapped[int] = mapped_column(ForeignKey("inspections.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    snapshot: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    workshop_id: Mapped[int] = mapped_column(ForeignKey("workshops.id"), index=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(80))
    resource_type: Mapped[str] = mapped_column(String(40))
    resource_id: Mapped[int] = mapped_column(Integer, index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class WorkshopZone(Base):
    __tablename__ = "workshop_zones"
    id: Mapped[int] = mapped_column(primary_key=True)
    workshop_id: Mapped[int] = mapped_column(ForeignKey("workshops.id"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    kind: Mapped[str] = mapped_column(String(80), default="service")
    capacity: Mapped[int] = mapped_column(Integer)
    x: Mapped[Decimal] = mapped_column(Numeric(10, 8))
    y: Mapped[Decimal] = mapped_column(Numeric(10, 8))
    width: Mapped[Decimal] = mapped_column(Numeric(10, 8))
    height: Mapped[Decimal] = mapped_column(Numeric(10, 8))
    revision: Mapped[int] = mapped_column(default=1)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (CheckConstraint("capacity > 0", name="zone_capacity"),)


class WorkshopBay(Base):
    __tablename__ = "workshop_bays"
    id: Mapped[int] = mapped_column(primary_key=True)
    workshop_id: Mapped[int] = mapped_column(ForeignKey("workshops.id"), index=True)
    zone_id: Mapped[int] = mapped_column(ForeignKey("workshop_zones.id"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    kind: Mapped[str] = mapped_column(String(80))
    capacity: Mapped[int] = mapped_column(Integer)
    x: Mapped[Decimal] = mapped_column(Numeric(10, 8))
    y: Mapped[Decimal] = mapped_column(Numeric(10, 8))
    width: Mapped[Decimal] = mapped_column(Numeric(10, 8))
    height: Mapped[Decimal] = mapped_column(Numeric(10, 8))
    revision: Mapped[int] = mapped_column(default=1)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (CheckConstraint("capacity > 0", name="bay_capacity"),)


class BayOccupancy(Base):
    __tablename__ = "bay_occupancies"
    __table_args__ = (Index("one_current_location", "order_id", unique=True,
        postgresql_where=text("exited_at IS NULL"), sqlite_where=text("exited_at IS NULL")),)
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("work_orders.id"), index=True)
    bay_id: Mapped[int] = mapped_column(ForeignKey("workshop_bays.id"), index=True)
    entered_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    entered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    exited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    exited_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    reason: Mapped[str] = mapped_column(String(250))
