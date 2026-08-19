from sqlalchemy.orm import Session

from app.models.user import User
from app.repositories import UserRepository
from app.schemas.user import UserCreate, UserUpdate


class UserService:
    def __init__(self, db: Session):
        self.repo = UserRepository(db)

    def find_by_phone(self, phone: str) -> User | None:
        return self.repo.find_by_phone(phone)

    def get(self, user_id: int) -> User | None:
        return self.repo.get(user_id)

    def create(self, data: UserCreate) -> User:
        if self.repo.find_by_phone(data.phone):
            raise ValueError("Telefone já cadastrado")
        return self.repo.create(**data.model_dump())

    def update(self, user_id: int, data: UserUpdate) -> User | None:
        values = data.model_dump(exclude_unset=True)
        if "phone" in values:
            existing = self.repo.find_by_phone(values["phone"])
            if existing and existing.id != user_id:
                raise ValueError("Telefone já cadastrado")
        return self.repo.update(user_id, **values)

    def link_whatsapp(self, user_id: int, whatsapp_number: str) -> User | None:
        return self.repo.update(user_id, whatsapp_number=whatsapp_number)