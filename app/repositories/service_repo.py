from sqlalchemy.orm import Session

from app.models.service import Service
from app.repositories.base import BaseRepository


class ServiceRepository(BaseRepository):
    def __init__(self, db: Session):
        super().__init__(db, Service)

    def list_by_professional(self, professional_id: int):
        return self.db.query(Service).filter(Service.professional_id == professional_id).all()

    def list_by_category(self, category: str):
        return self.db.query(Service).filter(Service.category == category).all()
