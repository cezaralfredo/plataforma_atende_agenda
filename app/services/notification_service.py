import logging
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.models.appointment import Appointment
from app.models.notification_log import NotificationLog
from app.models.payment import Payment

logger = logging.getLogger(__name__)


def format_payment_confirmation_message(appointment: Appointment, payment: Payment) -> str:
    """Gera mensagem formatada e humanizada de confirmação para envio via WhatsApp."""
    user_name = appointment.user.name if appointment.user else "Cliente"
    service_name = appointment.service.name if appointment.service else "Serviço"
    professional_name = appointment.professional.name if appointment.professional else "Profissional"
    date_str = appointment.start_time.strftime("%d/%m/%Y às %H:%M")
    amount = f"R$ {payment.amount_cents / 100:.2f}"
    billing = (payment.billing_type or "PIX").upper()

    return (
        f"Olá, {user_name}! 👋\n\n"
        f"✅ Seu pagamento de {amount} ({billing}) foi confirmado com sucesso!\n\n"
        f"📋 *Detalhes da sua Reserva:*\n"
        f"• *Serviço:* {service_name}\n"
        f"• *Profissional:* {professional_name}\n"
        f"• *Data e Horário:* {date_str}\n"
        f"• *Código da Reserva:* #{appointment.id}\n\n"
        f"Sua vaga está garantida na nossa agenda. Qualquer dúvida, é só responder por aqui!"
    )


def build_payment_notification_payload(appointment: Appointment, payment: Payment) -> dict[str, Any]:
    """Monta payload padronizado para envio ao n8n ou Hermes."""
    user = appointment.user
    service = appointment.service
    prof = appointment.professional

    client_phone = user.phone if user else ""
    whatsapp = getattr(user, "whatsapp_number", None) or client_phone

    return {
        "event": "payment.confirmed",
        "timestamp": datetime.now(UTC).isoformat(),
        "appointment_id": appointment.id,
        "chatId": whatsapp,
        "whatsapp": whatsapp,
        "payment_id": payment.id,
        "asaas_payment_id": payment.asaas_payment_id,
        "status": appointment.status,
        "payment_status": payment.status,
        "amount_cents": payment.amount_cents,
        "billing_type": payment.billing_type,
        "client": {
            "id": user.id if user else None,
            "name": user.name if user else "Cliente",
            "phone": client_phone,
            "whatsapp_number": whatsapp,
        },
        "service": {
            "id": service.id if service else None,
            "name": service.name if service else "Serviço",
            "duration_minutes": getattr(service, "duration_minutes", None),
            "price_cents": getattr(service, "price_cents", None),
        },
        "professional": {
            "id": prof.id if prof else None,
            "name": prof.name if prof else "Profissional",
        },
        "appointment": {
            "id": appointment.id,
            "start_time": appointment.start_time.isoformat() if appointment.start_time else None,
            "end_time": appointment.end_time.isoformat() if appointment.end_time else None,
            "notes": appointment.notes,
        },
        "formatted_message": format_payment_confirmation_message(appointment, payment),
    }


class NotificationService:
    def __init__(self, db: Session):
        self.db = db

    def get_effective_webhook_url(self) -> str:
        return (
            getattr(settings, "n8n_webhook_url", "")
            or getattr(settings, "hermes_webhook_url", "")
            or getattr(settings, "notification_webhook_url", "")
        )

    async def dispatch_payment_confirmed(self, appointment_id: int, payment_id: int) -> bool:
        """Envia notificação de pagamento confirmado para o n8n/Hermes e marca como notificado se configurado."""
        appointment = (
            self.db.query(Appointment)
            .options(
                joinedload(Appointment.user),
                joinedload(Appointment.service),
                joinedload(Appointment.professional),
            )
            .filter(Appointment.id == appointment_id)
            .first()
        )
        if not appointment:
            logger.warning("Appointment %s not found for notification dispatch", appointment_id)
            return False

        payment = self.db.query(Payment).filter(Payment.id == payment_id).first()
        if not payment:
            logger.warning("Payment %s not found for notification dispatch", payment_id)
            return False

        webhook_url = self.get_effective_webhook_url()
        if not webhook_url:
            logger.info(
                "No n8n/Hermes notification webhook URL configured. Appointment %s queued for Hermes pull via listar_pendentes_notificacao.",
                appointment.id,
            )
            return False

        payload = build_payment_notification_payload(appointment, payment)
        headers = {"Content-Type": "application/json"}
        token = getattr(settings, "notification_webhook_token", "")
        if token:
            headers["Authorization"] = f"Bearer {token}"

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(webhook_url, json=payload, headers=headers)
                response.raise_for_status()

            # Marca como notificado no banco de dados
            now = datetime.now(UTC)
            appointment.notified_at = now
            self.db.add(
                NotificationLog(
                    appointment_id=appointment.id,
                    type="confirmation",
                    sent_at=now,
                )
            )
            self.db.commit()
            logger.info(
                "Payment confirmation successfully dispatched to %s for appointment %s",
                webhook_url,
                appointment.id,
            )
            return True
        except Exception as e:
            logger.warning(
                "Failed to dispatch payment confirmation webhook to %s for appointment %s: %s",
                webhook_url,
                appointment.id,
                e,
            )
            return False
