from sqlalchemy.orm import Session, joinedload

from app.models.professional_service import ProfessionalService
from app.models.service import Service
from app.repositories.base import BaseRepository


class ServiceRepository(BaseRepository):
    def __init__(self, db: Session):
        super().__init__(db, Service)

    def list_catalog(self, skip: int = 0, limit: int = 100, active_only: bool = False):
        query = self.db.query(Service).options(
            joinedload(Service.professional_offerings).joinedload(ProfessionalService.professional)
        )
        if active_only:
            query = query.filter(Service.active.is_(True))
        return query.order_by(Service.id).offset(skip).limit(limit).all()

    def list_by_professional(self, professional_id: int, include_inactive: bool = False):
        query = (
            self.db.query(Service)
            .join(ProfessionalService, ProfessionalService.service_id == Service.id)
            .filter(ProfessionalService.professional_id == professional_id)
            .options(
                joinedload(Service.professional_offerings).joinedload(ProfessionalService.professional)
            )
        )
        if not include_inactive:
            query = query.filter(
                Service.active.is_(True),
                ProfessionalService.active.is_(True),
            )
        return query.order_by(Service.id).all()

    def list_by_category(self, category: str, skip: int = 0, limit: int = 100, active_only: bool = False):
        query = (
            self.db.query(Service)
            .filter(Service.category == category)
            .options(
                joinedload(Service.professional_offerings).joinedload(ProfessionalService.professional)
            )
        )
        if active_only:
            query = query.filter(Service.active.is_(True))
        return query.order_by(Service.id).offset(skip).limit(limit).all()

    def list_with_professional(self, skip: int = 0, limit: int = 100, include_inactive: bool = False):
        """Lista serviços carregando os profissionais vinculados"""
        query = self.db.query(Service).options(
            joinedload(Service.professional_offerings).joinedload(ProfessionalService.professional)
        )
        if not include_inactive:
            query = query.filter(Service.active.is_(True))
        return query.order_by(Service.id).offset(skip).limit(limit).all()
