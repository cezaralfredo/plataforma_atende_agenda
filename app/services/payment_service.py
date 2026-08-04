from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.repositories import UserRepository
from app.repositories.appointment_repo import AppointmentRepository
from app.models.payment import Payment
from app.services.asaas_client import AsaasClient


class PaymentService:
    def __init__(self, db: Session):
        self.db = db
        self.asaas = AsaasClient()
        self.user_repo = UserRepository(db)
        self.appointment_repo = AppointmentRepository(db)

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

    async def create_charge(self, appointment_id: int, billing_type: str = "UNDEFINED") -> Payment:
        appointment = self.appointment_repo.get(appointment_id)
        if not appointment:
            raise ValueError("Agendamento não encontrado")

        customer_id = await self.ensure_asaas_customer(appointment.user_id)
        due_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        value_cents = 0

        service = appointment.service
        if service:
            value_cents = service.price_cents

        resp = await self.asaas.create_payment(
            customer_id=customer_id,
            value=value_cents / 100.0,
            due_date=due_date,
            description=f"{service.name} - {appointment.professional.name}" if service else "Agendamento",
            billing_type=billing_type,
        )

        payment = Payment(
            appointment_id=appointment_id,
            asaas_payment_id=resp["id"],
            amount_cents=value_cents,
            billing_type=billing_type,
            status="pending",
            invoice_url=resp.get("invoiceUrl", ""),
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
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
            payment.updated_at = datetime.now().isoformat()
            if new_status == "received" or new_status == "confirmed":
                payment.received_at = datetime.now().isoformat()
                self.appointment_repo.update(payment.appointment_id, status="confirmed")
            self.db.commit()

        return new_status

    async def verify_recent_payments(self) -> list[Payment]:
        pending_payments = (
            self.db.query(Payment)
            .filter(Payment.status.in_(["pending", "confirmed"]))
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

    def get_payment_by_appointment(self, appointment_id: int) -> Payment | None:
        return self.db.query(Payment).filter(Payment.appointment_id == appointment_id).first()
