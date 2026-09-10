from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Service(Base):
    __tablename__ = "services"
    __table_args__ = (
        CheckConstraint("duration_minutes > 0", name="check_service_duration"),
        CheckConstraint("price_cents >= 0", name="check_service_price"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    professional_id: Mapped[int] = mapped_column(
        ForeignKey("professionals.id"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=True)
    price_cents: Mapped[int] = mapped_column(Integer, nullable=True)
    category: Mapped[str] = mapped_column(String(100), nullable=True, index=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    professional = relationship("Professional", back_populates="services")
    professional_offerings = relationship(
        "ProfessionalService", back_populates="service", cascade="all, delete-orphan"
    )
    appointments = relationship("Appointment", back_populates="service")
