from base64 import b64encode

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import settings
from app.models.professional import Professional


def _admin_headers() -> dict[str, str]:
    credentials = b64encode(f"admin:{settings.admin_api_key}".encode()).decode()
    return {"Authorization": f"Basic {credentials}"}


def test_professionals_overview_api_limits_rows_without_changing_row_contract(
    anonymous_client: TestClient,
    db_session: Session,
):
    for index in range(6):
        db_session.add(
            Professional(
                name=f"Profissional {index + 1}",
                phone=f"+5511999999{index:03d}",
                active=True,
            )
        )
    db_session.commit()

    response = anonymous_client.get(
        "/admin/api/professionals?limit=5",
        headers=_admin_headers(),
    )

    assert response.status_code == 200
    professionals = response.json()
    assert len(professionals) == 5
    assert set(professionals[0]) >= {
        "id",
        "name",
        "active",
        "services_count",
        "appointments_today",
        "appointments_week",
        "revenue_month_cents",
    }
