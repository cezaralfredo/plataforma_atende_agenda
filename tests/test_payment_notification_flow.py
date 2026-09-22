import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import settings
from app.mcp.tools import handle_tool_call
from app.models.notification_log import NotificationLog
from app.services.notification_service import (
    NotificationService,
    build_payment_notification_payload,
    format_payment_confirmation_message,
)
from tests.seed import seed_appointment, seed_data, seed_payment


def test_format_payment_confirmation_message(db_session: Session):
    entities = seed_data(db_session)
    appointment = seed_appointment(db_session, entities)
    payment = seed_payment(db_session, appointment)
    payment.amount_cents = 15000
    payment.billing_type = "pix"

    msg = format_payment_confirmation_message(appointment, payment)

    assert "R$ 150.00 (PIX)" in msg
    assert "confirmado com sucesso" in msg
    assert appointment.service.name in msg
    assert appointment.professional.name in msg
    assert f"#{appointment.id}" in msg


def test_build_payment_notification_payload(db_session: Session):
    entities = seed_data(db_session)
    appointment = seed_appointment(db_session, entities)
    payment = seed_payment(db_session, appointment)
    payment.status = "confirmed"
    payment.amount_cents = 8000
    payment.billing_type = "pix"
    payment.asaas_payment_id = "pay_test_123"

    payload = build_payment_notification_payload(appointment, payment)

    assert payload["event"] == "payment.confirmed"
    assert payload["appointment_id"] == appointment.id
    assert payload["payment_id"] == payment.id
    assert payload["asaas_payment_id"] == "pay_test_123"
    assert payload["amount_cents"] == 8000
    assert payload["client"]["name"] == appointment.user.name
    assert payload["service"]["name"] == appointment.service.name
    assert payload["professional"]["name"] == appointment.professional.name
    assert "formatted_message" in payload


@pytest.mark.asyncio
async def test_notification_service_dispatch_to_n8n(db_session: Session):
    entities = seed_data(db_session)
    appointment = seed_appointment(db_session, entities)
    payment = seed_payment(db_session, appointment)
    appointment.notified_at = None
    db_session.commit()

    service = NotificationService(db_session)

    mock_resp = AsyncMock()
    mock_resp.raise_for_status = MagicMock()

    with (
        patch.object(settings, "n8n_webhook_url", "https://n8n.test/webhook/payment"),
        patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post,
    ):
        mock_post.return_value = mock_resp
        dispatched = await service.dispatch_payment_confirmed(appointment.id, payment.id)

        assert dispatched is True
        assert mock_post.called
        call_args = mock_post.call_args
        assert call_args[0][0] == "https://n8n.test/webhook/payment"
        sent_json = call_args[1]["json"]
        assert sent_json["event"] == "payment.confirmed"
        assert sent_json["appointment_id"] == appointment.id

    db_session.refresh(appointment)
    assert appointment.notified_at is not None

    log = (
        db_session.query(NotificationLog)
        .filter(
            NotificationLog.appointment_id == appointment.id,
            NotificationLog.type == "confirmation",
        )
        .first()
    )
    assert log is not None


@pytest.mark.asyncio
async def test_notification_service_no_webhook_configured(db_session: Session):
    entities = seed_data(db_session)
    appointment = seed_appointment(db_session, entities)
    payment = seed_payment(db_session, appointment)
    appointment.notified_at = None
    db_session.commit()

    service = NotificationService(db_session)

    with (
        patch.object(settings, "n8n_webhook_url", ""),
        patch.object(settings, "hermes_webhook_url", ""),
        patch.object(settings, "notification_webhook_url", ""),
    ):
        dispatched = await service.dispatch_payment_confirmed(appointment.id, payment.id)
        assert dispatched is False

    db_session.refresh(appointment)
    assert appointment.notified_at is None


