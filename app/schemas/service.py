from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class ServiceCreate(BaseModel):
    professional_id: int
    name: str
    description: str | None = None
    duration_minutes: int = Field(gt=0)
    price_cents: int = Field(ge=0)
    category: str | None = None


class ServiceUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    duration_minutes: int | None = Field(default=None, gt=0)
    price_cents: int | None = Field(default=None, ge=0)
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
    created_at: datetime | None = None
