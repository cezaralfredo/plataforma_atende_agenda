from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy.orm import joinedload

from app.models.appointment import Appointment
from app.repositories import UserRepository
from app.repositories.appointment_repo import AppointmentRepository
from app.models.payment import Payment
from app.repositories.payment_repo import PaymentRepository
from app.services.asaas_client import AsaasClient


class PaymentService:
    def __init__(self, db: Session):
        self.db = db
        self.asaas = AsaasClient()
        self.user_repo = UserRepository(db)
        self.appointment_repo = AppointmentRepository(db)
        self.payment_repo = PaymentRepository(db)

    async def ensure_asaas_customer(self, user_id: int) -> str:
        user = self.user_repo.get(user_id)
        if not user:
            raise ValueError("Usuário não encontrado")

        if user.asaas_customer_id:
            return user.asaas_customer_id

        resp = await self.asaas.create_customer(
            name=user.name,
            phone=user.phone,
            email=user.email,
        )
        customer_id = resp["id"]
        self.user_repo.update(user_id, asaas_customer_id=customer_id)
        return customer_id

    async def create_charge(self, appointment_id: int, billing_type: str = "undefined", amount_cents: int | None = None) -> Payment:
        # Eager load related objects
        appointment = self.db.query(Appointment).options(
            joinedload(Appointment.service),
            joinedload(Appointment.professional),
            joinedload(Appointment.user)
        ).filter(Appointment.id == appointment_id).first()

        if not appointment:
            raise ValueError("Agendamento não encontrado")

        if appointment.status in {"cancelled", "completed"}:
            raise ValueError("Cannot charge a cancelled or completed appointment")

        billing_type = billing_type.lower()
        asaas_billing_type = billing_type.upper()
        if asaas_billing_type not in {"PIX", "BOLETO", "CREDIT_CARD", "UNDEFINED"}:
            raise ValueError("Invalid billing type")

        existing = self.payment_repo.list_by_appointment(appointment_id)
        active_payment = next(
            (payment for payment in existing if payment.status in {"pending", "received", "confirmed"}),
            None,
        )
        if active_payment:
            return active_payment

        customer_id = await self.ensure_asaas_customer(appointment.user_id)
        due_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        value_cents = 0

        if appointment.service:
            value_cents = appointment.service.price_cents
        if amount_cents is not None and amount_cents != value_cents:
            raise ValueError("Charge amount must match the service price")

        resp = await self.asaas.create_payment(
            customer_id=customer_id,
            value=value_cents / 100.0,
            due_date=due_date,
            description=f"{appointment.service.name} - {appointment.professional.name}" if appointment.service else "Agendamento",
            billing_type=asaas_billing_type,
        )

        payment = Payment(
            appointment_id=appointment_id,
            asaas_payment_id=resp["id"],
            amount_cents=value_cents,
            billing_type=billing_type,
            status="pending",
            invoice_url=resp.get("invoiceUrl", ""),
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        self.db.add(payment)
        self.db.commit()
        self.db.refresh(payment)

        self.appointment_repo.update(appointment_id, status="awaiting_payment")
        return payment

    async def check_payment_status(self, payment: Payment) -> str:
        if not payment.asaas_payment_id:
            return payment.status

        resp = await self.asaas.get_payment(payment.asaas_payment_id)
        asaas_status = resp.get("status", "")

        status_map = {
            "PENDING": "pending",
            "RECEIVED": "received",
            "CONFIRMED": "confirmed",
            "OVERDUE": "overdue",
            "REFUNDED": "refunded",
            "CANCELLED": "cancelled",
        }
        new_status = status_map.get(asaas_status, payment.status)

        if new_status != payment.status:
            payment.status = new_status
            payment.updated_at = datetime.now()
            if new_status in ("received", "confirmed"):
                payment.received_at = datetime.now()
                self.appointment_repo.update(payment.appointment_id, status="confirmed")
            self.db.commit()

        return new_status

    async def verify_recent_payments(self) -> list[Payment]:
        pending_payments = (
            self.db.query(Payment)
            .filter(Payment.status.in_(["pending", "awaiting_payment"]))
            .filter(Payment.asaas_payment_id.isnot(None))
            .all()
        )

        updated: list[Payment] = []
        for payment in pending_payments:
            try:
                old_status = payment.status
                await self.check_payment_status(payment)
                if payment.status != old_status:
                    updated.append(payment)
            except Exception:
                continue

        return updated

    def get_payment_by_appointment(self, appointment_id: int) -> Optional[Payment]:
        return self.db.query(Payment).filter(Payment.appointment_id == appointment_id).first()
