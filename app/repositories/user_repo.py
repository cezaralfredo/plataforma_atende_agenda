from sqlalchemy.orm import Session

from app.models.user import User
from app.repositories.base import BaseRepository


from app.utils.sanitizers import clean_digits


class UserRepository(BaseRepository):
    def __init__(self, db: Session):
        super().__init__(db, User)

    def find_by_phone(self, phone: str):
        if not phone or not str(phone).strip():
            return None
        raw_query = str(phone).strip()
        digits = clean_digits(raw_query)
        candidates = {raw_query}
        if digits:
            candidates.add(digits)
            candidates.add(f"+{digits}")
            if len(digits) in (10, 11):
                candidates.add(f"55{digits}")
                candidates.add(f"+55{digits}")
            elif digits.startswith("55") and len(digits) in (12, 13):
                candidates.add(digits[2:])
                candidates.add(f"+{digits[2:]}")

            # 1. Search by exact phone or whatsapp_number candidate
            user = (
                self.db.query(User)
                .filter(
                    (User.phone.in_(candidates))
                    | (User.whatsapp_number.in_(candidates))
                )
                .order_by(User.id.desc())
                .first()
            )
            if user:
                return user

            # 2. Match local number without DDD (8 or 9 digits)
            if len(digits) in (8, 9):
                user = (
                    self.db.query(User)
                    .filter(
                        (User.phone.like(f"%{digits}"))
                        | (User.whatsapp_number.like(f"%{digits}"))
                    )
                    .order_by(User.id.desc())
                    .first()
                )
                if user:
                    return user

        # 3. Fallback: Search by client name (case-insensitive substring)
        if len(raw_query) >= 3 and any(c.isalpha() for c in raw_query):
            user = (
                self.db.query(User)
                .filter(User.name.ilike(f"%{raw_query}%"))
                .order_by(User.id.desc())
                .first()
            )
            if user:
                return user

        return None

    def find_active_by_phone(self, phone: str):
        return self.find_by_phone(phone)


