from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    appointment_id: Mapped[int] = mapped_column(
        ForeignKey("appointments.id"), nullable=False
    )
    asaas_payment_id: Mapped[str] = mapped_column(String(50), nullable=True)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    billing_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pix"
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )
    invoice_url: Mapped[str] = mapped_column(String(500), nullable=True)
    received_at: Mapped[str] = mapped_column(String(30), nullable=True)
    created_at: Mapped[str] = mapped_column(
        String(30), nullable=False, default="now()"
    )
    updated_at: Mapped[str] = mapped_column(
        String(30), nullable=False, default="now()"
    )

    appointment = relationship("Appointment", back_populates="payments")
