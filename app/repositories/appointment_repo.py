from datetime import datetime

from sqlalchemy.orm import Session

from app.models.appointment import Appointment
from app.repositories.base import BaseRepository


class AppointmentRepository(BaseRepository):
    def __init__(self, db: Session):
        super().__init__(db, Appointment)

    def list_by_user(self, user_id: int):
        return self.db.query(Appointment).filter(Appointment.user_id == user_id).order_by(Appointment.start_time.desc()).all()

    def list_by_professional(self, professional_id: int):
        return self.db.query(Appointment).filter(Appointment.professional_id == professional_id).order_by(Appointment.start_time.desc()).all()

    def find_conflicting(self, professional_id: int, start_time: str, end_time: str, exclude_id: int | None = None):
        query = self.db.query(Appointment).filter(
            Appointment.professional_id == professional_id,
            Appointment.start_time < end_time,
            Appointment.end_time > start_time,
            Appointment.status.notin_(["cancelled"]),
        )
        if exclude_id:
            query = query.filter(Appointment.id != exclude_id)
        return query.all()

    def list_by_status(self, status: str):
        return self.db.query(Appointment).filter(Appointment.status == status).all()
