from sqlalchemy.orm import Session

from app.models.appointment import Appointment
from app.models.payment import Payment
from app.models.professional import Professional
from app.models.professional_service import ProfessionalService
from app.models.service import Service
from app.repositories import ServiceRepository
from app.repositories.base import RelatedRecordsError
from app.schemas.service import ServiceCreate, ServiceUpdate


class ServiceService:
    def __init__(self, db: Session):
        self.repo = ServiceRepository(db)

    def create(self, data: ServiceCreate):
        if not self.repo.db.get(Professional, data.professional_id):
            raise ValueError("Profissional não encontrado")
        return self.repo.create(**data.model_dump())

    def get(self, service_id: int):
        return self.repo.get(service_id)

    def list(self, professional_id: int | None = None, category: str | None = None, skip: int = 0, limit: int = 100):
        if professional_id is not None:
            return self.repo.list_by_professional(professional_id)
        if category is not None:
            return self.repo.list_by_category(category)
        # Quando sem filtro, carrega o relacionamento professional para incluir o nome
        return self.repo.list_with_professional(skip=skip, limit=limit)

    def update(self, service_id: int, data: ServiceUpdate):
        return self.repo.update(service_id, **data.model_dump(exclude_unset=True))

    def delete(self, service_id: int):
        if self.repo.db.query(Appointment.id).filter(
            Appointment.service_id == service_id
        ).first():
            raise RelatedRecordsError(
                "Serviço possui agendamentos e não pode ser excluído"
            )
        return self.repo.delete(service_id)


class ServiceCatalogService:
    """Applies safe archival rules to the shared service catalog."""

    def __init__(self, db: Session):
        self.db = db

    def create(self, *, name: str, description: str | None, category: str | None) -> Service:
        service = Service(name=name, description=description, category=category)
        self.db.add(service)
        self.db.commit()
        self.db.refresh(service)
        return service

    def update(
        self,
        service_id: int,
        *,
        name: str | None = None,
        description: str | None = None,
        category: str | None = None,
    ) -> Service | None:
        service = self.db.get(Service, service_id)
        if not service:
            return None
        if name is not None:
            service.name = name
        if description is not None:
            service.description = description
        if category is not None:
            service.category = category
        self.db.commit()
        self.db.refresh(service)
        return service

    def reactivate(self, service_id: int) -> Service | None:
        service = self.db.get(Service, service_id)
        if not service:
            return None
        service.active = True
        self.db.commit()
        self.db.refresh(service)
        return service

    def archive_or_delete(self, service_id: int) -> str | None:
        service = self.db.get(Service, service_id)
        if not service:
            return None

        has_appointments = self.db.query(Appointment.id).filter(
            Appointment.service_id == service_id
        ).first()
        has_payments = self.db.query(Payment.id).join(Appointment).filter(
            Appointment.service_id == service_id
        ).first()
        has_offerings = self.db.query(ProfessionalService.id).filter(
            ProfessionalService.service_id == service_id
        ).first()

        if has_appointments or has_payments or has_offerings:
            service.active = False
            for offering in service.professional_offerings:
                offering.active = False
            self.db.commit()
            return "archived"

        self.db.delete(service)
        self.db.commit()
        return "deleted"
