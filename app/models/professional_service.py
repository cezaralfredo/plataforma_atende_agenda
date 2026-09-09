from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ProfessionalService(Base):
    """Commercial conditions under which a professional offers a catalog service."""

    __tablename__ = "professional_services"
    __table_args__ = (
        UniqueConstraint(
            "professional_id", "service_id", name="uq_professional_services_pair"
        ),
        CheckConstraint("price_cents >= 0", name="check_professional_service_price"),
        CheckConstraint(
            "duration_minutes > 0", name="check_professional_service_duration"
        ),
        CheckConstraint(
            "commission_percent >= 0 AND commission_percent <= 100",
            name="check_professional_service_commission",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    professional_id: Mapped[int] = mapped_column(
        ForeignKey("professionals.id"), nullable=False, index=True
    )
    service_id: Mapped[int] = mapped_column(
        ForeignKey("services.id"), nullable=False, index=True
    )
    price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    commission_percent: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=Decimal("10.00")
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    professional = relationship("Professional", back_populates="service_offerings")
    service = relationship("Service", back_populates="professional_offerings")
