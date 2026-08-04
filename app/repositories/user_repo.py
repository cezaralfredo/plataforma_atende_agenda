from sqlalchemy.orm import Session

from app.models.user import User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository):
    def __init__(self, db: Session):
        super().__init__(db, User)

    def find_by_phone(self, phone: str):
        return self.db.query(User).filter(User.phone == phone).first()
