from base64 import b64encode

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import settings
from app.models.professional import Professional
from app.models.professional_service import ProfessionalService
from app.models.service import Service


def _admin_headers() -> dict[str, str]:
    credentials = b64encode(f"admin:{settings.admin_api_key}".encode()).decode()
    return {"Authorization": f"Basic {credentials}"}


def test_services_page_is_in_admin_navigation(anonymous_client: TestClient):
    response = anonymous_client.get("/admin/services", headers=_admin_headers())

    assert response.status_code == 200
    assert "Gestão de Serviços" in response.text
    assert 'href="/admin/services"' in response.text


def test_admin_manages_shared_service_catalog(anonymous_client: TestClient):
    created = anonymous_client.post(
        "/admin/api/services",
        headers=_admin_headers(),
        json={
            "name": "Massagem relaxante",
            "description": "Sessão de bem-estar",
            "category": "Massagens",
        },
    )

    assert created.status_code == 201
    service = created.json()
    assert service["name"] == "Massagem relaxante"
    assert service["active"] is True
    assert service["active_offerings_count"] == 0

    updated = anonymous_client.put(
        f"/admin/api/services/{service['id']}",
        headers=_admin_headers(),
        json={"name": "Massagem terapêutica", "category": "Terapias"},
    )

    assert updated.status_code == 200
    assert updated.json()["name"] == "Massagem terapêutica"
    assert updated.json()["category"] == "Terapias"


def test_deleting_catalog_service_with_offering_archives_it(
    anonymous_client: TestClient, db_session: Session
):
    professional = Professional(name="Profissional", phone="11999999999")
    service = Service(name="Corte", category="Cabelos", active=True)
    db_session.add_all([professional, service])
    db_session.commit()
    db_session.add(
        ProfessionalService(
            professional_id=professional.id,
            service_id=service.id,
            price_cents=9000,
            duration_minutes=45,
        )
    )
    db_session.commit()

    deleted = anonymous_client.delete(
        f"/admin/api/services/{service.id}", headers=_admin_headers()
    )

    assert deleted.status_code == 200
    assert deleted.json() == {"outcome": "archived"}
    assert db_session.get(Service, service.id).active is False

    reactivated = anonymous_client.post(
        f"/admin/api/services/{service.id}/reactivate", headers=_admin_headers()
    )

    assert reactivated.status_code == 200
    assert reactivated.json()["active"] is True
