from sqlalchemy import ForeignKey, Integer, String, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Availability(Base):
    __tablename__ = "availability"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    professional_id: Mapped[int] = mapped_column(
        ForeignKey("professionals.id"), nullable=False
    )
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=True)
    start_time: Mapped[str] = mapped_column(String(8), nullable=True)
    end_time: Mapped[str] = mapped_column(String(8), nullable=True)
    specific_date: Mapped[str] = mapped_column(String(10), nullable=True)

    professional = relationship("Professional", back_populates="availability")
