import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session, joinedload

from app.models.appointment import Appointment
from app.models.payment import Payment
from app.repositories import UserRepository
from app.repositories.appointment_repo import AppointmentRepository
from app.repositories.payment_repo import PaymentRepository
from app.services.asaas_client import (
    AsaasClient,
    AsaasIntegrationError,
    AsaasUncertainResultError,
)
from app.services.payment_state_service import apply_payment_state

logger = logging.getLogger(__name__)

ASAAS_STATUS_MAP = {
    "PENDING": "pending",
    "RECEIVED": "received",
    "CONFIRMED": "confirmed",
    "OVERDUE": "overdue",
    "REFUNDED": "refunded",
    "CANCELLED": "cancelled",
}


class AsaasReconciliationError(AsaasIntegrationError):
    """Remote records cannot be mapped safely to one local entity."""


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

        external_reference = f"user:{user.id}"
        matches = await self.asaas.list_customers(external_reference)
        customer = self._single_remote_match(matches, external_reference)
        if customer is None:
            try:
                customer = await self.asaas.create_customer(
                    name=user.name,
                    phone=user.phone,
                    email=user.email,
                    external_reference=external_reference,
                    cpf_cnpj=user.cpf_cnpj,
                )
            except AsaasUncertainResultError:
                matches = await self.asaas.list_customers(external_reference)
                customer = self._single_remote_match(matches, external_reference)
                if customer is None:
                    raise

        customer_id = customer.get("id")
        if not customer_id:
            raise AsaasReconciliationError(
                f"Asaas customer {external_reference} has no id"
            )

        # If the user has a CPF/CNPJ and the customer was not just created with
        # it, ensure it is present on the Asaas customer so charges can be made.
        if user.cpf_cnpj:
            try:
                await self.asaas.update_customer(customer_id, cpf_cnpj=user.cpf_cnpj)
            except AsaasUncertainResultError:
                pass

        user.asaas_customer_id = customer_id
        self.db.flush()
        return customer_id

    @staticmethod
    def _single_remote_match(
        matches: list[dict],
        external_reference: str,
    ) -> dict | None:
        if len(matches) > 1:
            raise AsaasReconciliationError(
                f"Asaas returned multiple records for {external_reference}"
            )
        return matches[0] if matches else None

    @staticmethod
    def _payment_from_asaas(
        appointment: Appointment,
        payload: dict,
        billing_type: str,
    ) -> Payment:
        payment_id = payload.get("id")
        if not payment_id:
            raise AsaasReconciliationError("Asaas payment has no id")
        remote_status = payload.get("status")
        return Payment(
            appointment_id=appointment.id,
            asaas_payment_id=payment_id,
            amount_cents=appointment.service.price_cents,
            billing_type=billing_type,
            status=(
                ASAAS_STATUS_MAP.get(remote_status, "pending")
                if isinstance(remote_status, str)
                else "pending"
            ),
            invoice_url=payload.get("invoiceUrl"),
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

    def _locked_appointment_query(self, appointment_id: int):
        return (
            self.db.query(Appointment)
            .options(
                joinedload(Appointment.service),
                joinedload(Appointment.professional),
                joinedload(Appointment.user),
            )
            .filter(Appointment.id == appointment_id)
            .with_for_update(of=Appointment)
        )

    async def create_charge(
        self,
        appointment_id: int,
        billing_type: str = "undefined",
        amount_cents: int | None = None,
    ) -> Payment:
        self.appointment_repo.expire_reservations(datetime.now(UTC))
        self.db.flush()
        appointment = self._locked_appointment_query(appointment_id).first()

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

        if not appointment.service:
            raise ValueError("Agendamento sem serviço")
        value_cents = appointment.service.price_cents
        if amount_cents is not None and amount_cents != value_cents:
            raise ValueError("Charge amount must match the service price")

        external_reference = f"appointment:{appointment.id}"
        matches = await self.asaas.list_payments(
            external_reference=external_reference
        )
        remote_payment = self._single_remote_match(matches, external_reference)
        if remote_payment is None:
            customer_id = await self.ensure_asaas_customer(appointment.user_id)
            due_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
            try:
                remote_payment = await self.asaas.create_payment(
                    customer_id=customer_id,
                    value=value_cents / 100.0,
                    due_date=due_date,
                    description=(
                        f"{appointment.service.name} - {appointment.professional.name}"
                    ),
                    billing_type=asaas_billing_type,
                    external_reference=external_reference,
                )
            except AsaasUncertainResultError:
                matches = await self.asaas.list_payments(
                    external_reference=external_reference
                )
                remote_payment = self._single_remote_match(
                    matches, external_reference
                )
                if remote_payment is None:
                    raise

        payment = self._payment_from_asaas(
            appointment,
            remote_payment,
            billing_type,
        )
        self.db.add(payment)
        appointment.status = (
            "confirmed"
            if payment.status in {"received", "confirmed"}
            else "awaiting_payment"
        )
        self.db.commit()
        self.db.refresh(payment)
        return payment

    async def check_payment_status(self, payment: Payment) -> str:
        if not payment.asaas_payment_id:
            return payment.status

        resp = await self.asaas.get_payment(payment.asaas_payment_id)
        asaas_status = resp.get("status", "")

        new_status = ASAAS_STATUS_MAP.get(asaas_status, payment.status)

        if new_status != payment.status:
            apply_payment_state(payment, new_status, datetime.now(UTC))
            self.db.commit()

        return new_status

    async def refresh(self, payment_id: int) -> Payment:
        payment = self.db.query(Payment).filter(Payment.id == payment_id).first()
        if not payment:
            raise ValueError("Pagamento não encontrado")
        await self.check_payment_status(payment)
        self.db.refresh(payment)
        return payment

    async def refund(self, payment_id: int) -> Payment:
        payment = self.db.query(Payment).filter(Payment.id == payment_id).first()
        if not payment:
            raise ValueError("Pagamento não encontrado")
        if payment.status not in {"received", "confirmed"}:
            raise ValueError(
                "Só é possível estornar pagamentos recebidos/confirmados"
            )
        if not payment.asaas_payment_id:
            raise ValueError("Pagamento sem identificador do Asaas")

        await self.asaas.refund_payment(payment.asaas_payment_id)
        apply_payment_state(payment, "refunded", datetime.now(UTC))
        self.db.commit()
        self.db.refresh(payment)
        return payment

    async def verify_recent_payments(self) -> list[Payment]:
        # Expire stale reservations first so the financeiro cron also cleans
        # reservations whose payment window lapsed; prevents lingering pending
        # rows and the "cannot charge a cancelled appointment" re-dispatch loop.
        self.appointment_repo.expire_reservations(datetime.now(UTC))
        self.db.flush()

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
                logger.exception(
                    "Recent payment verification failed payment_id=%s appointment_id=%s",
                    payment.id,
                    payment.appointment_id,
                )
                continue

        return updated

    def get_payment_by_appointment(self, appointment_id: int) -> Payment | None:
        return self.db.query(Payment).filter(Payment.appointment_id == appointment_id).first()
