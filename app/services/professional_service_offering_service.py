from decimal import Decimal

from sqlalchemy.orm import Session, joinedload

from app.models.professional import Professional
from app.models.professional_service import ProfessionalService
from app.models.service import Service


class ProfessionalOfferingService:
    """Manages the commercial terms for a professional's catalog offering."""

    def __init__(self, db: Session):
        self.db = db

    def get(self, professional_id: int, service_id: int) -> ProfessionalService | None:
        return (
            self.db.query(ProfessionalService)
            .filter(
                ProfessionalService.professional_id == professional_id,
                ProfessionalService.service_id == service_id,
            )
            .first()
        )

    def get_active(
        self, professional_id: int, service_id: int
    ) -> ProfessionalService | None:
        return (
            self.db.query(ProfessionalService)
            .filter(
                ProfessionalService.professional_id == professional_id,
                ProfessionalService.service_id == service_id,
                ProfessionalService.active.is_(True),
            )
            .first()
        )

    def list_active(
        self,
        *,
        professional_id: int | None = None,
        category: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[ProfessionalService]:
        query = (
            self.db.query(ProfessionalService)
            .join(ProfessionalService.service)
            .join(ProfessionalService.professional)
            .options(
                joinedload(ProfessionalService.service),
                joinedload(ProfessionalService.professional),
            )
            .filter(
                ProfessionalService.active.is_(True),
                Service.active.is_(True),
                Professional.active.is_(True),
            )
        )
        if professional_id is not None:
            query = query.filter(ProfessionalService.professional_id == professional_id)
        if category is not None:
            query = query.filter(Service.category == category)
        return (
            query.order_by(Service.name, Professional.name)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def create_or_update(
        self,
        *,
        professional_id: int,
        service_id: int,
        price_cents: int,
        duration_minutes: int,
        commission_percent: Decimal = Decimal("10.00"),
    ) -> ProfessionalService:
        professional = self.db.get(Professional, professional_id)
        if not professional or not professional.active:
            raise ValueError("Profissional não encontrado ou inativo")
        service = self.db.get(Service, service_id)
        if not service or not service.active:
            raise ValueError("Serviço não encontrado ou inativo")
        if price_cents < 0:
            raise ValueError("O valor do serviço não pode ser negativo")
        if duration_minutes <= 0:
            raise ValueError("A duração do serviço deve ser maior que zero")

        commission_percent = Decimal(commission_percent)
        if not Decimal("0") <= commission_percent <= Decimal("100"):
            raise ValueError("A comissão deve estar entre 0% e 100%")

        offering = self.get(professional_id, service_id)
        if offering:
            offering.price_cents = price_cents
            offering.duration_minutes = duration_minutes
            offering.commission_percent = commission_percent
            offering.active = True
        else:
            offering = ProfessionalService(
                professional_id=professional_id,
                service_id=service_id,
                price_cents=price_cents,
                duration_minutes=duration_minutes,
                commission_percent=commission_percent,
                active=True,
            )
            self.db.add(offering)
        self.db.commit()
        self.db.refresh(offering)
        return offering

    def archive_or_delete(self, professional_id: int, service_id: int) -> str | None:
        offering = self.get(professional_id, service_id)
        if not offering:
            return None

        from app.models.appointment import Appointment

        has_history = (
            self.db.query(Appointment.id)
            .filter(
                Appointment.professional_id == professional_id,
                Appointment.service_id == service_id,
            )
            .first()
        )
        if has_history:
            offering.active = False
            self.db.commit()
            return "archived"
        self.db.delete(offering)
        self.db.commit()
        return "deleted"
