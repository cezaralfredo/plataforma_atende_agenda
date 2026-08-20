from sqlalchemy.orm import Session

from app.repositories import ServiceRepository
from app.schemas.service import ServiceCreate, ServiceUpdate


class ServiceService:
    def __init__(self, db: Session):
        self.repo = ServiceRepository(db)

    def create(self, data: ServiceCreate):
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
        return self.repo.update(service_id, **data.model_dump())

    def delete(self, service_id: int):
        return self.repo.delete(service_id)
