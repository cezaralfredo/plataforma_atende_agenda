from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

from app.utils.sanitizers import clean_digits, clean_email, clean_phone, validate_cpf


class UserCreate(BaseModel):
    name: str
    phone: str
    email: str | None = None
    whatsapp_number: str | None = None
    cpf_cnpj: str | None = None

    @field_validator("phone", mode="before")
    @classmethod
    def sanitize_phone(cls, v: str | None) -> str | None:
        return clean_phone(v)

    @field_validator("whatsapp_number", mode="before")
    @classmethod
    def sanitize_whatsapp(cls, v: str | None) -> str | None:
        return clean_phone(v)

    @field_validator("email", mode="before")
    @classmethod
    def sanitize_email(cls, v: str | None) -> str | None:
        return clean_email(v)

    @field_validator("cpf_cnpj", mode="before")
    @classmethod
    def sanitize_cpf(cls, v: str | None) -> str | None:
        digits = clean_digits(v)
        if digits and not validate_cpf(digits):
            raise ValueError("CPF inválido")
        return digits


class UserUpdate(BaseModel):
    name: str | None = None
    phone: str | None = None
    email: str | None = None
    whatsapp_number: str | None = None
    cpf_cnpj: str | None = None
    asaas_customer_id: str | None = None

    @field_validator("phone", mode="before")
    @classmethod
    def sanitize_phone(cls, v: str | None) -> str | None:
        return clean_phone(v) if v is not None else None

    @field_validator("whatsapp_number", mode="before")
    @classmethod
    def sanitize_whatsapp(cls, v: str | None) -> str | None:
        return clean_phone(v) if v is not None else None

    @field_validator("email", mode="before")
    @classmethod
    def sanitize_email(cls, v: str | None) -> str | None:
        return clean_email(v) if v is not None else None

    @field_validator("cpf_cnpj", mode="before")
    @classmethod
    def sanitize_cpf(cls, v: str | None) -> str | None:
        if v is None:
            return None
        digits = clean_digits(v)
        if digits and not validate_cpf(digits):
            raise ValueError("CPF inválido")
        return digits


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    phone: str
    email: str | None = None
    whatsapp_number: str | None = None
    cpf_cnpj: str | None = None
    asaas_customer_id: str | None = None
    created_at: datetime | None = None