def test_asaas_webhook_dispatches_notification(client: TestClient, db_session: Session):
    entities = seed_data(db_session)
    appointment = seed_appointment(db_session, entities)
    payment = seed_payment(db_session, appointment)
    appointment.status = "awaiting_payment"
    appointment.notified_at = None
    payment.status = "pending"
    db_session.commit()

    with patch(
        "app.services.notification_service.NotificationService.dispatch_payment_confirmed",
        new_callable=AsyncMock,
    ) as mock_dispatch:
        mock_dispatch.return_value = True

        response = client.post(
            "/webhooks/asaas",
            json={
                "id": "evt_test_notif_dispatch",
                "event": "PAYMENT_RECEIVED",
                "payment": {"id": payment.asaas_payment_id},
            },
            headers={"asaas-access-token": settings.asaas_webhook_token},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

        db_session.refresh(appointment)
        assert appointment.status == "confirmed"

        assert mock_dispatch.called
        assert mock_dispatch.call_args[0][0] == appointment.id
        assert mock_dispatch.call_args[0][1] == payment.id


def test_mcp_tool_verificar_status_pagamento_confirmed(db_session: Session):
    entities = seed_data(db_session)
    appointment = seed_appointment(db_session, entities)
    payment = seed_payment(db_session, appointment)
    appointment.status = "confirmed"
    appointment.notified_at = None
    payment.status = "confirmed"
    payment.amount_cents = 12000
    payment.billing_type = "pix"
    db_session.commit()

    result = asyncio.run(
        handle_tool_call("verificar_status_pagamento", {"appointment_id": appointment.id}, db_session)
    )
    text = result["content"][0]["text"]

    assert "Pagamento CONFIRMADO com sucesso" in text
    assert f"#{appointment.id}" in text
    assert "R$ 120.00 (PIX)" in text
    assert appointment.service.name in text

    db_session.refresh(appointment)
    assert appointment.notified_at is not None


def test_mcp_tool_verificar_status_pagamento_pending(db_session: Session):
    entities = seed_data(db_session)
    appointment = seed_appointment(db_session, entities)
    payment = seed_payment(db_session, appointment)
    appointment.status = "awaiting_payment"
    payment.status = "pending"
    payment.amount_cents = 5000
    payment.invoice_url = "https://sandbox.asaas.com/i/test_invoice"
    db_session.commit()

    with patch(
        "app.services.payment_service.PaymentService.check_payment_status",
        new_callable=AsyncMock,
    ) as mock_check:
        mock_check.return_value = "pending"
        result = asyncio.run(
            handle_tool_call("verificar_status_pagamento", {"appointment_id": appointment.id}, db_session)
        )

    text = result["content"][0]["text"]
    assert "Pagamento PENDENTE" in text
    assert "https://sandbox.asaas.com/i/test_invoice" in text
    assert "R$ 50.00" in text


def test_mcp_tool_meus_agendamentos_rich_format(db_session: Session):
    entities = seed_data(db_session)
    appointment = seed_appointment(db_session, entities)
    payment = seed_payment(db_session, appointment)
    appointment.status = "confirmed"
    payment.status = "confirmed"
    db_session.commit()

    result = asyncio.run(
        handle_tool_call("meus_agendamentos", {"user_id": appointment.user_id}, db_session)
    )
    text = result["content"][0]["text"]

    assert f"#{appointment.id}" in text
    assert appointment.service.name in text
    assert appointment.professional.name in text
    assert "Pagamento: Confirmado" in text

    # Test via phone
    result_phone = asyncio.run(
        handle_tool_call("meus_agendamentos", {"phone": entities["user"].phone}, db_session)
    )
    text_phone = result_phone["content"][0]["text"]
    assert f"#{appointment.id}" in text_phone

    # Test without valid user
    result_none = asyncio.run(
        handle_tool_call("meus_agendamentos", {"phone": "99999999999"}, db_session)
    )
    assert "Não foi possível localizar o cliente" in result_none["content"][0]["text"]

