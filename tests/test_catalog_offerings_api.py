from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import settings
from app.models.professional import Professional
from app.models.professional_service import ProfessionalService
from app.models.service import Service


def _mcp_call(client: TestClient, name: str, arguments: dict):
    return client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "method": "tools/call",
            "id": 1,
            "params": {"name": name, "arguments": arguments},
        },
        headers={"Authorization": f"Bearer {settings.api_key}"},
    )


def _create_catalog_offerings(db_session: Session) -> tuple[Service, Professional]:
    service = Service(
        name="Massagem relaxante",
        category="Bem-estar",
        price_cents=15000,
        duration_minutes=60,
        active=True,
    )
    professional = Professional(name="Ana Lima", phone="11999999999", active=True)
    inactive_professional = Professional(
        name="Bruno Lima", phone="11999999998", active=False
    )
    db_session.add_all([service, professional, inactive_professional])
    db_session.flush()
    db_session.add_all(
        [
            ProfessionalService(
                professional_id=professional.id,
                service_id=service.id,
                commission_percent="10.00",
                active=True,
            ),
            ProfessionalService(
                professional_id=inactive_professional.id,
                service_id=service.id,
                commission_percent="25.00",
                active=True,
            ),
        ]
    )
    db_session.commit()
    return service, professional


def test_api_lists_only_active_offerings_from_global_catalog(
    client: TestClient, db_session: Session
):
    service, professional = _create_catalog_offerings(db_session)

    response = client.get("/api/services")

    assert response.status_code == 200
    assert response.json() == [
        {
            "service_id": service.id,
            "professional_id": professional.id,
            "name": "Massagem relaxante",
            "description": None,
            "category": "Bem-estar",
            "price_cents": 15000,
            "duration_minutes": 60,
            "commission_percent": "10.00",
        }
    ]


def test_mcp_lists_catalog_service_using_active_offering_values(
    client: TestClient, db_session: Session
):
    _create_catalog_offerings(db_session)

    response = _mcp_call(client, "listar_servicos", {})

    assert response.status_code == 200
    result = response.json()["result"]
    assert result.get("isError") is not True
    text = result["content"][0]["text"]
    assert "Massagem relaxante" in text
    assert "R$ 150,00" in text
    assert "(60min)" in text
    assert "Ana Lima" in text
    assert "Bruno Lima" not in text


def test_api_uses_company_terms_and_professional_commission(
    client: TestClient, db_session: Session
):
    service, first_professional = _create_catalog_offerings(db_session)
    second_professional = Professional(
        name="Carla Lima", phone="11999999997", active=True
    )
    db_session.add(second_professional)
    db_session.flush()
    db_session.add(
        ProfessionalService(
            professional_id=second_professional.id,
            service_id=service.id,
            commission_percent="25.00",
            active=True,
        )
    )
    db_session.commit()

    response = client.get("/api/services")

    assert response.status_code == 200
    items = {item["professional_id"]: item for item in response.json()}
    assert items[first_professional.id]["price_cents"] == 15000
    assert items[second_professional.id]["price_cents"] == 15000
    assert items[first_professional.id]["duration_minutes"] == 60
    assert items[second_professional.id]["duration_minutes"] == 60
    assert items[first_professional.id]["commission_percent"] == "10.00"
    assert items[second_professional.id]["commission_percent"] == "25.00"
