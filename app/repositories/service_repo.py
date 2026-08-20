from sqlalchemy.orm import Session, joinedload

from app.models.service import Service
from app.repositories.base import BaseRepository


class ServiceRepository(BaseRepository):
    def __init__(self, db: Session):
        super().__init__(db, Service)

    def list_by_professional(self, professional_id: int):
        return self.db.query(Service).filter(Service.professional_id == professional_id).all()

    def list_by_category(self, category: str):
        return self.db.query(Service).filter(Service.category == category).all()

    def list_with_professional(self, skip: int = 0, limit: int = 100):
        """Lista serviços carregando o relacionamento professional (para incluir nome na resposta)"""
        return (
            self.db.query(Service)
            .options(joinedload(Service.professional))
            .offset(skip)
            .limit(limit)
            .all()
        )
