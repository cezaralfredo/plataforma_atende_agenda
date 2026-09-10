from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AppointmentStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    AWAITING_PAYMENT = "awaiting_payment"


class PaymentStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    RECEIVED = "received"
    OVERDUE = "overdue"
    REFUNDED = "refunded"
    CANCELLED = "cancelled"


class AdminKPIs(BaseModel):
    appointments_today: int
    appointments_pending: int
    appointments_confirmed: int
    revenue_today_cents: int
    revenue_week_cents: int
    revenue_month_cents: int
    payments_pending: int
    payments_overdue: int
    professionals_active: int
    professionals_total: int
    users_total: int


class AdminAppointment(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    professional_id: int
    service_id: int
    start_time: datetime
    end_time: datetime
    status: str
    expires_at: datetime | None = None
    notes: str | None = None
    created_at: datetime

    # Related data
    client_name: str | None = None
    client_phone: str | None = None
    professional_name: str | None = None
    service_name: str | None = None
    service_price_cents: int | None = None
    payment_status: str | None = None
    payment_id: int | None = None


class AdminPayment(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    appointment_id: int
    asaas_payment_id: str | None = None
    amount_cents: int
    billing_type: str
    status: str
    invoice_url: str | None = None
    received_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    # Related data
    client_name: str | None = None
    client_phone: str | None = None
    professional_name: str | None = None
    service_name: str | None = None
    appointment_start: datetime | None = None


class AdminProfessional(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    phone: str | None = None
    email: str | None = None
    bio: str | None = None
    photo_url: str | None = None
    active: bool

    # Computed
    services_count: int = 0
    appointments_today: int = 0
    appointments_week: int = 0
    revenue_month_cents: int = 0


class AdminFilters(BaseModel):
    date_from: date | None = None
    date_to: date | None = None
    professional_id: int | None = None
    status: str | None = None
    search: str | None = None
    page: int = 1
    page_size: int = 20


class AdminClientCreate(BaseModel):
    name: str
    phone: str
    email: str | None = None
    whatsapp_number: str | None = None


class AdminAppointmentCreate(BaseModel):
    user_id: int | None = None
    new_client: AdminClientCreate | None = None
    professional_id: int
    service_id: int
    start_time: datetime
    end_time: datetime
    notes: str | None = None

    @model_validator(mode="after")
    def validate_client_source(self):
        if (self.user_id is None) == (self.new_client is None):
            raise ValueError("Informe um cliente existente ou cadastre um novo cliente")
        return self


class AdminAppointmentUpdate(BaseModel):
    user_id: int | None = None
    professional_id: int | None = None
    service_id: int | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    notes: str | None = None


class AdminProfessionalOfferingUpsert(BaseModel):
    service_id: int
    price_cents: int
    duration_minutes: int
    commission_percent: Decimal = Decimal("10.00")


class AdminAvailabilityInput(BaseModel):
    day_of_week: int | None = None
    start_time: time | None = None
    end_time: time | None = None
    specific_date: date | None = None


class AdminServiceCatalogCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    category: str | None = Field(default=None, max_length=100)


class AdminServiceCatalogUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    category: str | None = Field(default=None, max_length=100)


class AppointmentAction(BaseModel):
    action: Literal["cancel", "confirm", "complete"]
    notes: str | None = None


class PaymentAction(BaseModel):
    action: Literal["refresh", "refund", "archive", "unarchive", "delete_draft"]
