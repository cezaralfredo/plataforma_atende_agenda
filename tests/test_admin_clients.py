from app.admin.service import AdminService
from app.models.user import User
from tests.seed import seed_appointment, seed_data


def test_client_without_history_is_deleted(db_session):
    client = User(name="Cliente avulso", phone="11911112222")
    db_session.add(client)
    db_session.commit()
    client_id = client.id

    outcome = AdminService(db_session).archive_or_delete_user(client_id)

    assert outcome == "deleted"
    assert db_session.get(User, client_id) is None


def test_client_with_appointment_history_is_archived_and_can_be_reactivated(db_session):
    entities = seed_data(db_session)
    appointment = seed_appointment(db_session, entities)
    client = appointment.user

    outcome = AdminService(db_session).archive_or_delete_user(client.id)

    assert outcome == "archived"
    db_session.refresh(client)
    assert client.active is False

    reactivated = AdminService(db_session).reactivate_user(client.id)

    assert reactivated is not None
    assert reactivated.active is True
