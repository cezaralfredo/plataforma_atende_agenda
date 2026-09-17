from sqlalchemy.orm import Session, joinedload

from app.models.service import Service
from app.repositories.base import BaseRepository


class ServiceRepository(BaseRepository):
    def __init__(self, db: Session):
        super().__init__(db, Service)

    def list_by_professional(self, professional_id: int, include_inactive: bool = False):
        query = self.db.query(Service).filter(Service.professional_id == professional_id)
        if not include_inactive and hasattr(Service, "active"):
            query = query.filter(Service.active.is_(True))
        return query.all()

    def list_by_category(self, category: str, include_inactive: bool = False):
        query = self.db.query(Service).filter(Service.category == category)
        if not include_inactive and hasattr(Service, "active"):
            query = query.filter(Service.active.is_(True))
        return query.all()

    def list_with_professional(self, skip: int = 0, limit: int = 100, include_inactive: bool = False):
        """Lista serviços carregando o relacionamento professional (para incluir nome na resposta)"""
        query = self.db.query(Service).options(joinedload(Service.professional))
        if not include_inactive and hasattr(Service, "active"):
            query = query.filter(Service.active.is_(True))
        return query.offset(skip).limit(limit).all()
