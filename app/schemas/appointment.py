from pydantic import BaseModel, ConfigDict


class AppointmentCreate(BaseModel):
    user_id: int
    professional_id: int
    service_id: int
    start_time: str
    end_time: str
    notes: str | None = None


class AppointmentUpdate(BaseModel):
    status: str | None = None
    notes: str | None = None
    notified_at: str | None = None
    expires_at: str | None = None


class AppointmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    professional_id: int
    service_id: int
    start_time: str
    end_time: str
    status: str
    expires_at: str | None = None
    notified_at: str | None = None
    notes: str | None = None
    created_at: str | None = None
