from pydantic import BaseModel, ConfigDict


class ServiceCreate(BaseModel):
    professional_id: int
    name: str
    description: str | None = None
    duration_minutes: int
    price_cents: int
    category: str | None = None


class ServiceUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    duration_minutes: int | None = None
    price_cents: int | None = None
    category: str | None = None


class ServiceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    professional_id: int
    name: str
    description: str | None = None
    duration_minutes: int
    price_cents: int
    category: str | None = None
