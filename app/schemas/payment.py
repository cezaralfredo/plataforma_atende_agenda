from pydantic import BaseModel, ConfigDict


class PaymentCreate(BaseModel):
    appointment_id: int
    amount_cents: int
    billing_type: str = "pix"


class PaymentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    appointment_id: int
    asaas_payment_id: str | None = None
    amount_cents: int
    billing_type: str
    status: str
    invoice_url: str | None = None
    received_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class AsaasCustomerCreate(BaseModel):
    name: str
    cpfCnpj: str | None = None
    phone: str | None = None
    email: str | None = None


class AsaasPaymentCreate(BaseModel):
    customer: str
    billingType: str = "UNDEFINED"
    value: float
    dueDate: str
    description: str | None = None


class AsaasPaymentResponse(BaseModel):
    id: str
    invoiceUrl: str | None = None
    status: str
    value: float
    billingType: str
    dueDate: str


class AsaasCustomerResponse(BaseModel):
    id: str
    name: str
    cpfCnpj: str | None = None
    phone: str | None = None
    email: str | None = None


class AsaasWebhookEvent(BaseModel):
    event: str
    payment: dict | None = None
    subscription: dict | None = None
