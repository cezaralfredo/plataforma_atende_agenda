from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.business_time import as_business_time
from app.models.professional import Professional
from app.models.professional_service import ProfessionalService
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
        self.repo.expire_reservations(datetime.now(UTC))
        self.repo.db.commit()

    def create(self, data: AppointmentCreate):
        now = datetime.now(UTC)
        self._expire_pending()

        if not self.repo.db.get(User, data.user_id):
            raise ValueError("Cliente n\u00e3o encontrado")
        professional = self.repo.db.get(Professional, data.professional_id)
        if not professional or not professional.active:
            raise ValueError("Profissional n\u00e3o encontrado ou inativo")
        service = self.repo.db.get(Service, data.service_id)
        if not service or not service.active:
            raise ValueError("Serviço indisponível")
        offering = (
            self.repo.db.query(ProfessionalService)
            .filter(
                ProfessionalService.professional_id == data.professional_id,
                ProfessionalService.service_id == data.service_id,
                ProfessionalService.active.is_(True),
            )
            .first()
        )
        if not offering:
            raise ValueError("Serviço indisponível para o profissional informado")

        start_time = as_business_time(data.start_time)
        end_time = as_business_time(data.end_time)
        expected_end = start_time + timedelta(minutes=offering.duration_minutes)
        if end_time != expected_end:
            raise ValueError("A dura\u00e7\u00e3o da reserva deve corresponder \u00e0 dura\u00e7\u00e3o do servi\u00e7o")

        available = self.availability_service.is_interval_available(
            data.professional_id, start_time, end_time
        )
        if not available:
            raise ValueError("O hor\u00e1rio solicitado est\u00e1 fora da disponibilidade do profissional")

        # Check for conflicts
        conflicts = self.repo.find_conflicting(
            data.professional_id, start_time, end_time
        )
        if conflicts:
            raise ValueError("Já existe uma reserva neste horário")

        expires_at = now + timedelta(minutes=30)
        try:
            return self.repo.create(
                **data.model_dump(exclude={"start_time", "end_time"}),
                start_time=start_time,
                end_time=end_time,
                status="pending",
                expires_at=expires_at,
                created_at=now,
                service_price_cents=offering.price_cents,
                service_duration_minutes=offering.duration_minutes,
                professional_commission_percent=offering.commission_percent,
            )
        except IntegrityError as exc:
            self.repo.db.rollback()
            constraint_name = getattr(
                getattr(exc.orig, "diag", None), "constraint_name", None
            )
            if constraint_name == "exclude_professional_overlapping_appointments":
                raise ValueError("Já existe uma reserva neste horário") from exc
            raise

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
        appointment = self.get(appointment_id)
        if not appointment:
            return None
        if appointment.status == "completed":
            raise ValueError("Não é possível cancelar um agendamento concluído")
        if appointment.status == "cancelled":
            return appointment
        return self.repo.update(appointment_id, status="cancelled")

    def confirm(self, appointment_id: int):
        appointment = self.get(appointment_id)
        if not appointment:
            return None
        if appointment.status == "confirmed":
            return appointment
        if appointment.status in {"cancelled", "completed"}:
            raise ValueError("N\u00e3o \u00e9 poss\u00edvel confirmar este agendamento")
        if appointment.status == "pending" and appointment.expires_at and appointment.expires_at <= datetime.now(UTC):
            self.repo.update(appointment_id, status="cancelled")
            raise ValueError("A reserva expirou")
        return self.repo.update(appointment_id, status="confirmed")

    def delete(self, appointment_id: int):
        return self.repo.delete(appointment_id)
