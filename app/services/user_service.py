from sqlalchemy.orm import Session

from app.models.appointment import Appointment
from app.models.user import User
from app.repositories import UserRepository
from app.repositories.base import RelatedRecordsError
from app.schemas.user import UserCreate, UserUpdate


class UserService:
    def __init__(self, db: Session):
        self.repo = UserRepository(db)

    def find_by_phone(self, phone: str) -> User | None:
        return self.repo.find_by_phone(phone)

    def get(self, user_id: int) -> User | None:
        return self.repo.get(user_id)

    def create(self, data: UserCreate) -> User:
        dump = data.model_dump()
        if self.repo.find_by_phone(dump["phone"]):
            raise ValueError("Telefone já cadastrado")
        if dump.get("email"):
            existing_email = self.repo.db.query(User).filter(User.email == dump["email"]).first()
            if existing_email:
                raise ValueError("E-mail já cadastrado por outro cliente")
        return self.repo.create(**dump)

    def update(self, user_id: int, data: UserUpdate) -> User | None:
        values = data.model_dump(exclude_unset=True)
        if "phone" in values and values["phone"]:
            existing = self.repo.find_by_phone(values["phone"])
            if existing and existing.id != user_id:
                raise ValueError("Telefone já cadastrado")
        if "email" in values and values["email"]:
            existing_email = (
                self.repo.db.query(User)
                .filter(User.email == values["email"], User.id != user_id)
                .first()
            )
            if existing_email:
                raise ValueError("E-mail já cadastrado por outro cliente")
        return self.repo.update(user_id, **values)

    def link_whatsapp(self, user_id: int, whatsapp_number: str) -> User | None:
        return self.repo.update(user_id, whatsapp_number=whatsapp_number)

    def delete(self, user_id: int) -> bool:
        if self.repo.db.query(Appointment.id).filter(
            Appointment.user_id == user_id
        ).first():
            raise RelatedRecordsError(
                "Cliente possui agendamentos e não pode ser excluído"
            )
        return self.repo.delete(user_id)
