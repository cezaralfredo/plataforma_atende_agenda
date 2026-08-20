from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict


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


class AppointmentAction(BaseModel):
    action: str  # cancel, confirm
    notes: str | None = None


class PaymentAction(BaseModel):
    action: str  # refresh, refund