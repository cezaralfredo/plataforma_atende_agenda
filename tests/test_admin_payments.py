from base64 import b64encode
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import settings
from app.services.asaas_client import AsaasClient, AsaasIntegrationError
from tests.seed import seed_appointment, seed_data, seed_payment


def _admin_headers() -> dict[str, str]:
    credentials = b64encode(f"admin:{settings.admin_api_key}".encode()).decode()
    return {"Authorization": f"Basic {credentials}"}


def _received_payment(db_session: Session):
    entities = seed_data(db_session)
    appointment = seed_appointment(db_session, entities)
    payment = seed_payment(db_session, appointment)
    payment.status = "received"
    appointment.status = "confirmed"
    db_session.commit()
    return appointment, payment


def test_admin_refund_calls_asaas_before_local_change(
    anonymous_client: TestClient,
    db_session: Session,
    monkeypatch,
):
    appointment, payment = _received_payment(db_session)
    refund = AsyncMock(
        return_value={"id": payment.asaas_payment_id, "status": "REFUNDED"}
    )
    monkeypatch.setattr(AsaasClient, "refund_payment", refund)

    response = anonymous_client.post(
        f"/admin/payments/{payment.id}/action",
        json={"action": "refund"},
        headers=_admin_headers(),
    )

    assert response.status_code == 200
    assert refund.await_count == 1
    db_session.refresh(payment)
    db_session.refresh(appointment)
    assert payment.status == "refunded"
    assert appointment.status == "cancelled"


def test_failed_asaas_refund_keeps_local_status(
    anonymous_client: TestClient,
    db_session: Session,
    monkeypatch,
):
    appointment, payment = _received_payment(db_session)
    monkeypatch.setattr(
        AsaasClient,
        "refund_payment",
        AsyncMock(side_effect=AsaasIntegrationError("rejected")),
    )

    response = anonymous_client.post(
        f"/admin/payments/{payment.id}/action",
        json={"action": "refund"},
        headers=_admin_headers(),
    )

    assert response.status_code == 502
    db_session.refresh(payment)
    db_session.refresh(appointment)
    assert payment.status == "received"
    assert appointment.status == "confirmed"


def test_admin_refresh_reads_real_provider_status(
    anonymous_client: TestClient,
    db_session: Session,
    monkeypatch,
):
    entities = seed_data(db_session)
    appointment = seed_appointment(db_session, entities)
    payment = seed_payment(db_session, appointment)
    get_payment = AsyncMock(
        return_value={"id": payment.asaas_payment_id, "status": "CONFIRMED"}
    )
    monkeypatch.setattr(AsaasClient, "get_payment", get_payment)

    response = anonymous_client.post(
        f"/admin/payments/{payment.id}/action",
        json={"action": "refresh"},
        headers=_admin_headers(),
    )

    assert response.status_code == 200
    assert get_payment.await_count == 1
    db_session.refresh(payment)
    assert payment.status == "confirmed"


def test_admin_payment_action_rejects_unknown_action(
    anonymous_client: TestClient,
    db_session: Session,
):
    _appointment, payment = _received_payment(db_session)

    response = anonymous_client.post(
        f"/admin/payments/{payment.id}/action",
        json={"action": "mark_paid_locally"},
        headers=_admin_headers(),
    )

    assert response.status_code == 422
