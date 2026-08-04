from datetime import time
from pydantic import BaseModel, ConfigDict


class AvailabilityCreate(BaseModel):
    professional_id: int
    day_of_week: int | None = None
    start_time: str | None = None
    end_time: str | None = None
    specific_date: str | None = None


class AvailabilityUpdate(BaseModel):
    day_of_week: int | None = None
    start_time: str | None = None
    end_time: str | None = None
    specific_date: str | None = None


class AvailabilityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    professional_id: int
    day_of_week: int | None = None
    start_time: str | None = None
    end_time: str | None = None
    specific_date: str | None = None


class TimeSlot(BaseModel):
    start: str
    end: str
