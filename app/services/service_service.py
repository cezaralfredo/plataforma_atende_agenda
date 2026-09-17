from sqlalchemy.orm import Session

from app.models.appointment import Appointment
from app.models.professional import Professional
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

    def list(
        self,
        professional_id: int | None = None,
        category: str | None = None,
        skip: int = 0,
        limit: int = 100,
        include_inactive: bool = False,
    ):
        if professional_id is not None:
            return self.repo.list_by_professional(professional_id, include_inactive=include_inactive)
        if category is not None:
            return self.repo.list_by_category(category, include_inactive=include_inactive)
        return self.repo.list_with_professional(skip=skip, limit=limit, include_inactive=include_inactive)

    def update(self, service_id: int, data: ServiceUpdate):
        return self.repo.update(service_id, **data.model_dump(exclude_unset=True))

    def delete(self, service_id: int):
        service = self.get(service_id)
        if not service:
            return False
        if self.repo.db.query(Appointment.id).filter(
            Appointment.service_id == service_id
        ).first():
            # Soft delete to preserve historical appointments without database errors
            service.active = False
            self.repo.db.commit()
            return True
        return self.repo.delete(service_id)


# Backward compatibility alias
ServiceCatalogService = ServiceService
