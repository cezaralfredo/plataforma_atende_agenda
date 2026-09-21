from base64 import b64encode
from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.admin.service import AdminService
from app.config import settings
from app.models.payment import Payment
from tests.seed import seed_appointment, seed_data


def test_appointment_list_returns_one_row_with_latest_payment(db_session: Session):
    entities = seed_data(db_session)
    appointment = seed_appointment(db_session, entities)
    old = Payment(
        appointment_id=appointment.id,
        asaas_payment_id="pay_old",
        amount_cents=5000,
        billing_type="pix",
        status="cancelled",
        created_at=datetime(2026, 8, 1),
        updated_at=datetime(2026, 8, 1),
    )
    latest = Payment(
        appointment_id=appointment.id,
        asaas_payment_id="pay_latest",
        amount_cents=5000,
        billing_type="pix",
        status="pending",
        created_at=datetime(2026, 8, 2),
        updated_at=datetime(2026, 8, 2),
    )
    db_session.add_all([old, latest])
    db_session.commit()

    rows, total = AdminService(db_session).list_appointments()

    assert total == 1
    assert len(rows) == 1
    assert rows[0]["payment_id"] == latest.id


def test_confirmed_payment_is_not_counted_pending(db_session: Session):
    entities = seed_data(db_session)
    appointment = seed_appointment(db_session, entities)
    db_session.add(
        Payment(
            appointment_id=appointment.id,
            asaas_payment_id="pay_confirmed",
            amount_cents=5000,
            billing_type="pix",
            status="confirmed",
        )
    )
    db_session.commit()
    assert AdminService(db_session).get_kpis()["payments_pending"] == 0


def test_admin_rejects_zero_page(anonymous_client: TestClient):
    credentials = b64encode(f"admin:{settings.admin_api_key}".encode()).decode()
    response = anonymous_client.get(
        "/admin/api/appointments?page=0",
        headers={"Authorization": f"Basic {credentials}"},
    )
    assert response.status_code == 422


def test_reconcile_paid_appointments_updates_cancelled_to_confirmed(db_session: Session):
    entities = seed_data(db_session)
    appointment = seed_appointment(db_session, entities)
    appointment.status = "cancelled"
    db_session.add(
        Payment(
            appointment_id=appointment.id,
            asaas_payment_id="pay_rec_1",
            amount_cents=5000,
            billing_type="pix",
            status="received",
        )
    )
    db_session.commit()

    rows, total = AdminService(db_session).list_appointments()
    assert total == 1
    assert rows[0]["status"] == "confirmed"
    assert rows[0]["payment_status"] == "received"

    db_session.refresh(appointment)
    assert appointment.status == "confirmed"


def test_reconcile_paid_appointments_preserves_explicit_admin_cancellation(db_session: Session):
    entities = seed_data(db_session)
    appointment = seed_appointment(db_session, entities)
    appointment.status = "cancelled"
    appointment.notes = "[Admin] Cancelado: Cliente solicitou cancelamento formal"
    db_session.add(
        Payment(
            appointment_id=appointment.id,
            asaas_payment_id="pay_rec_2",
            amount_cents=5000,
            billing_type="pix",
            status="received",
        )
    )
    db_session.commit()

    rows, total = AdminService(db_session).list_appointments()
    assert total == 1
    assert rows[0]["status"] == "cancelled"

    db_session.refresh(appointment)
    assert appointment.status == "cancelled"


def test_admin_can_reactivate_and_confirm_cancelled_appointment(db_session: Session):
    entities = seed_data(db_session)
    appointment = seed_appointment(db_session, entities)
    appointment.status = "cancelled"
    db_session.commit()

    admin_service = AdminService(db_session)
    result = admin_service.appointment_action(appointment.id, "confirm", notes="Reativado após verificar pagamento")

    assert result["status"] == "confirmed"
    assert "[Admin] Confirmado: Reativado após verificar pagamento" in result["notes"]

    db_session.refresh(appointment)
    assert appointment.status == "confirmed"

