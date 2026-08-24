from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.business_time import as_business_time
from tests.seed import seed_data


def test_naive_datetime_is_interpreted_in_business_timezone():
    value = as_business_time(datetime(2026, 8, 24, 9, 0))
    assert value.isoformat() == "2026-08-24T09:00:00-03:00"


def test_utc_datetime_is_converted_to_business_timezone():
    value = as_business_time(datetime(2026, 8, 24, 12, 0, tzinfo=UTC))
    assert value.isoformat() == "2026-08-24T09:00:00-03:00"


def test_booking_with_z_suffix_compares_against_local_availability(
    client: TestClient,
    db_session: Session,
):
    entities = seed_data(db_session)
    response = client.post(
        "/api/appointments",
        json={
            "user_id": entities["user"].id,
            "professional_id": entities["professional"].id,
            "service_id": entities["service"].id,
            "start_time": "2026-07-30T12:00:00Z",
            "end_time": "2026-07-30T13:00:00Z",
        },
    )

    assert response.status_code == 201
    assert response.json()["start_time"].endswith("-03:00")
