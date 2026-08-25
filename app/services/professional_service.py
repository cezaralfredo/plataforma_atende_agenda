from sqlalchemy.orm import Session

from app.models.appointment import Appointment
from app.models.service import Service
from app.repositories import ProfessionalRepository
from app.repositories.base import RelatedRecordsError
from app.schemas.professional import ProfessionalCreate, ProfessionalUpdate


class ProfessionalService:
    def __init__(self, db: Session):
        self.repo = ProfessionalRepository(db)

    def create(self, data: ProfessionalCreate):
        return self.repo.create(**data.model_dump())

    def get(self, professional_id: int):
        return self.repo.get(professional_id)

    def list(self, skip: int = 0, limit: int = 100, active_only: bool = False):
        if active_only:
            return self.repo.list_active()
        return self.repo.list(skip=skip, limit=limit)

    def update(self, professional_id: int, data: ProfessionalUpdate):
        return self.repo.update(
            professional_id, **data.model_dump(exclude_unset=True)
        )

    def delete(self, professional_id: int):
        has_history = self.repo.db.query(Appointment.id).filter(
            Appointment.professional_id == professional_id
        ).first() or self.repo.db.query(Service.id).filter(
            Service.professional_id == professional_id
        ).first()
        if has_history:
            raise RelatedRecordsError(
                "Profissional possui histórico; desative-o em vez de excluir"
            )
        return self.repo.delete(professional_id)
