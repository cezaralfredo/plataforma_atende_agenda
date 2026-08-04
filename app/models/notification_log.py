from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class NotificationLog(Base):
    __tablename__ = "notification_log"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    appointment_id: Mapped[int] = mapped_column(
        ForeignKey("appointments.id"), nullable=False
    )
    type: Mapped[str] = mapped_column(String(30), nullable=False)
    sent_at: Mapped[str] = mapped_column(
        String(30), nullable=False, default="now()"
    )

    appointment = relationship("Appointment", back_populates="notifications")
