
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import settings
from tests.seed import seed_appointment, seed_data, seed_payment


def _admin_headers() -> dict[str, str]:
    return {"X-Admin-Key": settings.admin_api_key}


def test_admin_can_create_client_and_appointment(
    anonymous_client: TestClient, db_session: Session
):
    entities = seed_data(db_session)

    response = anonymous_client.post(
        "/admin/api/appointments",
        headers=_admin_headers(),
        json={
            "new_client": {
                "name": "Cliente Teste",
                "phone": "+5511977777777",
                "email": "cliente@example.com",
            },
            "professional_id": entities["professional"].id,
            "service_id": entities["service"].id,
            "start_time": "2026-07-30T09:00:00-03:00",
            "end_time": "2026-07-30T10:00:00-03:00",
        },
    )

    assert response.status_code == 201
    assert response.json()["status"] == "pending"
    assert response.json()["client_name"] == "Cliente Teste"


def test_appointments_page_exposes_admin_creation_flow(
    anonymous_client: TestClient, db_session: Session
):
    seed_data(db_session)

    response = anonymous_client.get(
        "/admin/appointments", headers=_admin_headers()
    )

    assert response.status_code == 200
    assert "Novo agendamento" in response.text
    assert "Cadastrar novo cliente" in response.text
    assert "Excluir" in response.text


def test_complete_action_returns_domain_response_instead_of_500(
    anonymous_client: TestClient, db_session: Session
):
    entities = seed_data(db_session)
    appointment = seed_appointment(db_session, entities)
    appointment.status = "confirmed"
    db_session.commit()

    response = anonymous_client.post(
        f"/admin/appointments/{appointment.id}/action",
        headers=_admin_headers(),
        json={"action": "complete", "notes": "Serviço realizado"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "completed"


def test_admin_can_update_pending_appointment_notes(
    anonymous_client: TestClient, db_session: Session
):
    entities = seed_data(db_session)
    appointment = seed_appointment(db_session, entities)
    appointment.status = "pending"
    db_session.commit()

    response = anonymous_client.put(
        f"/admin/api/appointments/{appointment.id}",
        headers=_admin_headers(),
        json={"notes": "Cliente pediu confirmação por WhatsApp"},
    )

    assert response.status_code == 200
    assert response.json()["notes"] == "Cliente pediu confirmação por WhatsApp"


def test_admin_cannot_delete_appointment_with_payment(
    anonymous_client: TestClient, db_session: Session
):
    entities = seed_data(db_session)
    appointment = seed_appointment(db_session, entities)
    seed_payment(db_session, appointment)

    response = anonymous_client.delete(
        f"/admin/api/appointments/{appointment.id}", headers=_admin_headers()
    )

    assert response.status_code == 409
    assert "pagamento" in response.json()["detail"].lower()
