from sqlalchemy.orm import Session

from app.models.user import User
from app.repositories.base import BaseRepository


from app.utils.sanitizers import clean_digits


class UserRepository(BaseRepository):
    def __init__(self, db: Session):
        super().__init__(db, User)

    def find_by_phone(self, phone: str):
        digits = clean_digits(phone)
        candidates = {phone}
        if digits:
            candidates.add(digits)
            candidates.add(f"+{digits}")
        return self.db.query(User).filter(User.phone.in_(candidates)).first()
