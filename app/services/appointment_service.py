from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.repositories import AppointmentRepository
from app.schemas.appointment import AppointmentCreate, AppointmentUpdate
from app.services.availability_service import AvailabilityService


class AppointmentService:
    def __init__(self, db: Session):
        self.repo = AppointmentRepository(db)
        self.availability_service = AvailabilityService(db)

    def create(self, data: AppointmentCreate):
        conflicts = self.repo.find_conflicting(
            data.professional_id, data.start_time, data.end_time
        )
        if conflicts:
            raise ValueError("Já existe uma reserva neste horário")

        expires_at = (datetime.now() + timedelta(minutes=30)).isoformat()
        return self.repo.create(
            **data.model_dump(),
            status="pending",
            expires_at=expires_at,
            created_at=datetime.now().isoformat(),
        )

    def get(self, appointment_id: int):
        return self.repo.get(appointment_id)

    def list(
        self,
        user_id: int | None = None,
        professional_id: int | None = None,
        status: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ):
        if user_id is not None:
            return self.repo.list_by_user(user_id)
        if professional_id is not None:
            return self.repo.list_by_professional(professional_id)
        if status is not None:
            return self.repo.list_by_status(status)
        return self.repo.list(skip=skip, limit=limit)

    def update(self, appointment_id: int, data: AppointmentUpdate):
        return self.repo.update(appointment_id, **data.model_dump())

    def cancel(self, appointment_id: int):
        return self.repo.update(appointment_id, status="cancelled")

    def confirm(self, appointment_id: int):
        return self.repo.update(appointment_id, status="confirmed")

    def delete(self, appointment_id: int):
        return self.repo.delete(appointment_id)
