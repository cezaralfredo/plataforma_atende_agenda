from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.professional import Professional
from app.models.service import Service
from app.models.user import User
from app.repositories import AppointmentRepository
from app.schemas.appointment import AppointmentCreate, AppointmentUpdate
from app.services.availability_service import AvailabilityService


class AppointmentService:
    def __init__(self, db: Session):
        self.repo = AppointmentRepository(db)
        self.availability_service = AvailabilityService(db)

    def _expire_pending(self) -> None:
        self.repo.expire_pending(datetime.now(timezone.utc))
        self.repo.db.commit()

    def create(self, data: AppointmentCreate):
        now = datetime.now(timezone.utc)
        self._expire_pending()

        if not self.repo.db.get(User, data.user_id):
            raise ValueError("Cliente n\u00e3o encontrado")
        professional = self.repo.db.get(Professional, data.professional_id)
        if not professional or not professional.active:
            raise ValueError("Profissional n\u00e3o encontrado ou inativo")
        service = self.repo.db.get(Service, data.service_id)
        if not service or service.professional_id != data.professional_id:
            raise ValueError("Servi\u00e7o n\u00e3o pertence ao profissional informado")

        expected_end = data.start_time + timedelta(minutes=service.duration_minutes)
        if data.end_time != expected_end:
            raise ValueError("A dura\u00e7\u00e3o da reserva deve corresponder \u00e0 dura\u00e7\u00e3o do servi\u00e7o")

        available = self.availability_service.is_interval_available(
            data.professional_id, data.start_time, data.end_time
        )
        if not available:
            raise ValueError("O hor\u00e1rio solicitado est\u00e1 fora da disponibilidade do profissional")

        # Check for conflicts
        conflicts = self.repo.find_conflicting(
            data.professional_id, data.start_time, data.end_time
        )
        if conflicts:
            raise ValueError("Já existe uma reserva neste horário")

        expires_at = now + timedelta(minutes=30)
        return self.repo.create(
            **data.model_dump(),
            status="pending",
            expires_at=expires_at,
            created_at=now,
        )

    def get(self, appointment_id: int):
        self._expire_pending()
        return self.repo.get(appointment_id)

    def list(
        self,
        user_id: int | None = None,
        professional_id: int | None = None,
        status: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ):
        self._expire_pending()
        if user_id is not None:
            return self.repo.list_by_user(user_id)
        if professional_id is not None:
            return self.repo.list_by_professional(professional_id)
        if status is not None:
            return self.repo.list_by_status(status)
        return self.repo.list(skip=skip, limit=limit)

    def update(self, appointment_id: int, data: AppointmentUpdate):
        values = data.model_dump(exclude_unset=True)
        if "status" in values:
            raise ValueError("Use the confirm or cancel actions to change appointment status")
        return self.repo.update(appointment_id, **values)

    def cancel(self, appointment_id: int):
        return self.repo.update(appointment_id, status="cancelled")

    def confirm(self, appointment_id: int):
        appointment = self.get(appointment_id)
        if not appointment:
            return None
        if appointment.status in {"cancelled", "completed"}:
            raise ValueError("N\u00e3o \u00e9 poss\u00edvel confirmar este agendamento")
        if appointment.status == "pending" and appointment.expires_at and appointment.expires_at <= datetime.now(timezone.utc):
            self.repo.update(appointment_id, status="cancelled")
            raise ValueError("A reserva expirou")
        return self.repo.update(appointment_id, status="confirmed")

    def delete(self, appointment_id: int):
        return self.repo.delete(appointment_id)
