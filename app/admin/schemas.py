from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, ConfigDict
from enum import Enum


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
    clients_total: int


class AdminAppointment(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    professional_id: int
    service_id: int
    start_time: datetime
    end_time: datetime
    status: str
    expires_at: Optional[datetime] = None
    notes: Optional[str] = None
    created_at: datetime

    # Related data
    client_name: Optional[str] = None
    client_phone: Optional[str] = None
    professional_name: Optional[str] = None
    service_name: Optional[str] = None
    service_price_cents: Optional[int] = None
    payment_status: Optional[str] = None
    payment_id: Optional[int] = None


class AdminPayment(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    appointment_id: int
    asaas_payment_id: Optional[str] = None
    amount_cents: int
    billing_type: str
    status: str
    invoice_url: Optional[str] = None
    received_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    # Related data
    client_name: Optional[str] = None
    client_phone: Optional[str] = None
    professional_name: Optional[str] = None
    service_name: Optional[str] = None
    appointment_start: Optional[datetime] = None


class AdminProfessional(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    bio: Optional[str] = None
    photo_url: Optional[str] = None
    active: bool

    # Computed
    services_count: int = 0
    appointments_today: int = 0
    appointments_week: int = 0
    revenue_month_cents: int = 0


class AdminFilters(BaseModel):
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    professional_id: Optional[int] = None
    status: Optional[str] = None
    search: Optional[str] = None
    page: int = 1
    page_size: int = 20


class AppointmentAction(BaseModel):
    action: str  # cancel, confirm
    notes: Optional[str] = None


class PaymentAction(BaseModel):
    action: str  # refresh, refund