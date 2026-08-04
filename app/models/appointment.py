from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Appointment(Base):
    __tablename__ = "appointments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    professional_id: Mapped[int] = mapped_column(
        ForeignKey("professionals.id"), nullable=False
    )
    service_id: Mapped[int] = mapped_column(
        ForeignKey("services.id"), nullable=False
    )
    start_time: Mapped[str] = mapped_column(String(30), nullable=False)
    end_time: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )
    expires_at: Mapped[str] = mapped_column(String(30), nullable=True)
    notified_at: Mapped[str] = mapped_column(String(30), nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(
        String(30), nullable=False, default="now()"
    )

    user = relationship("User", back_populates="appointments")
    professional = relationship("Professional", back_populates="appointments")
    service = relationship("Service", back_populates="appointments")
    payments = relationship("Payment", back_populates="appointment")
    notifications = relationship("NotificationLog", back_populates="appointment")
