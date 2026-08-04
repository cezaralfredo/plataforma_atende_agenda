from sqlalchemy.orm import Session

from app.repositories import ProfessionalRepository
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
        return self.repo.update(professional_id, **data.model_dump())

    def delete(self, professional_id: int):
        return self.repo.delete(professional_id)
