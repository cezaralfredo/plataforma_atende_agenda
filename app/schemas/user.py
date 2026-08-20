from datetime import datetime
from pydantic import BaseModel, ConfigDict


class UserCreate(BaseModel):
    name: str
    phone: str
    email: str | None = None
    whatsapp_number: str | None = None


class UserUpdate(BaseModel):
    name: str | None = None
    phone: str | None = None
    email: str | None = None
    whatsapp_number: str | None = None
    asaas_customer_id: str | None = None


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    phone: str
    email: str | None = None
    whatsapp_number: str | None = None
    asaas_customer_id: str | None = None
    created_at: str | None = None
